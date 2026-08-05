from __future__ import annotations

from app.dashboards.kubernetes.repository import count_records, query_all
from app.dashboards.kubernetes.schema import ReportingSnapshot, ReportItem
from app.dashboards.kubernetes.utils import coerce_datetime, get_attr, human_time
from app.models import Report, ReportSchedule, ReportTemplate


def build_reporting_snapshot(selected_cluster_id: str | None) -> ReportingSnapshot:
    reports = query_all(Report, selected_cluster_id, limit=3)
    latest: list[ReportItem] = []
    for report in reports:
        title = str(get_attr(report, 'title', 'name', 'report_name', default='Generated Report'))
        status = str(get_attr(report, 'status', default='unknown')).title()
        generated_at = coerce_datetime(get_attr(report, 'generated_at', 'created_at', 'updated_at'))
        latest.append(
            ReportItem(
                title=title,
                status=status,
                generated_at=human_time(generated_at) if generated_at else 'Unknown time',
            )
        )

    return ReportingSnapshot(
        generated_reports=count_records(Report, selected_cluster_id),
        templates=count_records(ReportTemplate),
        schedules=count_records(ReportSchedule, selected_cluster_id),
        latest_reports=latest,
        source_status='Available',
    )
