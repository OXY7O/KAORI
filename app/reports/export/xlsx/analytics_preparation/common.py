from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from app.reports.export.xlsx.analytics_schema import (
    AnalyticsColumn,
    AnalyticsMetricSpec,
    AnalyticsMetricValue,
    AnalyticsTableData,
)

GIB = float(1024**3)


def column(
    key: str,
    label: str,
    definition: str,
    *,
    data_type: str = 'text',
    number_format: str | None = None,
    unit: str | None = None,
    width: float = 18.0,
) -> AnalyticsColumn:
    return AnalyticsColumn(
        key=key,
        label=label,
        definition=definition,
        data_type=data_type,  # type: ignore[arg-type]
        number_format=number_format,
        unit=unit,
        width=width,
    )


def mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def sequence(value: Any) -> list[Mapping[str, Any]]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [item for item in value if isinstance(item, Mapping)]
    return []


def number(value: Any) -> float | None:
    if isinstance(value, bool):
        return float(int(value))
    if isinstance(value, (int, float)):
        return float(value)
    if value is None:
        return None
    rendered = str(value).strip().replace(',', '')
    if not rendered or rendered.casefold() in {'n/a', 'na', 'not available', 'unknown', '-'}:
        return None
    token = rendered.split()[0].rstrip('%')
    try:
        return float(token)
    except ValueError:
        return None


def integer(value: Any) -> int:
    parsed = number(value)
    return int(parsed or 0)


def text(value: Any, fallback: str = 'Not Available') -> str:
    if value is None or value == '':
        return fallback
    return str(value)


def first(source: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        value = source.get(key)
        if value not in (None, ''):
            return value
    return default


def percent_from_resource(resource: Mapping[str, Any]) -> float | None:
    direct = first(resource, 'utilization_percent', 'used_percent', 'usage_percent', 'percent')
    direct_number = number(direct)
    if direct_number is not None:
        return direct_number
    headroom = number(resource.get('headroom'))
    if headroom is not None and 0 <= headroom <= 100:
        return 100.0 - headroom
    used = number(resource.get('used'))
    capacity = number(resource.get('capacity'))
    if used is not None and capacity and capacity > 0:
        return used / capacity * 100.0
    return None


def metric_value(spec: AnalyticsMetricSpec, value: Any, *, note: str | None = None) -> AnalyticsMetricValue:
    return AnalyticsMetricValue(
        label=spec.label,
        value=value if value not in (None, '') else 'Not Available',
        number_format=spec.number_format,
        unit=spec.unit,
        note=note,
    )


def table(
    sheet_name: str,
    title: str,
    description: str,
    columns: tuple[AnalyticsColumn, ...],
    rows: Iterable[Mapping[str, Any]],
) -> AnalyticsTableData:
    return AnalyticsTableData(
        sheet_name=sheet_name,
        title=title,
        description=description,
        columns=columns,
        rows=tuple(dict(row) for row in rows),
    )


RESOURCE_COLUMNS = (
    column('resource', 'Resource', 'Resource dimension represented by the committed analytics evidence.', width=24),
    column(
        'current_percent',
        'Current %',
        'Current committed utilization or pressure percentage.',
        data_type='percent',
        number_format='0.0"%"',
        width=16,
    ),
    column(
        'headroom_percent',
        'Headroom %',
        'Remaining capacity percentage when available.',
        data_type='percent',
        number_format='0.0"%"',
        width=16,
    ),
    column('status', 'Status', 'Committed status or posture label.', width=22),
)

TREND_COLUMNS = (
    column(
        'observation',
        'Observation',
        'Committed series position in source order.',
        data_type='integer',
        number_format='#,##0',
        width=14,
    ),
    column('timestamp', 'Timestamp', 'Committed timestamp when supplied by the analytics source.', width=22),
    column(
        'cpu_percent',
        'CPU %',
        'CPU utilization at this observation.',
        data_type='percent',
        number_format='0.0"%"',
        width=14,
    ),
    column(
        'memory_percent',
        'Memory %',
        'Memory utilization at this observation.',
        data_type='percent',
        number_format='0.0"%"',
        width=14,
    ),
    column(
        'pods_percent',
        'Pods %',
        'Pod utilization at this observation.',
        data_type='percent',
        number_format='0.0"%"',
        width=14,
    ),
    column(
        'storage_percent',
        'Storage %',
        'Storage utilization at this observation.',
        data_type='percent',
        number_format='0.0"%"',
        width=14,
    ),
)

FORECAST_POSTURE_COLUMNS = (
    column('resource', 'Resource', 'Forecast resource dimension.', width=20),
    column(
        'current_percent',
        'Current %',
        'Latest committed observed utilization.',
        data_type='percent',
        number_format='0.0"%"',
        width=16,
    ),
    column(
        'projected_percent',
        'Projected %',
        'Committed projected utilization at the configured forecast horizon.',
        data_type='percent',
        number_format='0.0"%"',
        width=16,
    ),
    column(
        'change_pp',
        'Change (pp)',
        'Projected change from the latest observation in percentage points.',
        data_type='number',
        number_format='+0.0;-0.0;0.0',
        unit='pp',
        width=16,
    ),
    column('trend', 'Trend', 'Committed forecast direction.', width=18),
    column('confidence', 'Confidence', 'Committed forecast confidence label.', width=18),
)

RECOMMENDATION_COLUMNS = (
    column('priority', 'Priority', 'Committed recommendation priority.', width=16),
    column('recommendation', 'Recommendation', 'Committed recommendation title or action.', width=38),
    column('evidence', 'Evidence', 'Evidence or description supplied by the analytics source.', width=54),
    column('affected_scope', 'Affected Scope', 'Affected resource or scope when supplied.', width=34),
    column('source', 'Source Rule', 'Source rule or analytics domain that produced the recommendation.', width=24),
)


def recommendation_rows(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    candidates: list[Any] = [
        payload.get('actionable_recommendations'),
        payload.get('recommendations'),
        payload.get('recommendation_cards'),
        mapping(payload.get('forecast_payload')).get('actionable_recommendations'),
        mapping(payload.get('forecast_payload')).get('recommendation_cards'),
    ]
    rows: list[dict[str, Any]] = []
    for candidate in candidates:
        if isinstance(candidate, Mapping):
            candidate = candidate.get('items') or candidate.get('rows') or []
        for item in sequence(candidate):
            title = first(item, 'title', 'recommendation', 'label')
            if not title:
                continue
            rows.append(
                {
                    'priority': first(item, 'priority', 'severity', default='Not Available'),
                    'recommendation': title,
                    'evidence': first(item, 'evidence', 'description', 'detail', default='Not Available'),
                    'affected_scope': first(item, 'affected_scope', 'resource', 'scope', default='Not Available'),
                    'source': first(item, 'source_rule', 'source', 'rule', default='Not Available'),
                }
            )
        if rows:
            break
    return rows


def append_recommendations(tables: list[AnalyticsTableData], payload: Mapping[str, Any]) -> None:
    rows = recommendation_rows(payload)
    if rows:
        tables.append(
            table(
                'Recommendations',
                'Committed Recommendations',
                'Recommendations already owned by KAORI analytics; the XLSX renderer does not create new actions.',
                RECOMMENDATION_COLUMNS,
                rows,
            )
        )


def source_evidence_table(payload: Mapping[str, Any]) -> AnalyticsTableData | None:
    rows = sequence(payload.get('source_evidence'))
    if not rows:
        return None
    normalized = [
        {
            'source': first(row, 'source', 'label', default='Unknown Source'),
            'freshness': first(row, 'freshness', 'status', default='Not Available'),
            'last_collected': first(row, 'last_collected', 'generated_at', default='Not Available'),
        }
        for row in rows
    ]
    return table(
        'Raw Data',
        'Source Evidence',
        'Evidence boundary supplied by the canonical analytics payload.',
        (
            column('source', 'Source', 'Canonical analytics evidence source.', width=38),
            column('freshness', 'Freshness', 'Freshness or readiness evidence.', width=22),
            column('last_collected', 'Last Collected', 'Collection timestamp or evidence boundary.', width=24),
        ),
        normalized,
    )


def leading_percent_readout(metrics: Sequence[AnalyticsMetricValue], noun: str) -> str:
    numeric = [(metric.label, number(metric.value)) for metric in metrics]
    available = [(label, value) for label, value in numeric if value is not None]
    if not available:
        return f'No committed {noun} percentage evidence is available for the selected reporting boundary.'
    label, value = max(available, key=lambda item: item[1])
    return f'{label} is the leading committed {noun} signal at {value:.1f}%. Review the supporting evidence before taking action.'


def clean_unit(value: Any) -> str:
    rendered = str(value or '').strip()
    if rendered.casefold() in {'', 'n/a', 'na', 'not available', 'unknown', '-'}:
        return ''
    return rendered


def display_numeric(value: Any) -> float | None:
    if value in (None, ''):
        return None
    rendered = str(value).strip()
    if not rendered:
        return None
    token = rendered.split()[0].rstrip('%')
    if not token:
        return None
    if token.count(',') > 1 and '.' not in token:
        token = token.replace(',', '')
    elif token.count('.') > 1 and ',' not in token:
        token = token.replace('.', '')
    elif ',' in token and '.' in token:
        if token.rfind(',') > token.rfind('.'):
            token = token.replace('.', '').replace(',', '.')
        else:
            token = token.replace(',', '')
    elif ',' in token:
        whole, fraction = token.rsplit(',', 1)
        token = f'{whole}.{fraction}' if len(fraction) <= 2 else token.replace(',', '')
    try:
        return float(token)
    except ValueError:
        return None


def normalized_consumer_value(
    *,
    resource: str,
    raw_value: float | None,
    display_value: Any,
    unit: str,
) -> float | None:
    displayed = display_numeric(display_value)
    rendered_display = str(display_value or '').strip()
    has_explicit_display_unit = any(character.isalpha() or character == '%' for character in rendered_display)
    if displayed is not None and unit and has_explicit_display_unit:
        return displayed
    if raw_value is None:
        return None
    normalized_unit = unit.casefold()
    if normalized_unit == 'gib' and raw_value > 1024**2:
        return raw_value / GIB
    if normalized_unit == 'mib' and raw_value > 1024:
        return raw_value / float(1024**2)
    if normalized_unit == 'kib' and raw_value > 1024:
        return raw_value / 1024.0
    if resource.casefold() in {'memory', 'pvc'} and raw_value > 1024**2:
        return raw_value / GIB
    return raw_value
