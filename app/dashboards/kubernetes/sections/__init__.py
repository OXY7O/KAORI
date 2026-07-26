"""Independent Kubernetes dashboard section builders."""

from app.dashboards.kubernetes.sections.alerts import alerts_snapshot_with_message, build_alerts_snapshot
from app.dashboards.kubernetes.sections.capacity import build_capacity_snapshot, empty_capacity_snapshot
from app.dashboards.kubernetes.sections.cluster_health import build_cluster_health, paginate_sequence
from app.dashboards.kubernetes.sections.forecast import build_forecast_snapshot
from app.dashboards.kubernetes.sections.freshness import build_data_freshness, build_hero_integration_meta
from app.dashboards.kubernetes.sections.kpis import build_kpis
from app.dashboards.kubernetes.sections.recommendations import build_recommendations
from app.dashboards.kubernetes.sections.reporting import build_reporting_snapshot
from app.dashboards.kubernetes.sections.top_consumers import (
    build_top_consumers_snapshot,
    top_consumers_snapshot_with_message,
)

__all__ = [
    'alerts_snapshot_with_message',
    'build_alerts_snapshot',
    'build_capacity_snapshot',
    'empty_capacity_snapshot',
    'build_cluster_health',
    'paginate_sequence',
    'build_forecast_snapshot',
    'build_data_freshness',
    'build_hero_integration_meta',
    'build_kpis',
    'build_recommendations',
    'build_reporting_snapshot',
    'build_top_consumers_snapshot',
    'top_consumers_snapshot_with_message',
]
