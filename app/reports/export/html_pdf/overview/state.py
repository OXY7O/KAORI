from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from .actions import decision_items, priority_findings, recommendations
from .alerts import alerts, anomalies
from .common import mapping
from .context import OverviewContext
from .forecast import forecast_series
from .freshness import source_rows
from .inventory import build_inventory
from .resources import (
    executive_metric,
    metric_evidence_state,
    reconcile_resource_metrics,
    resource_metrics,
    storage_headroom_metric,
)


@dataclass(frozen=True, slots=True)
class OverviewState:
    snapshot_summary: Mapping[str, Any]
    resource_snapshot: Mapping[str, Any]
    capacity_snapshot: Mapping[str, Any]
    storage_snapshot: Mapping[str, Any]
    workload_snapshot: Mapping[str, Any]
    forecast_snapshot: Mapping[str, Any]
    alerts_snapshot: Mapping[str, Any]
    health_summary: Mapping[str, Any]
    actionable: Mapping[str, Any]
    top_consumers: Mapping[str, Any]
    alert_detail: Mapping[str, Any]
    reporting_summary: Mapping[str, Any]
    inventory_snapshot: Mapping[str, Any]
    freshness: Mapping[str, Any]
    resource_metrics: Mapping[str, Mapping[str, Any]]
    forecast_series: Sequence[Mapping[str, Any]]
    recommendation_items: Sequence[Mapping[str, Any]]
    alert_items: Sequence[Mapping[str, Any]]
    anomaly_items: Sequence[Mapping[str, Any]]
    inventory: Mapping[str, Any]
    source_rows: Sequence[Mapping[str, Any]]
    priority_findings: Sequence[Mapping[str, Any]]
    decisions: Sequence[Mapping[str, Any]]
    executive_metrics: Sequence[Mapping[str, Any]]


def build_overview_state(context: OverviewContext) -> OverviewState:
    payload = context.payload
    snapshots = _snapshot_groups(payload)
    metrics = resource_metrics(
        snapshots['resource_snapshot'],
        evidence_state=metric_evidence_state(payload, snapshots['snapshot_summary']),
    )
    series = forecast_series(snapshots['forecast_snapshot'])
    metrics = reconcile_resource_metrics(
        metrics,
        forecast_series=series,
        storage_snapshot=snapshots['storage_snapshot'],
        capacity_snapshot=snapshots['capacity_snapshot'],
        inventory_snapshot=snapshots['inventory_snapshot'],
    )
    recommendation_items = recommendations(snapshots['actionable'], payload)
    alert_items = alerts(snapshots['alert_detail'])
    anomaly_items = anomalies(snapshots['alert_detail'])
    inventory = build_inventory(
        snapshots['inventory_snapshot'],
        getattr(context.report, 'cluster_id', None),
    )
    source_rows_value = source_rows(
        payload=payload,
        inventory=inventory,
        freshness=snapshots['freshness'],
        alert_detail=snapshots['alert_detail'],
    )
    findings = priority_findings(
        resource_metrics=metrics,
        storage_snapshot=snapshots['storage_snapshot'],
        workload_snapshot=snapshots['workload_snapshot'],
        forecast_snapshot=snapshots['forecast_snapshot'],
        alerts_snapshot=snapshots['alerts_snapshot'],
        recommendations=recommendation_items,
    )
    decisions_value = decision_items(recommendation_items, findings)
    executive_metrics = _executive_metrics(metrics, snapshots['storage_snapshot'], recommendation_items, findings)
    return OverviewState(
        **snapshots,
        resource_metrics=metrics,
        forecast_series=series,
        recommendation_items=recommendation_items,
        alert_items=alert_items,
        anomaly_items=anomaly_items,
        inventory=inventory,
        source_rows=source_rows_value,
        priority_findings=findings,
        decisions=decisions_value,
        executive_metrics=executive_metrics,
    )


def _snapshot_groups(payload: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        'snapshot_summary': mapping(payload.get('snapshot_summary')),
        'resource_snapshot': mapping(payload.get('resource_snapshot')),
        'capacity_snapshot': mapping(payload.get('capacity_snapshot')),
        'storage_snapshot': mapping(payload.get('storage_snapshot')),
        'workload_snapshot': mapping(payload.get('workload_snapshot')),
        'forecast_snapshot': mapping(payload.get('forecast_snapshot')),
        'alerts_snapshot': mapping(payload.get('alerts_snapshot')),
        'health_summary': mapping(payload.get('health_summary')),
        'actionable': mapping(payload.get('actionable_recommendations')),
        'top_consumers': mapping(payload.get('top_consumers')),
        'alert_detail': mapping(payload.get('alert_detail')),
        'reporting_summary': mapping(payload.get('reporting_summary')),
        'inventory_snapshot': mapping(payload.get('inventory_snapshot')),
        'freshness': mapping(payload.get('data_freshness')),
    }


def _executive_metrics(
    metrics: Mapping[str, Mapping[str, Any]],
    storage_snapshot: Mapping[str, Any],
    recommendation_items: Sequence[Mapping[str, Any]],
    findings: Sequence[Mapping[str, Any]],
) -> tuple[Mapping[str, Any], ...]:
    active_count = len(recommendation_items) or len(findings)
    return (
        executive_metric(metrics, 'cpu', 'CPU P95'),
        executive_metric(metrics, 'memory', 'Memory P95'),
        storage_headroom_metric(storage_snapshot),
        {
            'label': 'Active Findings',
            'value': str(active_count),
            'status': 'Review' if recommendation_items or findings else 'Normal',
            'tone': 'warning' if recommendation_items or findings else 'normal',
            'note': 'Evidence-backed items requiring operational review.',
        },
    )
