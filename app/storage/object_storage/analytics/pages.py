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
        'Review capacity, request health, consumer concentration, forecast, and posture within KAORI.',
        'layout-dashboard',
        'Object Storage Analytics',
    ),
    'capacity': PageDefinition(
        'Object Storage Capacity & Usage',
        'Review capacity, consumption trends, bucket pressure, quota posture, and growth within KAORI.',
        'database',
        'Object Storage Analytics',
    ),
    'performance': PageDefinition(
        'Object Storage Performance',
        'Review S3 request activity, error pressure, queue depth, in-flight demand, and traffic in KAORI.',
        'activity',
        'Object Storage Analytics',
    ),
    'forecast': PageDefinition(
        'Forecast',
        'Project storage growth, utilization, and exhaustion risk from committed metric history in KAORI.',
        'line-chart',
        'Object Storage Analytics',
    ),
    'top_consumers': PageDefinition(
        'Top Consumers',
        'Rank buckets by storage, objects, request activity, errors, and concentration within KAORI.',
        'users',
        'Object Storage Analytics',
    ),
    'alerts': PageDefinition(
        'Alerts & Anomalies',
        'Review active alerts from Alertmanager or Metrics Source with metric-derived operating signals.',
        'triangle-alert',
        'Object Storage Analytics',
    ),
}
