from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.models.report import Report
from app.reports.catalog import validate_report_instance
from app.reports.export.payloads.inventory import get_report_kubernetes_inventory_payload
from app.reports.export.payloads.tls_inventory import get_report_tls_inventory_payload
from app.reports.export.xlsx.standard import InventoryWorkbookProfile
from app.reports.reference import build_report_reference
from app.reports.storage.naming import get_report_cluster_name


@dataclass(frozen=True, slots=True)
class InventoryExportContext:
    report_id: int | str
    report_name: str
    report_type: str
    generated_at: datetime
    generated_by: str
    cluster_scope: str
    namespace_scope: str
    period_label: str
    data_cutoff: datetime | str | None
    source_label: str = 'Kubernetes Committed Inventory'
    classification: str = 'Internal'


def get_inventory_rows(
    payload: Mapping[str, Any],
    profile: InventoryWorkbookProfile,
) -> list[dict[str, Any]]:
    raw_rows = payload.get(profile.row_source, [])
    if not isinstance(raw_rows, Iterable) or isinstance(raw_rows, (str, bytes, Mapping)):
        return []

    return [dict(row) for row in raw_rows if isinstance(row, Mapping)]


PERIOD_LABELS = {
    'snapshot': 'Current Inventory Snapshot',
    '24h': 'Last 24 Hours',
    '7d': 'Last 7 Days',
    '30d': 'Last 30 Days',
    '90d': 'Last 90 Days',
    'month': 'This Month',
}


def collect_inventory_payload(report: Report) -> dict[str, Any]:
    validate_report_instance(report)
    if report.report_type == 'tls_inventory':
        return get_report_tls_inventory_payload(report)
    return get_report_kubernetes_inventory_payload(report)


def build_inventory_export_context(
    report: Report,
    payload: dict[str, Any],
    *,
    generated_at: datetime | None = None,
) -> InventoryExportContext:
    validate_report_instance(report)
    cluster_scope = get_report_cluster_name(report)
    if not cluster_scope:
        raise ValueError('The selected cluster no longer exists or cannot be resolved.')

    generated_at = generated_at or datetime.now(UTC)
    return InventoryExportContext(
        report_id=build_report_reference(report, generated_at=generated_at),
        report_name=report.name,
        report_type=report.report_type,
        generated_at=generated_at,
        generated_by=generated_by_label(report),
        cluster_scope=cluster_scope,
        namespace_scope=report.namespace or 'All Namespaces',
        period_label=PERIOD_LABELS.get(report.period, report.period or 'Current Inventory Snapshot'),
        data_cutoff=payload.get('data_cutoff') or payload.get('collected_at') or generated_at,
    )


def generated_by_label(report: Report) -> str:
    display_name = str(report.generated_by_display_name_snapshot or '').strip()
    username = str(report.generated_by_username_snapshot or '').strip()
    return display_name or username or 'KAORI'
