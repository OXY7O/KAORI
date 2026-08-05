from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from app.models.report import Report
from app.reports.catalog import get_report_type_spec

JOB_CONTRACT_VERSION = 'kaori-report-job-v1.0'
ANALYTICS_PERIODS = {'24h': timedelta(hours=24), '7d': timedelta(days=7), '30d': timedelta(days=30), '90d': timedelta(days=90)}


@dataclass(frozen=True)
class ReportJobParameters:
    contract_version: str
    report_id: int
    report_type: str
    report_family: str
    execution_mode: str
    selected_cluster_id: str
    namespace: str | None
    output_format: str
    sections: list[str]
    period: str
    window_start: str | None
    window_end: str
    snapshot_policy: str | None
    trigger_type: str
    schedule_id: int | None
    schedule_run_id: int | None
    requested_at: str

    def to_payload(self) -> dict[str, Any]:
        return asdict(self)


def build_report_job_parameters(
    report: Report,
    *,
    trigger_type: str,
    schedule_id: int | None = None,
    schedule_run_id: int | None = None,
    now: datetime | None = None,
) -> ReportJobParameters:
    if not report.id:
        raise ValueError('The report must be persisted before a job contract can be built.')
    if not report.cluster_id:
        raise ValueError('Report jobs require one selected cluster.')

    spec = get_report_type_spec(report.report_type)
    family = str(spec.family)
    boundary = (now or datetime.now(UTC)).astimezone(UTC)

    if family == 'analytics':
        execution_mode = 'time_range'
        window_end = boundary
        if report.period == 'month':
            window_start = boundary.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            duration = ANALYTICS_PERIODS.get(report.period)
            if duration is None:
                raise ValueError(f'Analytics report period {report.period!r} is not supported by the worker.')
            window_start = boundary - duration
        snapshot_policy = None
    elif family == 'inventory':
        if report.period != 'snapshot':
            raise ValueError('Inventory report jobs must use the committed snapshot period.')
        execution_mode = 'committed_snapshot'
        window_start = None
        window_end = boundary
        snapshot_policy = 'latest_committed_generation_at_or_before_cutoff'
    else:
        raise ValueError(f'Unsupported report family: {family}')

    return ReportJobParameters(
        contract_version=JOB_CONTRACT_VERSION,
        report_id=int(report.id),
        report_type=report.report_type,
        report_family=family,
        execution_mode=execution_mode,
        selected_cluster_id=str(report.cluster_id),
        namespace=report.namespace,
        output_format=report.output_format,
        sections=report.sections_as_list(),
        period=report.period,
        window_start=window_start.isoformat() if window_start else None,
        window_end=window_end.isoformat(),
        snapshot_policy=snapshot_policy,
        trigger_type=trigger_type,
        schedule_id=schedule_id,
        schedule_run_id=schedule_run_id,
        requested_at=boundary.isoformat(),
    )
