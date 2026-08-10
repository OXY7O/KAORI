from dataclasses import dataclass
from datetime import datetime
from math import ceil
from typing import (
    Any,
    Literal,
    NotRequired,
    TypedDict,
)

DEFAULT_PER_PAGE = 5

PER_PAGE_OPTIONS = [5, 10, 25, 50]
SOURCE_OPTIONS = ['auto', 'alertmanager', 'prometheus']
SEVERITY_OPTIONS = ['all', 'critical', 'warning', 'info', 'none']
STATUS_OPTIONS = ['all', 'firing', 'pending', 'resolved', 'active']


class NormalizedAlert(TypedDict):
    name: str
    severity: str
    status: str
    namespace: Any
    target: Any
    source: Literal['Alertmanager', 'Prometheus']
    summary: Any
    description: Any
    starts_at: Any
    starts_at_display: str
    ends_at: Any
    ends_at_display: str
    labels: dict[str, Any]
    annotations: dict[str, Any]
    owner: str
    runbook_url: str
    contact: str
    generator_url: Any
    fingerprint: Any
    receiver: NotRequired[Any]
    route: NotRequired[Any]
    silenced: NotRequired[bool]
    inhibited: NotRequired[bool]
    silenced_by: NotRequired[Any]
    inhibited_by: NotRequired[Any]
    value: NotRequired[str]


class AlertSourceStatus(TypedDict):
    source: str
    selected_source: str
    resolved_source: str
    label: str
    configured: bool
    connected: bool
    fallback_used: bool
    fallback_reason: str | None
    error: str | None
    response_time_ms: int | None
    last_checked_at: datetime | None


class AlertIntegrationStatus(TypedDict):
    configured: bool
    connected: bool
    label: str
    status: Literal['not_set', 'configured', 'connected']
    response_time_ms: int | None


class AlertIntegrationStatusMap(TypedDict):
    prometheus: AlertIntegrationStatus
    alertmanager: AlertIntegrationStatus


class AlertSourceHealthCheck(TypedDict):
    label: str
    status: Literal['pass', 'warning', 'fail']
    description: str


class AlertSourceHealthSummary(TypedDict):
    score: int
    level: Literal['healthy', 'fallback', 'degraded', 'unavailable']
    label: str
    description: str
    icon: str
    checks: list[AlertSourceHealthCheck]
    selected_source: NotRequired[str]
    resolved_source: NotRequired[str]
    fallback_used: NotRequired[bool]


class AlertRoutingGroup(TypedDict):
    label: str
    count: int
    percent: float


class AlertRoutingSummary(TypedDict):
    enabled: bool
    level: Literal['available', 'limited', 'unavailable']
    label: str
    description: str
    icon: str
    source: str
    alert_count: int
    receiver_count: int
    group_count: int
    fingerprint_count: int
    namespace_count: int
    severity_groups: list[AlertRoutingGroup]
    receiver_groups: list[AlertRoutingGroup]
    namespace_groups: list[AlertRoutingGroup]
    grouping_keys: list[AlertRoutingGroup]


class AlertSilenceApiStatus(TypedDict):
    connected: bool
    error: str | None


class AlertSilenceMatcher(TypedDict):
    name: str
    value: str
    is_regex: bool
    is_equal: bool
    label: str


class AlertSilenceItem(TypedDict):
    id: str
    state: str
    created_by: str
    comment: str
    starts_at: str
    ends_at: str
    matchers: list[str]
    matched_alerts: int


class AlertSilenceSummary(TypedDict):
    enabled: bool
    level: Literal['available', 'limited', 'unavailable']
    label: str
    description: str
    icon: str
    source: str
    active_silences: int
    pending_silences: int
    expired_silences: int
    matched_alerts: int
    silenced_namespaces: list[str]
    silenced_matchers: list[str]
    items: list[AlertSilenceItem]


class AlertInhibitionItem(TypedDict):
    name: str
    namespace: str
    target: str
    severity: str
    inhibited_by: Any


class AlertInhibitionSummary(TypedDict):
    enabled: bool
    level: Literal['available', 'limited', 'unavailable']
    label: str
    description: str
    icon: str
    source: str
    rules_detected: int
    matched_alerts: int
    source_equal_labels: list[str]
    target_matchers: list[str]
    items: list[AlertInhibitionItem]


class AlertOwnershipGroup(TypedDict):
    label: str
    count: int
    percent: float


class AlertRunbookItem(TypedDict):
    name: str
    namespace: str
    url: str
    owner: str


class AlertMissingMetadataItem(TypedDict):
    name: str
    namespace: str
    severity: str
    missing: list[str]


class AlertOwnershipSummary(TypedDict):
    score: int
    level: Literal['ready', 'partial', 'weak', 'unknown']
    label: str
    description: str
    icon: str
    source: str
    alert_count: int
    owner_count: int
    runbook_count: int
    contact_count: int
    missing_owner_count: int
    missing_runbook_count: int
    missing_contact_count: int
    owner_groups: list[AlertOwnershipGroup]
    runbook_items: list[AlertRunbookItem]
    missing_metadata_items: list[AlertMissingMetadataItem]


class AlertResourceLink(TypedDict):
    configured: bool
    label: str
    url: str | None
    description: str
    name: NotRequired[str | None]
    email: NotRequired[str | None]


class AlertResourceLinks(TypedDict):
    alertmanager: AlertResourceLink
    runbook: AlertResourceLink
    contact_point: AlertResourceLink


class AlertSignalPriority(TypedDict):
    level: Literal['critical', 'warning', 'normal', 'unknown']
    label: str
    description: str
    icon: str


class AlertSignalInsight(TypedDict):
    dominant_signal: str
    dominant_signal_count: int
    dominant_anomaly: str
    dominant_anomaly_count: int
    action_hint: str


class AlertSignalBars(TypedDict):
    active_alerts: int
    critical_alerts: int
    warning_alerts: int
    anomalies: int


class AlertSelectedClusterSignalOverview(TypedDict):
    cluster_id: str
    cluster_name: str
    source: str
    fallback_used: bool
    fallback_reason: str | None
    connected: bool
    evidence_complete: bool
    active_alerts: int
    critical_alerts: int
    warning_alerts: int
    info_alerts: int
    pending_alerts: int
    resolved_alerts: int
    anomalies: int
    restart_anomalies: int
    not_ready_anomalies: int
    total_signals: int
    priority: AlertSignalPriority
    insight: AlertSignalInsight
    bars: AlertSignalBars


class AlertIncidentReadinessCheck(TypedDict):
    label: str
    status: Literal['pass', 'warning', 'fail']
    description: str


class AlertIncidentReadinessSummary(TypedDict):
    score: int
    level: Literal['ready', 'watch', 'degraded', 'incident_risk']
    label: str
    description: str
    icon: str
    critical_signals: int
    warning_signals: int
    anomaly_signals: int
    ownership_score: int
    source_score: int
    silence_risk: int
    inhibition_risk: int
    routing_ready: bool
    recommended_action: str
    checks: list[AlertIncidentReadinessCheck]


class AlertsSnapshot(TypedDict):
    firing_alerts: int
    pending_alerts: int
    critical_alerts: int
    warning_alerts: int
    recent_anomalies: int
    highest_severity: str
    highest_severity_description: str
    source: str
    resolved_source: str
    fallback_used: bool
    fallback_reason: str | None
    source_connected: bool
    source_health: AlertSourceHealthSummary
    routing_summary: AlertRoutingSummary
    silence_summary: AlertSilenceSummary
    inhibition_summary: AlertInhibitionSummary
    ownership_summary: AlertOwnershipSummary
    incident_readiness: AlertIncidentReadinessSummary
    priority: AlertSignalPriority
    insight: AlertSignalInsight
    recommendation_count: int
    evidence_complete: bool
    anomaly_evidence_partial: bool
    status: str
    tone: str


type AlertLoadResult = tuple[list[NormalizedAlert], AlertSourceStatus]


@dataclass(frozen=True, slots=True)
class AlertsSelection:
    cluster_id: str | None = None
    source: str | None = 'auto'
    severity: str | None = 'all'
    status: str | None = 'all'
    namespace: str | None = ''
    search: str | None = ''
    alerts_page: str | int | None = 1
    anomalies_page: str | int | None = 1
    alerts_per_page: str | int | None = DEFAULT_PER_PAGE
    anomalies_per_page: str | int | None = DEFAULT_PER_PAGE
    preserve_namespace: bool = False


@dataclass(frozen=True)
class AlertsPagination:
    page: int
    per_page: int
    total_items: int
    total_pages: int
    has_prev: bool
    has_next: bool
    prev_page: int
    next_page: int
    start_item: int
    end_item: int


def normalize_page(
    value: str | int | None,
) -> int:
    try:
        page = int(
            value or 1,
        )
    except (
        TypeError,
        ValueError,
    ):
        return 1

    return max(
        page,
        1,
    )


def normalize_per_page(
    value: str | int | None,
) -> int:
    try:
        per_page = int(
            value or DEFAULT_PER_PAGE,
        )
    except (
        TypeError,
        ValueError,
    ):
        return DEFAULT_PER_PAGE

    if per_page not in PER_PAGE_OPTIONS:
        return DEFAULT_PER_PAGE

    return per_page


def normalize_string(
    value: str | None,
    *,
    default: str = '',
) -> str:
    return (value or default).strip()


def normalize_option(
    value: str | None,
    *,
    allowed: list[str],
    default: str,
) -> str:
    normalized = (value or default).strip().lower()

    if normalized not in allowed:
        return default

    return normalized


def build_pagination(
    *,
    page: int,
    per_page: int,
    total_items: int,
) -> AlertsPagination:
    total_pages = max(
        ceil(
            total_items / per_page,
        ),
        1,
    )

    page = min(
        page,
        total_pages,
    )

    if total_items == 0:
        start_item = 0
        end_item = 0
    else:
        start_item = ((page - 1) * per_page) + 1
        end_item = min(
            page * per_page,
            total_items,
        )

    return AlertsPagination(
        page=page,
        per_page=per_page,
        total_items=total_items,
        total_pages=total_pages,
        has_prev=page > 1,
        has_next=page < total_pages,
        prev_page=max(
            page - 1,
            1,
        ),
        next_page=min(
            page + 1,
            total_pages,
        ),
        start_item=start_item,
        end_item=end_item,
    )


def paginate_items[ItemT](
    items: list[ItemT],
    *,
    page: int,
    per_page: int,
) -> tuple[list[ItemT], AlertsPagination]:
    pagination = build_pagination(
        page=page,
        per_page=per_page,
        total_items=len(
            items,
        ),
    )

    start = (pagination.page - 1) * pagination.per_page
    end = start + pagination.per_page

    return items[start:end], pagination
