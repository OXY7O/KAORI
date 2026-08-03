from __future__ import annotations

import csv
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from flask import current_app

from app.models.report import Report
from app.reports.catalog import (
    FORMAT_CSV,
    REPORT_FAMILY_ANALYTICS,
    REPORT_FAMILY_INVENTORY,
    get_report_type_spec,
    validate_report_instance,
)
from app.reports.export.csv.standard import (
    ANALYTICS_HEADERS,
    COMMON_METADATA_HEADERS,
    CSV_DELIMITER,
    CSV_ENCODING,
    CSV_LINE_TERMINATOR,
    CSV_STANDARD,
    protect_spreadsheet_formula,
)
from app.reports.export.html_pdf.builder import build_report_document
from app.reports.export.html_pdf.collectors import collect_report_payload
from app.reports.export.inventory_common import (
    build_inventory_export_context,
    collect_inventory_payload,
    get_inventory_rows,
)
from app.reports.export.xlsx.standard import get_inventory_workbook_profile


@dataclass(frozen=True, slots=True)
class AnalyticsCsvRecord:
    section_number: int
    section: str
    record_type: str
    record_number: int | str
    field: str
    value: Any
    note: str = ''
    status: str = ''
    tone: str = ''


def render_report_csv(report: Report, output_path: Path) -> None:
    validate_report_instance(report)
    if report.output_format != FORMAT_CSV:
        raise ValueError('The canonical CSV renderer accepts CSV reports only.')
    family = get_report_type_spec(report.report_type).family

    if family == REPORT_FAMILY_ANALYTICS:
        _render_analytics_csv(report, output_path)
        return
    if family == REPORT_FAMILY_INVENTORY:
        _render_inventory_csv(report, output_path)
        return
    raise ValueError(f'CSV rendering is not implemented for report family {family!r}.')


def _render_analytics_csv(report: Report, output_path: Path) -> None:
    payload = collect_report_payload(report)
    error = str(payload.get('_error') or '').strip()
    if error:
        raise RuntimeError(error)

    document = build_report_document(
        report,
        payload,
        classification=str(current_app.config.get('REPORT_PDF_CLASSIFICATION', 'Internal')),
        retention_days=int(current_app.config.get('REPORT_RETENTION_DAYS', 90) or 90),
    )
    metadata = {
        'report_standard': CSV_STANDARD,
        'report_id': document.report_id,
        'report_name': document.report_name,
        'report_type': report.report_type,
        'report_family': REPORT_FAMILY_ANALYTICS,
        'cluster': document.cluster_scope,
        'namespace': document.namespace_scope,
        'period': document.period_label,
        'data_cutoff': document.data_cutoff,
    }

    rows: list[dict[str, Any]] = []
    for index, metric in enumerate(document.source_metrics, start=1):
        rows.append(
            _analytics_row(
                metadata,
                AnalyticsCsvRecord(
                    section_number=0,
                    section='Source Evidence',
                    record_type='source_metric',
                    record_number=index,
                    field=metric.label,
                    value=metric.value,
                    note=metric.note,
                    tone=metric.tone,
                ),
            )
        )

    for section in document.sections:
        rows.append(
            _analytics_row(
                metadata,
                AnalyticsCsvRecord(
                    section_number=section.number,
                    section=section.title,
                    record_type='section_status',
                    record_number=1,
                    field='status',
                    value=section.status_label,
                    note=section.description,
                    status=section.status_label,
                    tone=section.status_tone,
                ),
            )
        )
        for index, metric in enumerate(section.metrics, start=1):
            rows.append(
                _analytics_row(
                    metadata,
                    AnalyticsCsvRecord(
                        section_number=section.number,
                        section=section.title,
                        record_type='metric',
                        record_number=index,
                        field=metric.label,
                        value=metric.value,
                        note=metric.note,
                        tone=metric.tone,
                    ),
                )
            )
        for index, finding in enumerate(section.findings, start=1):
            rows.append(
                _analytics_row(
                    metadata,
                    AnalyticsCsvRecord(
                        section_number=section.number,
                        section=section.title,
                        record_type='finding',
                        record_number=index,
                        field=finding.title,
                        value=finding.description,
                        tone=finding.tone,
                    ),
                )
            )
        for table_index, table in enumerate(section.tables, start=1):
            for row_index, values in enumerate(table.rows, start=1):
                for column, value in zip(table.columns, values, strict=False):
                    rows.append(
                        _analytics_row(
                            metadata,
                            AnalyticsCsvRecord(
                                section_number=section.number,
                                section=section.title,
                                record_type=f'table:{table.title}',
                                record_number=f'{table_index}.{row_index}',
                                field=column,
                                value=value,
                                note=table.note,
                            ),
                        )
                    )
        if section.note:
            rows.append(
                _analytics_row(
                    metadata,
                    AnalyticsCsvRecord(
                        section_number=section.number,
                        section=section.title,
                        record_type='section_note',
                        record_number=1,
                        field='note',
                        value=section.note,
                    ),
                )
            )

    for index, note in enumerate(document.methodology_notes, start=1):
        rows.append(
            _analytics_row(
                metadata,
                AnalyticsCsvRecord(
                    section_number=len(document.sections) + 1,
                    section='Methodology',
                    record_type='methodology_note',
                    record_number=index,
                    field='note',
                    value=note,
                ),
            )
        )

    _write_dict_rows(output_path, ANALYTICS_HEADERS, rows)


def _render_inventory_csv(report: Report, output_path: Path) -> None:
    payload = collect_inventory_payload(report)
    error = str(payload.get('_error') or '').strip()
    if error:
        raise RuntimeError(error)

    profile = get_inventory_workbook_profile(report.report_type)
    context = build_inventory_export_context(report, payload)
    rows = get_inventory_rows(payload, profile)
    headers = (
        *COMMON_METADATA_HEADERS,
        'row_number',
        *(column.key for column in profile.columns),
    )
    metadata = {
        'report_standard': CSV_STANDARD,
        'report_id': context.report_id,
        'report_name': context.report_name,
        'report_type': report.report_type,
        'report_family': REPORT_FAMILY_INVENTORY,
        'cluster': context.cluster_scope,
        'namespace': context.namespace_scope,
        'period': context.period_label,
        'data_cutoff': _serialize_value(context.data_cutoff),
    }

    exported_rows: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        exported = {**metadata, 'row_number': index}
        for column in profile.columns:
            exported[column.key] = _serialize_value(row.get(column.key))
        exported_rows.append(exported)

    _write_dict_rows(output_path, headers, exported_rows)


def _analytics_row(
    metadata: dict[str, Any],
    record: AnalyticsCsvRecord,
) -> dict[str, Any]:
    return {
        **metadata,
        'section_number': record.section_number,
        'section': record.section,
        'record_type': record.record_type,
        'record_number': record.record_number,
        'field': record.field,
        'value': _serialize_value(record.value),
        'note': record.note,
        'status': record.status,
        'tone': record.tone,
    }


def _write_dict_rows(
    output_path: Path,
    headers: Iterable[str],
    rows: Iterable[dict[str, Any]],
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(headers)
    with output_path.open('w', encoding=CSV_ENCODING, newline='') as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
            delimiter=CSV_DELIMITER,
            lineterminator=CSV_LINE_TERMINATOR,
            extrasaction='ignore',
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    key: protect_spreadsheet_formula(_serialize_value(row.get(key)))
                    for key in fieldnames
                }
            )


def _serialize_value(value: Any) -> str:
    if value is None:
        return ''
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, bool):
        return 'Yes' if value else 'No'
    if isinstance(value, (list, tuple, set)):
        return '; '.join(_serialize_value(item) for item in value)
    if isinstance(value, dict):
        return '; '.join(f'{key}={_serialize_value(item)}' for key, item in value.items())
    return str(value)
