from __future__ import annotations

from app.kubernetes.dashboard.schema import ReportingSnapshot, ReportItem
from app.kubernetes.dashboard.utils import coerce_datetime, get_attr, human_time
from app.models import Report, ReportSchedule, ReportTemplate


def _kubernetes_report_query(selected_cluster_id: str | None):
    query = Report.query.filter(Report.report_domain == 'kubernetes')
    if selected_cluster_id:
        query = query.filter(Report.cluster_id == selected_cluster_id)
    return query


def count_kubernetes_reports(selected_cluster_id: str | None) -> int:
    """Count only Kubernetes-domain report records in the selected cluster scope."""
    return int(_kubernetes_report_query(selected_cluster_id).count())


def build_reporting_snapshot(selected_cluster_id: str | None) -> ReportingSnapshot:
    reports = (
        _kubernetes_report_query(selected_cluster_id)
        .order_by(Report.created_at.desc(), Report.id.desc())
        .limit(4)
        .all()
    )
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

    schedules_query = ReportSchedule.query.filter(ReportSchedule.report_domain == 'kubernetes')
    if selected_cluster_id:
        schedules_query = schedules_query.filter(ReportSchedule.cluster_id == selected_cluster_id)

    return ReportingSnapshot(
        generated_reports=count_kubernetes_reports(selected_cluster_id),
        templates=ReportTemplate.query.filter(ReportTemplate.report_domain == 'kubernetes').count(),
        schedules=schedules_query.count(),
        latest_reports=latest,
        source_status='Available',
    )
