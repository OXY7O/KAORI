from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PageDefinition:
    title: str
    description: str
    icon: str
    eyebrow: str


PAGES: dict[str, PageDefinition] = {
    'overview': PageDefinition(
        'Overview',
        'Review capacity, requests, concentration, forecasts, and posture.',
        'layout-dashboard',
        'Object Storage Analytics',
    ),
    'capacity': PageDefinition(
        'Capacity & Usage',
        'Review capacity, bucket pressure, quotas, trends, and growth.',
        'database',
        'Object Storage Analytics',
    ),
    'performance': PageDefinition(
        'Performance',
        'Review S3 activity, errors, queue depth, demand, and traffic.',
        'activity',
        'Object Storage Analytics',
    ),
    'forecast': PageDefinition(
        'Forecast',
        'Project storage growth and exhaustion risk from committed history.',
        'line-chart',
        'Object Storage Analytics',
    ),
    'top_consumers': PageDefinition(
        'Top Consumers',
        'Rank buckets by storage, objects, requests, and concentration.',
        'users',
        'Object Storage Analytics',
    ),
    'alerts': PageDefinition(
        'Alerts & Anomalies',
        'Review active alerts and metric-derived operating signals.',
        'triangle-alert',
        'Object Storage Analytics',
    ),
}
