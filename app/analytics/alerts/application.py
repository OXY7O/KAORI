from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.analytics.alerts.anomalies import filter_anomalies, load_prometheus_anomaly_metrics
from app.analytics.alerts.contracts import (
    PER_PAGE_OPTIONS,
    SEVERITY_OPTIONS,
    SOURCE_OPTIONS,
    STATUS_OPTIONS,
    normalize_option,
    normalize_page,
    normalize_per_page,
    normalize_string,
    paginate_items,
)
from app.analytics.alerts.health import (
    build_integration_status,
    build_source_health,
    build_summary,
)
from app.analytics.alerts.inhibition import build_inhibition_summary
from app.analytics.alerts.ownership import build_ownership_summary
from app.analytics.alerts.readiness import build_incident_readiness
from app.analytics.alerts.routing import build_routing_summary
from app.analytics.alerts.selection import (
    get_clusters_for_filter,
    get_namespace_options,
    get_selected_cluster,
)
from app.analytics.alerts.signals import build_resource_links, build_selected_cluster_signal_overview
from app.analytics.alerts.silences import build_silence_summary
from app.analytics.alerts.sources import filter_items, load_alerts_by_source
from app.common.dependencies import (
    alert_source_connection_blocker,
    alert_source_setup_blocker,
    cluster_required_blocker,
)
from app.intelligence.recommendation_engine import (
    build_alerts_actionable_recommendations,
    count_actionable_recommendations,
    format_recommendation_cards,
)


def get_alerts_context(
    *,
    cluster_id: str | None,
    source: str | None,
    severity: str | None,
    status: str | None,
    namespace: str | None,
    search: str | None,
    page: str | int | None,
    alerts_per_page: str | int | None,
    anomalies_per_page: str | int | None,
) -> dict[str, Any]:
    clusters = get_clusters_for_filter()

    selected_cluster = get_selected_cluster(
        cluster_id=cluster_id,
    )

    selected_source = normalize_option(
        source,
        allowed=SOURCE_OPTIONS,
        default='auto',
    )

    selected_severity = normalize_option(
        severity,
        allowed=SEVERITY_OPTIONS,
        default='all',
    )

    selected_status = normalize_option(
        status,
        allowed=STATUS_OPTIONS,
        default='all',
    )

    selected_namespace = normalize_string(
        namespace,
    )

    selected_search = normalize_string(
        search,
    )

    selected_page = normalize_page(
        page,
    )

    selected_alerts_per_page = normalize_per_page(
        alerts_per_page,
    )

    selected_anomalies_per_page = normalize_per_page(
        anomalies_per_page,
    )

    namespace_options = get_namespace_options(
        cluster=selected_cluster,
    )

    if selected_namespace and selected_namespace not in namespace_options:
        selected_namespace = ''

    raw_alerts, source_status = load_alerts_by_source(
        cluster=selected_cluster,
        source=selected_source,
    )

    filtered_alerts = filter_items(
        raw_alerts,
        severity=selected_severity,
        status=selected_status,
        namespace=selected_namespace,
        search=selected_search,
    )

    paginated_alerts, pagination = paginate_items(
        filtered_alerts,
        page=selected_page,
        per_page=selected_alerts_per_page,
    )

    raw_anomalies = (
        load_prometheus_anomaly_metrics(
            cluster=selected_cluster,
        )
        if selected_cluster is not None
        else []
    )

    anomalies = filter_anomalies(
        raw_anomalies,
        severity=selected_severity,
        namespace=selected_namespace,
        search=selected_search,
    )

    anomaly_rows, anomaly_pagination = paginate_items(
        anomalies,
        page=1,
        per_page=selected_anomalies_per_page,
    )

    summary = build_summary(
        alerts=filtered_alerts,
        anomalies=anomalies,
        source_status=source_status,
    )

    actionable_payload = {
        'alerts': filtered_alerts,
        'all_alerts': filtered_alerts,
        'anomalies': anomalies,
        'all_anomalies': anomalies,
        'summary': summary,
        'source_status': source_status,
        'selected_cluster_signal_overview': build_selected_cluster_signal_overview(
            cluster=selected_cluster,
            alerts=raw_alerts,
            anomalies=raw_anomalies,
            source_status=source_status,
        ),
    }

    actionable_recommendations = build_alerts_actionable_recommendations(
        actionable_payload,
    )
    recommendation_cards = format_recommendation_cards(
        actionable_recommendations,
        default_title='Continue alert and anomaly monitoring',
        default_description=(
            'No actionable alert or anomaly recommendation was generated. '
            'Continue monitoring alert source health, active signals, and anomaly candidates.'
        ),
        default_source='alerts',
        default_action_type='alert_review',
    )

    selected_cluster_signal_overview = actionable_payload['selected_cluster_signal_overview']

    integration_status = build_integration_status(
        cluster=selected_cluster,
        source_status=source_status,
    )

    dependency_blocker = cluster_required_blocker() if selected_cluster is None else None

    if selected_cluster is not None and not source_status.get('connected', False):
        if source_status.get('configured', False):
            dependency_blocker = alert_source_connection_blocker(
                selected_cluster,
                source=selected_source,
                detail=str(source_status.get('error') or ''),
            )
        else:
            dependency_blocker = alert_source_setup_blocker(
                selected_cluster,
                source=selected_source,
            )

    source_health = build_source_health(
        cluster=selected_cluster,
        source_status=source_status,
        integration_status=integration_status,
    )

    routing_summary = build_routing_summary(
        alerts=raw_alerts,
        source_status=source_status,
    )

    silence_summary = build_silence_summary(
        cluster=selected_cluster,
        alerts=raw_alerts,
        source_status=source_status,
    )

    inhibition_summary = build_inhibition_summary(
        alerts=raw_alerts,
        source_status=source_status,
    )

    ownership_summary = build_ownership_summary(
        alerts=raw_alerts,
        source_status=source_status,
    )

    incident_readiness = build_incident_readiness(
        signal_overview=selected_cluster_signal_overview,
        source_health=source_health,
        routing_summary=routing_summary,
        silence_summary=silence_summary,
        inhibition_summary=inhibition_summary,
        ownership_summary=ownership_summary,
    )

    return {
        'clusters': clusters,
        'selected_cluster': selected_cluster,
        'selected_cluster_id': selected_cluster.id if selected_cluster else '',
        'selected_source': selected_source,
        'selected_severity': selected_severity,
        'selected_status': selected_status,
        'selected_namespace': selected_namespace,
        'selected_search': selected_search,
        'selected_alerts_per_page': selected_alerts_per_page,
        'selected_anomalies_per_page': selected_anomalies_per_page,
        'selected_per_page': selected_alerts_per_page,
        'source_options': SOURCE_OPTIONS,
        'severity_options': SEVERITY_OPTIONS,
        'status_options': STATUS_OPTIONS,
        'per_page_options': PER_PAGE_OPTIONS,
        'namespace_options': namespace_options,
        'alerts': paginated_alerts,
        'all_alerts': filtered_alerts,
        'alerts_pagination': pagination,
        'anomalies': anomaly_rows,
        'all_anomalies': anomalies,
        'anomalies_pagination': anomaly_pagination,
        'summary': summary,
        'source_status': source_status,
        'integration_status': integration_status,
        'dependency_blocker': dependency_blocker,
        'source_health': source_health,
        'routing_summary': routing_summary,
        'silence_summary': silence_summary,
        'inhibition_summary': inhibition_summary,
        'ownership_summary': ownership_summary,
        'incident_readiness': incident_readiness,
        'resource_links': build_resource_links(
            cluster=selected_cluster,
        ),
        'selected_cluster_signal_overview': selected_cluster_signal_overview,
        'actionable_recommendations': actionable_recommendations,
        'recommendation_cards': recommendation_cards,
        'recommendation_count': count_actionable_recommendations(
            actionable_recommendations,
        ),
        'recommendations': recommendation_cards,
        'generated_at': datetime.now(
            UTC,
        ),
    }
