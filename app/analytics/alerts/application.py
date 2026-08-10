from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any, cast

from app.analytics.alerts.anomalies import filter_anomalies, load_prometheus_anomaly_metrics
from app.analytics.alerts.contracts import (
    PER_PAGE_OPTIONS,
    SEVERITY_OPTIONS,
    SOURCE_OPTIONS,
    STATUS_OPTIONS,
    AlertSelectedClusterSignalOverview,
    AlertSourceStatus,
    AlertsSelection,
    NormalizedAlert,
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
    is_alert_evidence_complete,
)
from app.analytics.alerts.inhibition import build_inhibition_summary
from app.analytics.alerts.ownership import build_ownership_summary
from app.analytics.alerts.readiness import build_incident_readiness
from app.analytics.alerts.records import filter_items
from app.analytics.alerts.routing import build_routing_summary
from app.analytics.alerts.selection import get_clusters_for_filter, get_namespace_options, get_selected_cluster
from app.analytics.alerts.signals import build_resource_links, build_selected_cluster_signal_overview
from app.analytics.alerts.silences import build_silence_summary
from app.analytics.alerts.sources import load_alerts_by_source
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


def _summary_aliases(summary: Mapping[str, Any] | None) -> dict[str, int]:
    values = summary or {}
    return {
        'active_alerts': int(values.get('active_alerts') or 0),
        'critical_alerts': int(values.get('critical_alerts') or 0),
        'warning_alerts': int(values.get('warning_alerts') or 0),
        'anomaly_count': int(values.get('detected_anomalies') or 0),
    }


def _normalize_selection(selection: AlertsSelection) -> dict[str, Any]:
    return {
        'cluster_id': str(selection.cluster_id or '') or None,
        'source': normalize_option(selection.source, allowed=SOURCE_OPTIONS, default='auto'),
        'severity': normalize_option(selection.severity, allowed=SEVERITY_OPTIONS, default='all'),
        'status': normalize_option(selection.status, allowed=STATUS_OPTIONS, default='all'),
        'namespace': normalize_string(selection.namespace),
        'search': normalize_string(selection.search),
        'alerts_page': normalize_page(selection.alerts_page),
        'anomalies_page': normalize_page(selection.anomalies_page),
        'alerts_per_page': normalize_per_page(selection.alerts_per_page),
        'anomalies_per_page': normalize_per_page(selection.anomalies_per_page),
    }


def _load_anomaly_evidence(cluster) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, str]]]:
    if cluster is None:
        return (
            [],
            {
                'configured': False,
                'connected': False,
                'label': 'Cluster Required',
                'error': None,
                'response_time_ms': None,
                'partial': False,
                'available_queries': [],
                'failed_queries': [],
            },
            [],
        )

    anomalies, status = load_prometheus_anomaly_metrics(cluster=cluster)
    if not status.get('partial', False):
        return anomalies, status, []

    partially_available = bool(status.get('connected'))
    warning = {
        'title': (
            'Prometheus Anomaly Evidence Is Partial'
            if partially_available
            else 'Prometheus Anomaly Evidence Is Unavailable'
        ),
        'detail': str(
            status.get('error') or 'One or more optional Prometheus anomaly queries did not return usable evidence.'
        ),
        'remediation': (
            'Review the Analytics Worker job log and Prometheus query pressure. '
            'Successful alert or anomaly signal families remain available from the committed snapshot.'
        ),
    }
    return anomalies, status, [warning]


def _namespace_options(
    *,
    inventory_options: list[str],
    alerts: Sequence[Mapping[str, Any]],
    anomalies: Sequence[Mapping[str, Any]],
) -> list[str]:
    observed = {
        str(item.get('namespace') or '').strip()
        for item in [*alerts, *anomalies]
        if str(item.get('namespace') or '').strip() not in {'', '-'}
    }
    inventory = {str(item).strip() for item in inventory_options if str(item).strip()}
    return sorted(inventory | observed)


def _present_collections(
    *,
    raw_alerts: list[NormalizedAlert],
    raw_anomalies: list[dict[str, Any]],
    selected: dict[str, Any],
) -> dict[str, Any]:
    filtered_alerts = filter_items(
        raw_alerts,
        severity=selected['severity'],
        status=selected['status'],
        namespace=selected['namespace'],
        search=selected['search'],
    )
    filtered_anomalies = filter_anomalies(
        raw_anomalies,
        severity=selected['severity'],
        namespace=selected['namespace'],
        search=selected['search'],
    )
    alert_rows, alert_pagination = paginate_items(
        filtered_alerts,
        page=selected['alerts_page'],
        per_page=selected['alerts_per_page'],
    )
    anomaly_rows, anomaly_pagination = paginate_items(
        filtered_anomalies,
        page=selected['anomalies_page'],
        per_page=selected['anomalies_per_page'],
    )
    return {
        'alerts': alert_rows,
        'filtered_alerts': filtered_alerts,
        'alerts_pagination': alert_pagination,
        'anomalies': anomaly_rows,
        'filtered_anomalies': filtered_anomalies,
        'anomalies_pagination': anomaly_pagination,
    }


def _build_recommendation_context(
    *,
    alerts: list[NormalizedAlert],
    anomalies: list[dict[str, Any]],
    summary: dict[str, Any],
    source_status: AlertSourceStatus,
    collection_warnings: list[dict[str, str]],
    anomaly_source_status: dict[str, Any],
    signal_overview: AlertSelectedClusterSignalOverview,
) -> dict[str, Any]:
    recommendations = build_alerts_actionable_recommendations(
        {
            'alerts': alerts,
            'all_alerts': alerts,
            'anomalies': anomalies,
            'all_anomalies': anomalies,
            'summary': summary,
            **_summary_aliases(summary),
            'source_status': source_status,
            'collection_warnings': collection_warnings,
            'anomaly_source_status': anomaly_source_status,
            'selected_cluster_signal_overview': signal_overview,
        }
    )
    cards = format_recommendation_cards(
        recommendations,
        default_title='Continue Alert and Anomaly Monitoring',
        default_description=(
            'No actionable alert or anomaly recommendation was generated. '
            'Continue monitoring alert source health, active signals, and anomaly candidates.'
        ),
        default_source='alerts',
        default_action_type='alert_review',
    )
    return {
        'actionable_recommendations': recommendations,
        'recommendation_cards': cards,
        'recommendation_count': count_actionable_recommendations(recommendations),
        'recommendations': cards,
    }


def _dependency_blocker(*, cluster, source_status: AlertSourceStatus, selected_source: str):
    if cluster is None:
        return cluster_required_blocker()
    if source_status.get('connected', False):
        return None
    if source_status.get('configured', False):
        return alert_source_connection_blocker(
            cluster,
            source=selected_source,
            detail=str(source_status.get('error') or ''),
        )
    return alert_source_setup_blocker(cluster, source=selected_source)


def _operational_context(
    *,
    cluster,
    source_status: AlertSourceStatus,
    anomaly_source_status: dict[str, Any],
    raw_alerts: list[NormalizedAlert],
    raw_anomalies: list[dict[str, Any]],
    signal_overview: AlertSelectedClusterSignalOverview,
) -> dict[str, Any]:
    integration_status = build_integration_status(
        cluster=cluster,
        source_status=source_status,
        anomaly_source_status=anomaly_source_status,
    )
    source_health = build_source_health(
        cluster=cluster,
        source_status=source_status,
        integration_status=integration_status,
    )
    routing_summary = build_routing_summary(alerts=raw_alerts, source_status=source_status)
    silence_summary = build_silence_summary(
        cluster=cluster,
        alerts=raw_alerts,
        source_status=source_status,
    )
    inhibition_summary = build_inhibition_summary(alerts=raw_alerts, source_status=source_status)
    ownership_summary = build_ownership_summary(alerts=raw_alerts, source_status=source_status)
    incident_readiness = build_incident_readiness(
        signal_overview=signal_overview,
        source_health=source_health,
        routing_summary=routing_summary,
        silence_summary=silence_summary,
        inhibition_summary=inhibition_summary,
        ownership_summary=ownership_summary,
    )
    return {
        'integration_status': integration_status,
        'source_health': source_health,
        'routing_summary': routing_summary,
        'silence_summary': silence_summary,
        'inhibition_summary': inhibition_summary,
        'ownership_summary': ownership_summary,
        'incident_readiness': incident_readiness,
        'resource_links': build_resource_links(cluster=cluster),
    }


def get_alerts_context(selection: AlertsSelection) -> dict[str, Any]:
    selected = _normalize_selection(selection)
    clusters = get_clusters_for_filter()
    cluster = get_selected_cluster(cluster_id=selected['cluster_id'])
    raw_alerts, source_status = load_alerts_by_source(
        cluster=cluster,
        source=selected['source'],
    )
    raw_anomalies, anomaly_source_status, collection_warnings = _load_anomaly_evidence(cluster)
    namespace_options = _namespace_options(
        inventory_options=get_namespace_options(cluster=cluster),
        alerts=raw_alerts,
        anomalies=raw_anomalies,
    )
    if selected['namespace'] and selected['namespace'] not in namespace_options:
        selected['namespace'] = ''

    collections = _present_collections(
        raw_alerts=raw_alerts,
        raw_anomalies=raw_anomalies,
        selected=selected,
    )
    filtered_alerts = collections['filtered_alerts']
    filtered_anomalies = collections['filtered_anomalies']
    summary = build_summary(
        alerts=filtered_alerts,
        anomalies=filtered_anomalies,
        source_status=source_status,
    )
    evidence_complete = is_alert_evidence_complete(
        source_status=source_status,
        anomaly_source_status=anomaly_source_status,
    )
    signal_overview = build_selected_cluster_signal_overview(
        cluster=cluster,
        alerts=raw_alerts,
        anomalies=raw_anomalies,
        source_status=source_status,
        evidence_complete=evidence_complete,
    )
    recommendations = _build_recommendation_context(
        alerts=filtered_alerts,
        anomalies=filtered_anomalies,
        summary=summary,
        source_status=source_status,
        collection_warnings=collection_warnings,
        anomaly_source_status=anomaly_source_status,
        signal_overview=signal_overview,
    )
    operations = _operational_context(
        cluster=cluster,
        source_status=source_status,
        anomaly_source_status=anomaly_source_status,
        raw_alerts=raw_alerts,
        raw_anomalies=raw_anomalies,
        signal_overview=signal_overview,
    )

    return {
        'clusters': clusters,
        'selected_cluster': cluster,
        'selected_cluster_id': cluster.id if cluster else '',
        'selected_source': selected['source'],
        'selected_severity': selected['severity'],
        'selected_status': selected['status'],
        'selected_namespace': selected['namespace'],
        'selected_search': selected['search'],
        'selected_alerts_page': selected['alerts_page'],
        'selected_anomalies_page': selected['anomalies_page'],
        'selected_alerts_per_page': selected['alerts_per_page'],
        'selected_anomalies_per_page': selected['anomalies_per_page'],
        'selected_per_page': selected['alerts_per_page'],
        'source_options': SOURCE_OPTIONS,
        'severity_options': SEVERITY_OPTIONS,
        'status_options': STATUS_OPTIONS,
        'per_page_options': PER_PAGE_OPTIONS,
        'namespace_options': namespace_options,
        **collections,
        'all_alerts': raw_alerts,
        'all_anomalies': raw_anomalies,
        'summary': summary,
        **_summary_aliases(summary),
        'source_status': source_status,
        'collection_warnings': collection_warnings,
        'anomaly_source_status': anomaly_source_status,
        'dependency_blocker': _dependency_blocker(
            cluster=cluster,
            source_status=source_status,
            selected_source=selected['source'],
        ),
        'selected_cluster_signal_overview': signal_overview,
        **operations,
        **recommendations,
        'generated_at': datetime.now(UTC),
    }


def get_alerts_materialization_context(query_args: Mapping[str, Any]) -> dict[str, Any]:
    """Build one unfiltered alert-source snapshot for a cluster/source pair."""
    return get_alerts_context(
        AlertsSelection(
            cluster_id=str(query_args.get('cluster_id') or '') or None,
            source=str(query_args.get('source') or 'auto'),
            alerts_per_page=50,
            anomalies_per_page=50,
        )
    )


def present_alerts_materialized_context(
    context: dict[str, Any],
    selection: AlertsSelection,
) -> dict[str, Any]:
    """Apply local record controls without changing global posture evidence."""
    presented = deepcopy(context)
    selected = _normalize_selection(selection)
    namespace_options = list(presented.get('namespace_options') or [])
    if selected['namespace'] and selected['namespace'] not in namespace_options and not selection.preserve_namespace:
        selected['namespace'] = ''

    raw_alerts = cast(list[NormalizedAlert], list(presented.get('all_alerts') or []))
    raw_anomalies = list(presented.get('all_anomalies') or [])
    collections = _present_collections(
        raw_alerts=raw_alerts,
        raw_anomalies=raw_anomalies,
        selected=selected,
    )
    source_status = cast(AlertSourceStatus, presented.get('source_status') or {})
    global_summary = presented.get('summary')
    if not isinstance(global_summary, dict):
        global_summary = build_summary(
            alerts=raw_alerts,
            anomalies=raw_anomalies,
            source_status=source_status,
        )
    record_summary = build_summary(
        alerts=collections['filtered_alerts'],
        anomalies=collections['filtered_anomalies'],
        source_status=source_status,
    )
    anomaly_source_status = presented.get('anomaly_source_status') or {}
    evidence_complete = is_alert_evidence_complete(
        source_status=source_status,
        anomaly_source_status=anomaly_source_status,
    )
    signal_overview = build_selected_cluster_signal_overview(
        cluster=presented.get('selected_cluster'),
        alerts=raw_alerts,
        anomalies=raw_anomalies,
        source_status=source_status,
        evidence_complete=evidence_complete,
    )
    recommendations = _build_recommendation_context(
        alerts=raw_alerts,
        anomalies=raw_anomalies,
        summary=global_summary,
        source_status=source_status,
        collection_warnings=list(presented.get('collection_warnings') or []),
        anomaly_source_status=anomaly_source_status,
        signal_overview=signal_overview,
    )

    presented.update(
        {
            'selected_severity': selected['severity'],
            'selected_status': selected['status'],
            'selected_namespace': selected['namespace'],
            'selected_search': selected['search'],
            'selected_alerts_page': selected['alerts_page'],
            'selected_anomalies_page': selected['anomalies_page'],
            'selected_alerts_per_page': selected['alerts_per_page'],
            'selected_anomalies_per_page': selected['anomalies_per_page'],
            'selected_per_page': selected['alerts_per_page'],
            **collections,
            'all_alerts': raw_alerts,
            'all_anomalies': raw_anomalies,
            'summary': global_summary,
            'record_summary': record_summary,
            **_summary_aliases(global_summary),
            'selected_cluster_signal_overview': signal_overview,
            **recommendations,
        }
    )
    return presented
