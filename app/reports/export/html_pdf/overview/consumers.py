from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from .common import display_percent, number, text


def measurement_number(value: Any) -> float:
    rendered = str(value or '')
    match = re.search(r'-?\d+(?:[.,]\d+)?', rendered)
    if not match:
        return 0.0
    return number(match.group(0).replace(',', '.'))


def consumer_rows(items: Sequence[Any], resource_label: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(items[:8], start=1):
        if not isinstance(item, Mapping):
            continue
        name = text(item.get('name') or item.get('workload') or item.get('pod'), 'Unnamed Resource')
        namespace = text(item.get('namespace'), 'Cluster Scoped')
        display = text(item.get('display_value') or item.get('value'), 'Not Available')
        share_percent = None
        if item.get('percent') is not None:
            share_percent = max(0.0, min(number(item.get('percent')), 100.0))
        raw_value = measurement_number(display)
        if resource_label.lower() == 'memory' and raw_value > 1024**2:
            raw_value = raw_value / 1024**3
            display = f'{raw_value:.2f} GiB'
        rows.append(
            {
                'rank': index,
                'marker': str(index),
                'name': name,
                'namespace': namespace,
                'resource': resource_label,
                'value': display,
                'raw_value': raw_value,
                'percent': share_percent if share_percent is not None else 0.0,
                'bar_percent': 0.0,
                'status': 'Review' if share_percent is not None and share_percent >= 10 else 'Observed',
                'tone': 'warning' if share_percent is not None and share_percent >= 10 else 'info',
            }
        )
    return rows


def normalize_consumer_bars(rows: Sequence[dict[str, Any]]) -> None:
    maximum = max((number(item.get('raw_value')) for item in rows), default=0.0)
    source_key = 'raw_value'
    if maximum <= 0:
        maximum = max((number(item.get('percent')) for item in rows), default=0.0)
        source_key = 'percent'
    for item in rows:
        value = number(item.get(source_key))
        item['bar_percent'] = max(
            4.0 if value > 0 else 0.0,
            min(100.0, value / maximum * 100.0 if maximum else 0.0),
        )


def consumer_mix(items: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    total = sum(number(item.get('percent')) for item in items) or 1.0
    segments = []
    cursor = 0.0
    palette = ('#5b21b6', '#7c3aed', '#2563eb', '#0d9488', '#94a3b8', '#f59e0b')
    for index, item in enumerate(items[:6]):
        share = (number(item.get('percent')) / total) * 100.0
        segments.append(
            {
                'marker': text(item.get('marker'), str(index + 1)),
                'name': text(item.get('name')),
                'namespace': text(item.get('namespace')),
                'percent': share,
                'start': cursor,
                'end': cursor + share,
                'color': palette[index % len(palette)],
            }
        )
        cursor += share
    return {'segments': segments, 'total': total}


def consumer_insight(groups: Mapping[str, Sequence[Mapping[str, Any]]]) -> str:
    memory = list(groups.get('memory') or [])
    if memory:
        top = memory[:2]
        refs = ' and '.join(f'M{index}' for index in range(1, len(top) + 1))
        share = sum(number(item.get('percent')) for item in top)
        return (
            f'{refs} account for {display_percent(share)} of the displayed memory consumer signal. '
            'Complete identities are listed in the reference register.'
        )
    cpu = list(groups.get('cpu') or [])
    if cpu:
        return (
            'C1 is the highest displayed CPU consumer. Complete identity and namespace evidence '
            'are listed in the reference register.'
        )
    return 'Top-consumer evidence is not available for the selected reporting boundary.'


def observation_scope(
    source_rows: Sequence[Mapping[str, Any]],
    period_label: str,
) -> list[dict[str, Any]]:
    result = [
        {
            'label': text(row.get('label')),
            'value': text(row.get('source_short') or row.get('source')),
        }
        for row in source_rows[:3]
    ]
    result.append({'label': 'Time Window', 'value': period_label})
    return result
