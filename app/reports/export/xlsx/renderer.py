from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.models.report import Report
from app.reports.export.payloads.inventory import get_report_kubernetes_inventory_payload
from app.reports.export.payloads.tls_certificate_health import get_report_tls_certificate_health_payload
from app.reports.export.xlsx.builder import InventoryWorkbookContext, build_inventory_workbook
from app.reports.export.xlsx.standard import INVENTORY_XLSX_REPORT_TYPES
from app.reports.storage.naming import get_report_cluster_name

_PERIOD_LABELS = {
    'snapshot': 'Current Inventory Snapshot',
    '24h': 'Last 24 Hours',
    '7d': 'Last 7 Days',
    '30d': 'Last 30 Days',
    '90d': 'Last 90 Days',
    'month': 'This Month',
}


def render_inventory_xlsx(report: Report, output_path: Path) -> None:
    if report.report_type not in INVENTORY_XLSX_REPORT_TYPES:
        raise ValueError(f'Report type {report.report_type!r} is not an Inventory Excel report.')

    payload = _collect_inventory_payload(report)
    error = str(payload.get('_error') or '').strip()
    if error:
        raise RuntimeError(error)

    generated_at = datetime.now(UTC)
    context = InventoryWorkbookContext(
        report_id=report.id,
        report_name=report.name,
        report_type=report.report_type,
        generated_at=generated_at,
        generated_by=_generated_by_label(report),
        cluster_scope=get_report_cluster_name(report) or 'All Clusters',
        namespace_scope=report.namespace or 'All Namespaces',
        period_label=_PERIOD_LABELS.get(report.period, report.period or 'Current Inventory Snapshot'),
        data_cutoff=payload.get('data_cutoff') or payload.get('collected_at') or generated_at,
    )
    build_inventory_workbook(
        report_type=report.report_type,
        payload=payload,
        context=context,
        output_path=output_path,
    )


def _collect_inventory_payload(report: Report) -> dict[str, Any]:
    if report.report_type == 'tls_inventory':
        return get_report_tls_certificate_health_payload(report)
    return get_report_kubernetes_inventory_payload(report)


def _generated_by_label(report: Report) -> str:
    display_name = str(report.generated_by_display_name_snapshot or '').strip()
    username = str(report.generated_by_username_snapshot or '').strip()
    return display_name or username or 'KAORI'
