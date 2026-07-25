from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.analytics.materialization.service import SnapshotResult, read_snapshot

CAPACITY_DATASET_KEY = 'analytics.capacity'
TOP_CONSUMERS_DATASET_KEY = 'analytics.top_consumers'
FORECAST_DATASET_KEY = 'analytics.forecast'
ALERTS_DATASET_KEY = 'dashboard.kubernetes.alerts'


def capacity_parameters(cluster_id: str) -> dict[str, str]:
    return {'cluster_id': cluster_id, 'time_range': '24h'}


def top_consumers_parameters(cluster_id: str) -> dict[str, str]:
    return {'cluster_id': cluster_id, 'time_range': '24h'}


def forecast_parameters(cluster_id: str) -> dict[str, str]:
    return {
        'cluster_id': cluster_id,
        'history_window': '30d',
        'forecast_horizon': '90d',
        'resource': 'all',
        'method': 'linear',
    }


def alerts_parameters(cluster_id: str) -> dict[str, str]:
    return {'cluster_id': cluster_id}


@dataclass(frozen=True, slots=True)
class DashboardSnapshot:
    context: dict[str, Any] | None
    state: str
    stale: bool
    generated_at: datetime | None
    last_attempt_at: datetime | None
    last_error: str | None

    @property
    def available(self) -> bool:
        return self.context is not None


def read_dashboard_snapshot(
    *, cluster_id: str, dataset_key: str, parameters: dict[str, str]
) -> DashboardSnapshot:
    result: SnapshotResult = read_snapshot(
        cluster_id=cluster_id,
        dataset_key=dataset_key,
        parameters=parameters,
    )
    snapshot = result.snapshot
    return DashboardSnapshot(
        context=result.context,
        state=result.state,
        stale=result.stale,
        generated_at=getattr(snapshot, 'generated_at', None),
        last_attempt_at=getattr(snapshot, 'last_attempt_at', None),
        last_error=getattr(snapshot, 'last_error', None),
    )


def unavailable_message(label: str, snapshot: DashboardSnapshot) -> str:
    if snapshot.state == 'pending':
        return f'{label} snapshot is being prepared by a KAORI worker.'
    if snapshot.state == 'failed':
        return f'{label} worker refresh failed. Review Jobs & Executions for details.'
    if snapshot.state == 'expired':
        return f'{label} snapshot expired and is waiting for the next worker refresh.'
    if snapshot.state == 'invalid':
        return f'{label} snapshot is invalid and must be regenerated.'
    return f'No committed {label.lower()} snapshot is available yet.'
