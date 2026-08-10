from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class DashboardClusterOption:
    id: str
    name: str


@dataclass(slots=True)
class DashboardKpi:
    label: str
    value: str
    description: str
    icon: str


@dataclass(slots=True)
class DashboardKpiContext:
    clusters_raw: list[object]
    clusters: list[DashboardClusterOption]
    nodes_total: int
    nodes_ready: int
    not_ready_nodes: int
    namespaces_total: int
    workloads_total: int
    pods_total: int
    running_pods: int
    unhealthy_pods: int
    capacity_snapshot: CapacitySnapshot
    alerts_snapshot: AlertsSnapshot
    selected_cluster: object | None
    active_alerts_label: str
    active_alerts_description: str


@dataclass(slots=True)
class ClusterStatusSignals:
    cluster: object
    nodes_total: int
    not_ready_nodes: int
    unhealthy_pods: int
    inventory_nodes_available: bool
    active_alerts: int
    critical_alerts: int
    warning_alerts: int
    cpu_percent: float | None
    memory_percent: float | None


@dataclass(slots=True)
class ClusterHealthRow:
    cluster_id: str
    cluster_name: str
    cluster_endpoint: str
    status: str
    status_reason: str
    nodes_ready: int | None
    nodes_total: int | None
    nodes_status: str = 'Unavailable'
    cpu_percent: float | None = None
    memory_percent: float | None = None
    cpu_status: str = 'Unavailable'
    memory_status: str = 'Unavailable'
    active_alerts: int | None = None
    alerts_status: str = 'Unavailable'
    last_sync: str = 'No sync yet'


@dataclass(slots=True)
class ClusterHealthPagination:
    page: int = 1
    per_page: int = 5
    total_items: int = 0
    total_pages: int = 1
    has_prev: bool = False
    has_next: bool = False
    prev_page: int = 1
    next_page: int = 1
    start_item: int = 0
    end_item: int = 0


@dataclass(slots=True)
class CapacityItem:
    label: str
    used_percent: float | None
    headroom_percent: float | None
    description: str


@dataclass(slots=True)
class CapacitySnapshot:
    items: list[CapacityItem] = field(default_factory=list)
    risk: str = 'Unknown'
    insight: str = 'Capacity metrics are not available yet.'
    risk_detail: str = 'Risk meaning is unavailable until worker capacity metrics are loaded.'
    recommended_action: str = 'Select a cluster and verify the Prometheus source before taking capacity action.'
    source_status: str = 'Unavailable'


@dataclass(slots=True)
class AlertItem:
    title: str
    description: str
    severity: str
    age: str = ''


@dataclass(slots=True)
class AlertsSnapshot:
    critical: int = 0
    warning: int = 0
    info: int = 0
    items: list[AlertItem] = field(default_factory=list)
    source_status: str = 'Unavailable'
    message: str = 'Alertmanager data is not available yet.'


@dataclass(slots=True)
class ConsumerItem:
    rank: int
    name: str
    namespace: str
    value: str
    percent: float | None = None
    request_display: str = '-'
    limit_display: str = '-'
    signal_label: str = 'Usage Only'
    signal_state: str = 'unknown'


@dataclass(slots=True)
class TopConsumersSnapshot:
    cpu: list[ConsumerItem] = field(default_factory=list)
    memory: list[ConsumerItem] = field(default_factory=list)
    source_status: str = 'Unavailable'
    message: str = 'Prometheus top consumer data is not available yet.'
    insight_title: str = 'Consumer Insights'
    insight_description: str = 'Select a cluster to evaluate top consumer signals.'
    insight_items: list[str] = field(default_factory=list)
    missing_request_limit_count: int = 0
    high_usage_count: int = 0


@dataclass(slots=True)
class ForecastItem:
    label: str
    risk: str
    icon: str
    key: str = 'resource'
    projected_percent: float | None = None
    latest_daily_average_percent: float | None = None
    trend: str = 'Unknown'
    historical_points: str = ''
    forecast_points: str = ''


@dataclass(slots=True)
class ForecastSnapshot:
    items: list[ForecastItem] = field(default_factory=list)
    insight: str = 'Insufficient trend data for reliable forecasting.'
    source_status: str = 'Unavailable'
    horizon_days: int = 90
    item_count: int = 0
    at_risk_count: int = 0
    critical_count: int = 0
    highest_projected_label: str = 'N/A'
    highest_projected_percent: float | None = None
    has_historical_series: bool = False


@dataclass(slots=True)
class InventorySnapshot:
    namespaces: int = 0
    workloads: int = 0
    pods: int = 0
    services: int = 0
    ingresses: int = 0
    storage: int = 0
    running_pods: int = 0
    unhealthy_pods: int = 0


@dataclass(slots=True)
class ReportItem:
    title: str
    status: str
    generated_at: str


@dataclass(slots=True)
class ReportingSnapshot:
    generated_reports: int = 0
    templates: int = 0
    schedules: int = 0
    latest_reports: list[ReportItem] = field(default_factory=list)
    source_status: str = 'Available'


@dataclass(slots=True)
class FreshnessItem:
    label: str
    status: str
    value: str
    icon: str
    description: str = ''
    tone: str = 'unknown'


@dataclass(slots=True)
class RecommendationItem:
    title: str
    description: str
    category: str
    severity: str
    icon: str
    href: str = '#'
    priority: str = 'P3'
    source: str = 'Intelligence engine'
    rule_key: str = ''


@dataclass(slots=True)
class DashboardOverview:
    clusters: list[DashboardClusterOption] = field(default_factory=list)
    selected_cluster_id: str | None = None
    active_tab: str = 'overview'
    last_updated: str = 'Just now'
    global_kpis: list[DashboardKpi] = field(default_factory=list)
    cluster_health_snapshot: list[ClusterHealthRow] = field(default_factory=list)
    cluster_health_pagination: ClusterHealthPagination = field(default_factory=ClusterHealthPagination)
    capacity_snapshot: CapacitySnapshot = field(default_factory=CapacitySnapshot)
    alerts_snapshot: AlertsSnapshot = field(default_factory=AlertsSnapshot)
    top_consumers_snapshot: TopConsumersSnapshot = field(default_factory=TopConsumersSnapshot)
    forecast_snapshot: ForecastSnapshot = field(default_factory=ForecastSnapshot)
    inventory_snapshot: InventorySnapshot = field(default_factory=InventorySnapshot)
    reporting_snapshot: ReportingSnapshot = field(default_factory=ReportingSnapshot)
    data_freshness: list[FreshnessItem] = field(default_factory=list)
    recommended_actions: list[RecommendationItem] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)
