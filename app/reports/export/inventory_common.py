from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.models.report import Report
from app.reports.catalog import (
    REPORT_FAMILY_INVENTORY,
    get_report_type_spec,
    validate_report_instance,
)
from app.reports.export.payloads.inventory import get_report_kubernetes_inventory_payload
from app.reports.export.payloads.object_storage_inventory import get_report_object_storage_inventory_payload
from app.reports.export.payloads.tls_inventory import get_report_tls_inventory_payload
from app.reports.export.tabular import TabularExportMetadata, build_record_reference
from app.reports.export.xlsx.standard import (
    InventoryWorkbookProfile,
    get_inventory_workbook_profile,
)
from app.reports.reference import build_report_reference
from app.reports.scope import OBJECT_STORAGE_SYSTEM_ASSET_TYPE, resolve_report_scope


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
    scope_label: str = 'Kubernetes Cluster'
    scope_asset_type: str = 'kubernetes_cluster'

    def tabular_metadata(self, *, format_standard: str) -> TabularExportMetadata:
        report_spec = get_report_type_spec(self.report_type)
        return TabularExportMetadata(
            format_standard=format_standard,
            document_reference=str(self.report_id),
            report_name=self.report_name,
            report_type=self.report_type,
            report_type_label=report_spec.label,
            report_family=REPORT_FAMILY_INVENTORY,
            classification=self.classification,
            generated_at=self.generated_at,
            generated_by=self.generated_by,
            selected_cluster=self.cluster_scope,
            selected_namespace=self.namespace_scope,
            reporting_period=self.period_label,
            data_cutoff=self.data_cutoff,
            source_label=self.source_label,
        )


@dataclass(frozen=True, slots=True)
class InventoryExportDataset:
    profile: InventoryWorkbookProfile
    context: InventoryExportContext
    rows: tuple[dict[str, Any], ...]

    @property
    def row_count(self) -> int:
        return len(self.rows)

    def record_reference(self, row: Mapping[str, Any], row_number: int) -> str:
        return build_record_reference(
            row,
            self.profile.identity_columns,
            row_number=row_number,
            prefix=self.profile.report_type.upper().replace('-', '_'),
        )


def get_inventory_rows(
    payload: Mapping[str, Any],
    profile: InventoryWorkbookProfile,
) -> list[dict[str, Any]]:
    raw_rows = payload.get(profile.row_source, [])
    if not isinstance(raw_rows, Iterable) or isinstance(raw_rows, (str, bytes, Mapping)):
        return []

    return [dict(row) for row in raw_rows if isinstance(row, Mapping)]


def build_inventory_export_dataset(
    *,
    report_type: str,
    payload: Mapping[str, Any],
    context: InventoryExportContext,
) -> InventoryExportDataset:
    profile = get_inventory_workbook_profile(report_type)
    if context.report_type != report_type:
        raise ValueError('Inventory export context does not match the requested report type.')
    return InventoryExportDataset(
        profile=profile,
        context=context,
        rows=tuple(get_inventory_rows(payload, profile)),
    )


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
    if report.report_type == 'object_storage_inventory':
        return get_report_object_storage_inventory_payload(report)
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
    scope = resolve_report_scope(report)
    if scope is None:
        raise ValueError('The selected report asset no longer exists or cannot be resolved.')

    generated_at = generated_at or datetime.now(UTC)
    object_storage_scope = scope.asset_type == OBJECT_STORAGE_SYSTEM_ASSET_TYPE
    return InventoryExportContext(
        report_id=build_report_reference(report, generated_at=generated_at),
        report_name=report.name,
        report_type=report.report_type,
        generated_at=generated_at,
        generated_by=generated_by_label(report),
        cluster_scope=scope.label,
        namespace_scope='Not Applicable' if object_storage_scope else (report.namespace or 'All Namespaces'),
        period_label=PERIOD_LABELS.get(report.period, report.period or 'Current Inventory Snapshot'),
        data_cutoff=payload.get('data_cutoff') or payload.get('collected_at') or generated_at,
        source_label=(
            str(payload.get('source_label') or 'Object Storage Committed Inventory')
            if object_storage_scope
            else 'Kubernetes Committed Inventory'
        ),
        scope_label=scope.scope_label,
        scope_asset_type=scope.asset_type,
    )


def generated_by_label(report: Report) -> str:
    display_name = str(report.generated_by_display_name_snapshot or '').strip()
    username = str(report.generated_by_username_snapshot or '').strip()
    return display_name or username or 'KAORI'
