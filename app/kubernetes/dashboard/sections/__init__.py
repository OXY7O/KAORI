"""Independent Kubernetes dashboard section builders."""

from app.kubernetes.dashboard.sections.alerts import build_alerts_snapshot
from app.kubernetes.dashboard.sections.capacity import build_capacity_snapshot
from app.kubernetes.dashboard.sections.cluster_health import build_cluster_health, paginate_sequence
from app.kubernetes.dashboard.sections.forecast import build_forecast_snapshot
from app.kubernetes.dashboard.sections.freshness import build_data_freshness
from app.kubernetes.dashboard.sections.kpis import build_kpis
from app.kubernetes.dashboard.sections.recommendations import build_recommendations
from app.kubernetes.dashboard.sections.reporting import build_reporting_snapshot
from app.kubernetes.dashboard.sections.top_consumers import build_top_consumers_snapshot

__all__ = [
    'build_alerts_snapshot',
    'build_capacity_snapshot',
    'build_cluster_health',
    'paginate_sequence',
    'build_forecast_snapshot',
    'build_data_freshness',
    'build_kpis',
    'build_recommendations',
    'build_reporting_snapshot',
    'build_top_consumers_snapshot',
]
