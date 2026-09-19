from __future__ import annotations

import math
import re
from collections.abc import Iterable, Mapping, Sequence
from datetime import date, datetime
from typing import Any

from app.reports.export.html_pdf.document import ReportFinding, ReportMetric, ReportTable

_INTERNAL_KEY_PATTERN = re.compile(
    r'(?:traceback|exception|stack|password|secret|token|authorization|credential|kubeconfig)',
    re.IGNORECASE,
)
_URL_PATTERN = re.compile(r'https?://[^\s<>()]+', re.IGNORECASE)
_EXCEPTION_PATTERN = re.compile(
    r'\b(?:[A-Za-z]+Error|[A-Za-z]+Exception|HTTPSConnectionPool|HTTPConnectionPool|Max retries exceeded)\b',
    re.IGNORECASE,
)
_WHITESPACE_PATTERN = re.compile(r'\s+')

_COMMON_COLUMN_ORDER = (
    'rank',
    'severity',
    'status',
    'namespace',
    'name',
    'workload',
    'pod',
    'node',
    'resource',
    'resource_type',
    'label',
    'value',
    'current_display',
    'projected_display',
    'usage_percent',
    'utilization',
    'risk',
    'recommendation',
    'description',
)


def humanize_key(value: str) -> str:
    normalized = value.replace('-', ' ').replace('_', ' ').strip()
    return ' '.join(part.capitalize() for part in normalized.split()) or 'Value'


def sanitize_text(value: Any, *, fallback: str = '-') -> str:
    if value is None:
        return fallback

    if isinstance(value, bool):
        return 'Yes' if value else 'No'

    if isinstance(value, datetime):
        return value.strftime('%d %b %Y %H:%M %Z').strip()

    if isinstance(value, date):
        return value.strftime('%d %b %Y')

    if isinstance(value, float):
        if not math.isfinite(value):
            return fallback
        if value.is_integer():
            return f'{int(value):,}'
        return f'{value:,.2f}'.rstrip('0').rstrip('.')

    if isinstance(value, int):
        return f'{value:,}'

    if isinstance(value, Mapping):
        label = value.get('label') or value.get('status_label') or value.get('name')
        nested_value = value.get('value')
        if label is not None and nested_value is not None:
            return f'{sanitize_text(label)}: {sanitize_text(nested_value)}'
        if label is not None:
            return sanitize_text(label)
        return fallback

    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        rendered = [sanitize_text(item, fallback='') for item in value[:6]]
        return ', '.join(item for item in rendered if item) or fallback

    text = str(value)
    # PDF-safe punctuation normalization: keep technical identifiers and prose
    # renderable across WeasyPrint/PDF viewers without broken-glyph artifacts.
    text = (
        text.replace('\u00a0', ' ')
        .replace('\u00ad', '')
        .replace('\u2010', '-')
        .replace('\u2011', '-')
        .replace('\u2012', '-')
        .replace('\u2013', '-')
        .replace('\u2212', '-')
    )
    text = _WHITESPACE_PATTERN.sub(' ', text).strip()
    return text or fallback


def sanitize_error_message(value: Any) -> str:
    text = sanitize_text(value, fallback='')
    if not text:
        return 'The requested data was unavailable when KAORI generated this report.'

    lowered = text.lower()
    if any(token in lowered for token in ('timeout', 'timed out', 'connection refused', 'max retries')):
        return 'The data source was temporarily unreachable. KAORI excluded unavailable data from this report.'
    if any(token in lowered for token in ('401', '403', 'unauthorized', 'forbidden')):
        return 'The data source rejected the current integration credentials. Review integration readiness before regenerating.'
    if any(token in lowered for token in ('certificate', 'ssl', 'tls')):
        return (
            'The data source could not be reached because its TLS trust or certificate configuration requires review.'
        )

    text = _URL_PATTERN.sub('[endpoint hidden]', text)
    text = _EXCEPTION_PATTERN.sub('integration error', text)
    text = text[:280].rstrip(' .,:;-')
    return text or 'The requested data was unavailable when KAORI generated this report.'


def tone_from_value(value: Any) -> str:
    text = sanitize_text(value, fallback='').lower()
    if any(token in text for token in ('critical', 'failed', 'expired', 'unhealthy', 'error', 'not ready')):
        return 'critical'
    if any(token in text for token in ('warning', 'degraded', 'stale', 'review', 'pending', 'unknown')):
        return 'warning'
    if any(token in text for token in ('healthy', 'ready', 'normal', 'connected', 'current', 'success')):
        return 'normal'
    if any(token in text for token in ('info', 'active', 'enabled', 'configured')):
        return 'info'
    return 'neutral'


def is_scalar(value: Any) -> bool:
    return value is None or isinstance(value, (str, int, float, bool, date, datetime))


def should_include_key(key: str) -> bool:
    if key.startswith('_'):
        return False
    return not bool(_INTERNAL_KEY_PATTERN.search(key))


def resolve_path(payload: Mapping[str, Any], path: str) -> Any:
    current: Any = payload
    for part in path.split('.'):
        if not isinstance(current, Mapping) or part not in current:
            return None
        current = current[part]
    return current


def find_first_path(payload: Mapping[str, Any], paths: Iterable[str]) -> Any:
    for path in paths:
        value = resolve_path(payload, path)
        if value not in (None, '', [], {}):
            return value
    return None


def metrics_from_mapping(
    value: Mapping[str, Any],
    *,
    limit: int = 6,
    excluded_keys: set[str] | None = None,
) -> tuple[ReportMetric, ...]:
    excluded = excluded_keys or set()
    metrics: list[ReportMetric] = []

    for key, item in value.items():
        key_text = str(key)
        if key_text in excluded or not should_include_key(key_text):
            continue

        if is_scalar(item):
            rendered = sanitize_text(item)
            metrics.append(
                ReportMetric(
                    label=humanize_key(key_text),
                    value=rendered,
                    tone=tone_from_value(item),
                )
            )
        elif isinstance(item, Mapping):
            label = item.get('label') or item.get('title') or humanize_key(key_text)
            metric_value = (
                item.get('value')
                if 'value' in item
                else item.get('percent', item.get('status_label', item.get('status')))
            )
            if metric_value is None:
                continue
            note = item.get('caption') or item.get('subtitle') or item.get('description') or ''
            metrics.append(
                ReportMetric(
                    label=sanitize_text(label),
                    value=sanitize_text(metric_value),
                    note=sanitize_text(note, fallback='')[:140],
                    tone=tone_from_value(item.get('tone') or item.get('status') or metric_value),
                )
            )

        if len(metrics) >= limit:
            break

    return tuple(metrics)


def _finding_items(value: Any) -> list[Any]:
    if isinstance(value, Mapping):
        items: list[Any] = []
        for key, item in value.items():
            if not should_include_key(str(key)):
                continue
            if isinstance(item, Mapping):
                title = item.get('title') or item.get('label') or humanize_key(str(key))
                description = item.get('description') or item.get('message') or item.get('recommendation') or ''
                if description or item.get('severity') or item.get('status'):
                    items.append(
                        {
                            'title': title,
                            'description': description,
                            'tone': item.get('tone') or item.get('severity') or item.get('status'),
                        }
                    )
            elif is_scalar(item) and isinstance(item, str) and len(item) > 24:
                items.append({'title': humanize_key(str(key)), 'description': item})
        return items
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return list(value)
    return [value]


def _finding_fields(item: Any, index: int) -> tuple[Any, Any, Any]:
    if isinstance(item, Mapping):
        title = item.get('title') or item.get('label') or item.get('name') or f'Finding {index}'
        description = (
            item.get('description')
            or item.get('message')
            or item.get('summary')
            or item.get('recommendation')
            or item.get('reason')
            or ''
        )
        tone_value = item.get('tone') or item.get('severity') or item.get('priority') or item.get('status')
        return title, description, tone_value
    return f'Finding {index}', item, item


def findings_from_value(value: Any, *, limit: int = 8) -> tuple[ReportFinding, ...]:
    findings: list[ReportFinding] = []
    for index, item in enumerate(_finding_items(value), start=1):
        title, description, tone_value = _finding_fields(item, index)
        title_text = sanitize_text(title, fallback=f'Finding {index}')
        description_text = sanitize_text(description, fallback='')
        if not description_text and title_text == sanitize_text(item, fallback=''):
            description_text = ''

        findings.append(
            ReportFinding(
                title=title_text[:160],
                description=description_text[:600],
                tone=tone_from_value(tone_value),
            )
        )
        if len(findings) >= limit:
            break

    return tuple(findings)


def _ordered_columns(rows: Sequence[Mapping[str, Any]], *, max_columns: int) -> list[str]:
    discovered: list[str] = []
    for preferred in _COMMON_COLUMN_ORDER:
        if any(preferred in row for row in rows):
            discovered.append(preferred)
    for row in rows:
        for key in row:
            key_text = str(key)
            if key_text in discovered or not should_include_key(key_text):
                continue
            if any(is_scalar(candidate.get(key_text)) for candidate in rows):
                discovered.append(key_text)
            if len(discovered) >= max_columns:
                return discovered
    return discovered[:max_columns]


def table_from_rows(
    title: str,
    rows: Sequence[Any],
    *,
    max_rows: int = 25,
    max_columns: int = 7,
    note: str = '',
) -> ReportTable | None:
    mapping_rows = [row for row in rows if isinstance(row, Mapping)]
    if not mapping_rows:
        return None

    columns = _ordered_columns(mapping_rows, max_columns=max_columns)
    if not columns:
        return None

    rendered_rows: list[tuple[str, ...]] = []
    for row in mapping_rows[:max_rows]:
        rendered_rows.append(tuple(sanitize_text(row.get(column))[:240] for column in columns))

    if len(mapping_rows) > max_rows:
        overflow_note = f'Showing the first {max_rows} of {len(mapping_rows)} rows.'
        note = f'{note} {overflow_note}'.strip()

    return ReportTable(
        title=title,
        columns=tuple(humanize_key(column) for column in columns),
        rows=tuple(rendered_rows),
        note=note,
    )


def tables_from_value(title: str, value: Any) -> tuple[ReportTable, ...]:
    tables: list[ReportTable] = []

    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        table = table_from_rows(title, value)
        if table is not None:
            tables.append(table)
        return tuple(tables)

    if not isinstance(value, Mapping):
        return ()

    direct_rows = value.get('rows')
    if isinstance(direct_rows, Sequence) and not isinstance(direct_rows, (str, bytes, bytearray)):
        table = table_from_rows(title, direct_rows)
        if table is not None:
            tables.append(table)

    for key, nested in value.items():
        key_text = str(key)
        if not should_include_key(key_text) or key_text == 'rows':
            continue
        if isinstance(nested, Sequence) and not isinstance(nested, (str, bytes, bytearray)):
            table = table_from_rows(humanize_key(key_text), nested)
            if table is not None:
                tables.append(table)
        elif isinstance(nested, Mapping):
            nested_rows = nested.get('rows')
            if isinstance(nested_rows, Sequence) and not isinstance(nested_rows, (str, bytes, bytearray)):
                table = table_from_rows(humanize_key(key_text), nested_rows)
                if table is not None:
                    tables.append(table)

        if len(tables) >= 3:
            break

    if not tables:
        scalar_rows = [
            (humanize_key(str(key)), sanitize_text(item))
            for key, item in value.items()
            if should_include_key(str(key)) and is_scalar(item)
        ]
        if scalar_rows:
            tables.append(
                ReportTable(
                    title=title,
                    columns=('Metric', 'Value'),
                    rows=tuple(scalar_rows[:30]),
                )
            )

    return tuple(tables)
