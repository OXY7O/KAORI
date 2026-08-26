from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from flask import current_app

from app.models.report import Report
from app.reports.catalog import (
    FORMAT_XLSX,
    REPORT_FAMILY_ANALYTICS,
    REPORT_FAMILY_INVENTORY,
    get_report_type_spec,
    validate_report_instance,
)
from app.reports.export.formatting import format_period
from app.reports.export.html_pdf.collectors import collect_report_payload
from app.reports.export.inventory_common import (
    build_inventory_export_context,
    collect_inventory_payload,
    generated_by_label,
)
from app.reports.export.xlsx.analytics_builder import build_analytics_workbook
from app.reports.export.xlsx.analytics_schema import AnalyticsExportContext
from app.reports.export.xlsx.builder import build_inventory_workbook
from app.reports.export.xlsx.standard import INVENTORY_XLSX_REPORT_TYPES
from app.reports.reference import build_report_reference
from app.reports.scope import OBJECT_STORAGE_SYSTEM_ASSET_TYPE, resolve_report_scope


def render_report_xlsx(report: Report, output_path: Path) -> None:
    """Render a canonical KAORI XLSX artifact for the report's family."""

    validate_report_instance(report)
    if report.output_format != FORMAT_XLSX:
        raise ValueError('The canonical Excel renderer accepts XLSX reports only.')

    family = get_report_type_spec(report.report_type).family
    if family == REPORT_FAMILY_ANALYTICS:
        _render_analytics_xlsx(report, output_path)
        return
    if family == REPORT_FAMILY_INVENTORY:
        render_inventory_xlsx(report, output_path)
        return
    raise ValueError(f'XLSX rendering is not implemented for report family {family!r}.')


def render_inventory_xlsx(report: Report, output_path: Path) -> None:
    """Render the Inventory XLSX family using its committed inventory profile."""

    validate_report_instance(report)
    if report.output_format != FORMAT_XLSX:
        raise ValueError('The canonical Excel renderer accepts XLSX reports only.')
    if report.report_type not in INVENTORY_XLSX_REPORT_TYPES:
        raise ValueError(f'Report type {report.report_type!r} is not an Inventory Excel report.')

    payload = collect_inventory_payload(report)
    error = str(payload.get('_error') or '').strip()
    if error:
        raise RuntimeError(error)

    build_inventory_workbook(
        report_type=report.report_type,
        payload=payload,
        context=build_inventory_export_context(report, payload),
        output_path=output_path,
    )


def _render_analytics_xlsx(report: Report, output_path: Path) -> None:
    """Render Analytics XLSX from the same canonical payload used by PDF/CSV."""

    payload = collect_report_payload(report)
    error = str(payload.get('_error') or '').strip()
    if error:
        raise RuntimeError(error)

    build_analytics_workbook(
        report_type=report.report_type,
        payload=payload,
        context=_build_analytics_export_context(report, payload),
        output_path=output_path,
    )


def _build_analytics_export_context(
    report: Report,
    payload: dict[str, Any],
    *,
    generated_at: datetime | None = None,
) -> AnalyticsExportContext:
    scope = resolve_report_scope(report)
    if scope is None:
        raise ValueError('The selected report asset no longer exists or cannot be resolved.')

    generated_at = generated_at or datetime.now(UTC)
    object_storage_scope = scope.asset_type == OBJECT_STORAGE_SYSTEM_ASSET_TYPE
    return AnalyticsExportContext(
        report_id=build_report_reference(report, generated_at=generated_at),
        report_name=report.name,
        report_type=report.report_type,
        generated_at=generated_at,
        generated_by=generated_by_label(report),
        scope_label=scope.scope_label,
        scope_value=scope.label,
        namespace_scope='Not Applicable' if object_storage_scope else (report.namespace or 'All Namespaces'),
        period_label=format_period(report.period or ''),
        data_cutoff=_analytics_data_cutoff(payload, generated_at),
        classification=str(current_app.config.get('REPORT_PDF_CLASSIFICATION', 'Internal')),
    )


def _analytics_data_cutoff(payload: dict[str, Any], fallback: datetime) -> datetime | str:
    for key in (
        'data_cutoff',
        'last_analyzed_at',
        'collected_at',
        'observed_at',
        'updated_at',
        'generated_at',
    ):
        value = payload.get(key)
        if value not in (None, ''):
            return value
    return fallback
