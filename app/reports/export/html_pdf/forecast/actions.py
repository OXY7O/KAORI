from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from typing import Any

from app.reports.export.html_pdf.normalization import sanitize_text

from .model import ForecastState, metric, sequence, text


def build_recommendation_plan(state: ForecastState) -> dict[str, Any]:
    rows = provided_recommendations(state.forecast_payload)
    append_memory_recommendation(rows, state.resources)
    append_storage_recommendation(rows, state.resources)
    append_coverage_recommendations(rows, state.resources)
    rows.append(
        {
            'priority': 'P3',
            'title': 'Validate Forecast Freshness',
            'description': (
                'Review materialization time, missing observations, model status, and source ownership '
                'before relying on forecast conclusions.'
            ),
            'owner': 'Observability Owner',
            'target': 'This Month',
            'status': 'Planned',
            'tone': 'info',
        }
    )
    rows = finalize_recommendations(rows)
    p1 = sum(1 for item in rows if item['priority'] == 'P1')
    p2 = sum(1 for item in rows if item['priority'] == 'P2')
    p3 = sum(1 for item in rows if item['priority'] == 'P3')
    primary = rows[0]['title'] if rows else 'Maintain Forecast Monitoring'
    return {
        'metrics': (
            metric('P1 Actions', str(p1), 'Open' if p1 else 'None', 'critical' if p1 else 'normal'),
            metric('P2 Actions', str(p2), 'Open' if p2 else 'None', 'warning' if p2 else 'normal'),
            metric('P3 Actions', str(p3), 'Planned' if p3 else 'None', 'info' if p3 else 'normal'),
            metric('Validation Gates', str(len(rows)), 'Required', 'info'),
        ),
        'rows': tuple(rows),
        'primary_action': primary,
        'validation_criteria': (
            'Confirm source freshness, model status, scope, threshold policy, live metric, accountable '
            'ownership, and approved response before closure.'
        ),
        'assigned_owners': owner_summary(rows),
        'change_control': 'No infrastructure or workload change is authorized by this report alone.',
        'risk_summary': (
            f'{state.critical_count} critical and {state.warning_count} warning forecast exposure(s) are present.'
        ),
    }


def provided_recommendations(forecast_payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    candidates = sequence(
        forecast_payload.get('actionable_recommendations') or forecast_payload.get('recommendation_cards')
    )
    for item in candidates:
        if not isinstance(item, Mapping):
            continue
        title = sanitize_text(item.get('title') or item.get('label'), fallback='Review Forecast Evidence')
        description = sanitize_text(
            item.get('description') or item.get('message'),
            fallback='Validate committed forecast evidence and live state.',
        )
        level = priority(item.get('priority') or item.get('severity'))
        rows.append(
            {
                'priority': level,
                'title': title,
                'description': description,
                'owner': sanitize_text(item.get('owner'), fallback='Platform Operations'),
                'target': target(level),
                'status': 'Open' if level in {'P1', 'P2'} else 'Planned',
                'tone': 'critical' if level == 'P1' else 'warning' if level == 'P2' else 'info',
            }
        )
    return rows


def append_memory_recommendation(
    rows: list[dict[str, Any]],
    resources: Mapping[str, Mapping[str, Any]],
) -> None:
    memory = resources['memory']
    if not memory['available'] or memory['warning_eta'] in {'Not projected', 'Not Available'}:
        return
    rows.append(
        {
            'priority': 'P2',
            'title': 'Review Memory Long-Range Direction',
            'description': (
                f'Validate the projected memory position of {memory["projected_display"]} '
                f'and threshold ETA {memory["warning_eta"]}.'
            ),
            'owner': 'Platform Operations',
            'target': 'Next Week',
            'status': 'Open',
            'tone': 'warning',
        }
    )


def append_storage_recommendation(
    rows: list[dict[str, Any]],
    resources: Mapping[str, Mapping[str, Any]],
) -> None:
    storage = resources['storage']
    if storage['available']:
        return
    rows.append(
        {
            'priority': 'P2',
            'title': 'Restore Storage Forecast Evidence',
            'description': (
                'Commit normalized storage history, projection, threshold ETA, confidence, and freshness evidence.'
            ),
            'owner': 'Platform Operations',
            'target': 'Next Week',
            'status': 'Open',
            'tone': 'warning',
        }
    )


def append_coverage_recommendations(
    rows: list[dict[str, Any]],
    resources: Mapping[str, Mapping[str, Any]],
) -> None:
    for key, title in (('cpu', 'Maintain CPU Forecast Coverage'), ('pods', 'Maintain Pod Forecast Coverage')):
        resource = resources[key]
        rows.append(
            {
                'priority': 'P3',
                'title': title,
                'description': (
                    f'Keep committed {resource["label"]} history and projected endpoints available '
                    'for the selected reporting boundary.'
                    if resource['available']
                    else f'Restore committed {resource["label"]} history and projected endpoint evidence.'
                ),
                'owner': 'Observability Owner' if key == 'cpu' else 'Platform Operations',
                'target': 'This Month',
                'status': 'Current' if resource['available'] else 'Planned',
                'tone': 'normal' if resource['available'] else 'info',
            }
        )


def finalize_recommendations(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = dedupe_recommendations(rows)
    result.sort(key=lambda item: ({'P1': 0, 'P2': 1, 'P3': 2}.get(item['priority'], 9), item['title']))
    result = result[:5]
    for index, item in enumerate(result, start=1):
        item['ref'] = f'R{index}'
    return result


def dedupe_recommendations(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        key = row['title'].strip().casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(row)
    return result


def build_source_rows(state: ForecastState) -> tuple[dict[str, str], ...]:
    rows: list[dict[str, str]] = []
    for item in sequence(state.payload.get('source_evidence')):
        if not isinstance(item, Mapping):
            continue
        rows.append(
            {
                'source': sanitize_text(item.get('source'), fallback='Forecast Evidence'),
                'freshness': sanitize_text(item.get('freshness'), fallback='Not Available'),
                'last_collected': format_datetime(item.get('last_collected')),
            }
        )
    if not rows:
        rows.extend(
            [
                {
                    'source': 'Forecast Materialized Snapshot',
                    'freshness': state.history_window,
                    'last_collected': format_datetime(state.forecast_payload.get('generated_at')),
                },
                {
                    'source': 'Forecast Projection Evidence',
                    'freshness': state.horizon,
                    'last_collected': format_datetime(state.forecast_payload.get('generated_at')),
                },
            ]
        )
    return tuple(rows[:5])


def priority(value: Any) -> str:
    label = text(value, '').lower()
    if label in {'p1', 'critical', 'high'}:
        return 'P1'
    if label in {'p2', 'warning', 'medium', 'review'}:
        return 'P2'
    return 'P3'


def target(priority_label: str) -> str:
    return {'P1': 'This Week', 'P2': 'Next Week', 'P3': 'This Month'}.get(priority_label, 'This Month')


def owner_summary(rows: Sequence[Mapping[str, Any]]) -> str:
    counts: dict[str, int] = {}
    for item in rows:
        owner = sanitize_text(item.get('owner'), fallback='Platform Operations')
        counts[owner] = counts.get(owner, 0) + 1
    return '; '.join(f'{owner}: {count} action(s)' for owner, count in counts.items()) or 'No owner assignment available.'


def format_datetime(value: Any) -> str:
    if isinstance(value, datetime):
        normalized = value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)
        return normalized.strftime('%d %b %Y %H:%M UTC')
    if isinstance(value, date):
        return value.strftime('%d %b %Y')
    rendered = sanitize_text(value, fallback='Not Available')
    try:
        normalized = datetime.fromisoformat(rendered.replace('Z', '+00:00'))
    except (TypeError, ValueError):
        return rendered
    normalized = normalized.astimezone(UTC) if normalized.tzinfo else normalized.replace(tzinfo=UTC)
    return normalized.strftime('%d %b %Y %H:%M UTC')
