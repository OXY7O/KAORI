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
        'Analytics Overview',
        'Review consolidated capacity, request health, consumer concentration, forecast, and evidence posture.',
        'layout-dashboard',
        'Object Storage Analytics',
    ),
    'capacity': PageDefinition(
        'Object Storage Capacity & Usage',
        'Review usable capacity, consumption trends, bucket pressure, quota posture, and growth across the selected system.',
        'database',
        'Object Storage Analytics',
    ),
    'performance': PageDefinition(
        'Object Storage Performance',
        'Review S3 request activity, error pressure, queue depth, in-flight demand, and traffic across the selected system.',
        'activity',
        'Object Storage Analytics',
    ),
    'forecast': PageDefinition(
        'Forecast',
        'Project storage growth, future utilization, and capacity exhaustion from committed operational metric history.',
        'line-chart',
        'Object Storage Analytics',
    ),
    'top_consumers': PageDefinition(
        'Top Consumers',
        'Rank buckets by storage consumption, objects, request activity, error pressure, and concentration within the selected system.',
        'users',
        'Object Storage Analytics',
    ),
    'alerts': PageDefinition(
        'Alerts & Anomalies',
        'Review active alerts from Alertmanager or Metrics Source alongside metric-derived operating signals.',
        'triangle-alert',
        'Object Storage Analytics',
    ),
}
