from __future__ import annotations

import csv
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
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
    INVENTORY_CONTROL_HEADERS,
    protect_spreadsheet_formula,
)
from app.reports.export.html_pdf.builder import build_report_document
from app.reports.export.html_pdf.collectors import collect_report_payload
from app.reports.export.html_pdf.document import ReportDocument
from app.reports.export.inventory_common import (
    build_inventory_export_context,
    build_inventory_export_dataset,
    collect_inventory_payload,
)
from app.reports.export.tabular import (
    TabularExportMetadata,
    serialize_tabular_value,
    tabular_value_type,
)


@dataclass(frozen=True, slots=True)
class AnalyticsCsvRecord:
    section_order: int
    section_key: str
    section_title: str
    dataset: str
    record_type: str
    record_reference: str
    record_order: int
    field_order: int
    field: str
    value: Any
    status: str = ''
    tone: str = ''
    note: str = ''


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
    metadata = _analytics_metadata(report, document).as_dict()
    rows = [_analytics_row(metadata, record) for record in build_analytics_csv_records(document)]
    _write_dict_rows(output_path, ANALYTICS_HEADERS, rows)


def build_analytics_csv_records(document: ReportDocument) -> list[AnalyticsCsvRecord]:
    """Flatten a ReportDocument into a stable long-form analytical dataset."""

    records: list[AnalyticsCsvRecord] = []
    for index, metric in enumerate(document.source_metrics, start=1):
        records.append(
            AnalyticsCsvRecord(
                section_order=0,
                section_key='source_evidence',
                section_title='Source Evidence',
                dataset='source_metrics',
                record_type='metric',
                record_reference=f'SRC-M{index:02d}',
                record_order=index,
                field_order=1,
                field=metric.label,
                value=metric.value,
                tone=metric.tone,
                note=metric.note,
            )
        )

    for section in document.sections:
        section_reference = f'S{section.number:02d}'
        records.append(
            AnalyticsCsvRecord(
                section_order=section.number,
                section_key=section.key,
                section_title=section.title,
                dataset='section',
                record_type='section_status',
                record_reference=section_reference,
                record_order=0,
                field_order=1,
                field='status',
                value=section.status_label,
                status=section.status_label,
                tone=section.status_tone,
                note=section.description,
            )
        )

        for index, metric in enumerate(section.metrics, start=1):
            records.append(
                AnalyticsCsvRecord(
                    section_order=section.number,
                    section_key=section.key,
                    section_title=section.title,
                    dataset='metrics',
                    record_type='metric',
                    record_reference=f'{section_reference}-M{index:02d}',
                    record_order=index,
                    field_order=1,
                    field=metric.label,
                    value=metric.value,
                    tone=metric.tone,
                    note=metric.note,
                )
            )

        for index, finding in enumerate(section.findings, start=1):
            reference = f'{section_reference}-F{index:02d}'
            records.extend(
                (
                    AnalyticsCsvRecord(
                        section_order=section.number,
                        section_key=section.key,
                        section_title=section.title,
                        dataset='findings',
                        record_type='finding',
                        record_reference=reference,
                        record_order=index,
                        field_order=1,
                        field='title',
                        value=finding.title,
                        tone=finding.tone,
                    ),
                    AnalyticsCsvRecord(
                        section_order=section.number,
                        section_key=section.key,
                        section_title=section.title,
                        dataset='findings',
                        record_type='finding',
                        record_reference=reference,
                        record_order=index,
                        field_order=2,
                        field='description',
                        value=finding.description,
                        tone=finding.tone,
                    ),
                )
            )

        for table_index, table in enumerate(section.tables, start=1):
            dataset = _dataset_key(table.title, fallback=f'table_{table_index:02d}')
            for row_index, values in enumerate(table.rows, start=1):
                record_reference = _table_record_reference(
                    values,
                    table.columns,
                    fallback=f'{section_reference}-T{table_index:02d}-R{row_index:04d}',
                )
                for field_order, (column, value) in enumerate(
                    zip(table.columns, values, strict=False),
                    start=1,
                ):
                    records.append(
                        AnalyticsCsvRecord(
                            section_order=section.number,
                            section_key=section.key,
                            section_title=section.title,
                            dataset=dataset,
                            record_type='table_row',
                            record_reference=record_reference,
                            record_order=row_index,
                            field_order=field_order,
                            field=column,
                            value=value,
                            note=table.note,
                        )
                    )

        if section.note:
            records.append(
                AnalyticsCsvRecord(
                    section_order=section.number,
                    section_key=section.key,
                    section_title=section.title,
                    dataset='section_notes',
                    record_type='note',
                    record_reference=f'{section_reference}-N01',
                    record_order=1,
                    field_order=1,
                    field='note',
                    value=section.note,
                )
            )

    methodology_order = len(document.sections) + 1
    for index, note in enumerate(document.methodology_notes, start=1):
        records.append(
            AnalyticsCsvRecord(
                section_order=methodology_order,
                section_key='methodology',
                section_title='Methodology',
                dataset='methodology_notes',
                record_type='note',
                record_reference=f'MET-N{index:02d}',
                record_order=index,
                field_order=1,
                field='note',
                value=note,
            )
        )

    return records


def _render_inventory_csv(report: Report, output_path: Path) -> None:
    payload = collect_inventory_payload(report)
    error = str(payload.get('_error') or '').strip()
    if error:
        raise RuntimeError(error)

    context = build_inventory_export_context(report, payload)
    dataset = build_inventory_export_dataset(
        report_type=report.report_type,
        payload=payload,
        context=context,
    )
    headers = (
        *COMMON_METADATA_HEADERS,
        *INVENTORY_CONTROL_HEADERS,
        *(column.key for column in dataset.profile.columns),
    )
    metadata = context.tabular_metadata(format_standard=CSV_STANDARD).as_dict()

    exported_rows: list[dict[str, Any]] = []
    for index, row in enumerate(dataset.rows, start=1):
        exported: dict[str, Any] = {
            **metadata,
            'record_type': 'inventory_asset',
            'record_reference': dataset.record_reference(row, index),
            'row_number': index,
        }
        for column in dataset.profile.columns:
            exported[column.key] = row.get(column.key)
        exported_rows.append(exported)

    if not exported_rows:
        exported_rows.append(
            {
                **metadata,
                'record_type': 'no_data',
                'record_reference': 'NO-DATA',
                'row_number': '',
            }
        )

    _write_dict_rows(output_path, headers, exported_rows)


def _analytics_metadata(report: Report, document: ReportDocument) -> TabularExportMetadata:
    return TabularExportMetadata(
        format_standard=CSV_STANDARD,
        document_reference=document.report_id,
        report_name=document.report_name,
        report_type=report.report_type,
        report_type_label=document.report_type_label,
        report_family=REPORT_FAMILY_ANALYTICS,
        classification=document.classification,
        generated_at=_iso_datetime_text(document.generated_at),
        generated_by=document.generated_by,
        selected_cluster=document.cluster_scope,
        selected_namespace=document.namespace_scope,
        reporting_period=document.period_label,
        data_cutoff=_iso_datetime_text(document.data_cutoff),
        source_label=document.source_kind_label,
    )



def _iso_datetime_text(value: str) -> str:
    text = str(value or '').strip()
    for pattern in ('%d %b %Y %H:%M UTC', '%Y-%m-%d %H:%M UTC', '%Y-%m-%d %H:%M:%S UTC'):
        try:
            parsed = datetime.strptime(text, pattern).replace(tzinfo=UTC)
        except ValueError:
            continue
        return parsed.isoformat()
    return text


def _analytics_row(
    metadata: dict[str, Any],
    record: AnalyticsCsvRecord,
) -> dict[str, Any]:
    return {
        **metadata,
        'section_order': record.section_order,
        'section_key': record.section_key,
        'section_title': record.section_title,
        'dataset': record.dataset,
        'record_type': record.record_type,
        'record_reference': record.record_reference,
        'record_order': record.record_order,
        'field_order': record.field_order,
        'field': record.field,
        'value': record.value,
        'value_type': tabular_value_type(record.value),
        'status': record.status,
        'tone': record.tone,
        'note': record.note,
    }


def _table_record_reference(
    values: tuple[str, ...],
    columns: tuple[str, ...],
    *,
    fallback: str,
) -> str:
    if values and columns:
        first_column = str(columns[0]).strip().lower().rstrip('.')
        first_value = str(values[0]).strip()
        if first_value and first_column in {'ref', 'reference', 'id', 'code'}:
            return first_value
    return fallback


def _dataset_key(value: str, *, fallback: str) -> str:
    normalized = ''.join(character.lower() if character.isalnum() else '_' for character in value)
    compact = '_'.join(part for part in normalized.split('_') if part)
    return compact or fallback


def _write_dict_rows(
    output_path: Path,
    headers: Iterable[str],
    rows: Iterable[Mapping[str, Any]],
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
            quoting=csv.QUOTE_MINIMAL,
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    key: protect_spreadsheet_formula(serialize_tabular_value(row.get(key)))
                    for key in fieldnames
                }
            )
