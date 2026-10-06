from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func

from app.artifact_registry.presentation_common import _fmt_bytes, _providers
from app.artifact_registry.presentation_overview import build_overview
from app.common.pagination import paginate_sequence
from app.models.registry import RegistryAnalyticsSnapshot

def build_analytics_shell(
    *,
    active_tab: str = 'growth',
    alert_search: str = '',
    alert_severity: str = 'all',
    alert_state: str = 'all',
    alert_source: str = 'all',
    alert_page: int = 1,
    alert_per_page: int = 5,
) -> dict[str, Any]:
    overview = build_overview()
    normalized_tab = (
        active_tab
        if active_tab
        in {
            'growth',
            'capacity',
            'usage',
            'risk',
            'governance',
            'alerts',
            'insights',
        }
        else 'growth'
    )
    provider_count = int(overview['provider_count'])
    snapshot_count = (
        RegistryAnalyticsSnapshot.query.with_entities(
            func.count(func.distinct(RegistryAnalyticsSnapshot.integration_instance_id))
        )
        .filter(RegistryAnalyticsSnapshot.status == 'ready')
        .scalar()
        or 0
    )
    latest_generated_at = (
        RegistryAnalyticsSnapshot.query.with_entities(func.max(RegistryAnalyticsSnapshot.generated_at))
        .filter(RegistryAnalyticsSnapshot.status == 'ready')
        .scalar()
    )
    return {
        'setup': overview['setup'],
        'provider_count': provider_count,
        'snapshot_count': int(snapshot_count),
        'latest_generated_at': latest_generated_at,
        'active_tab': normalized_tab,
        'alert_filters': {
            'search': alert_search,
            'severity': alert_severity,
            'state': alert_state,
            'source': alert_source,
            'page': alert_page,
            'per_page': alert_per_page,
        },
    }


def _analytics_aggregate() -> dict[str, Any]:
    return {
        'projects': 0,
        'repositories': 0,
        'artifacts': 0,
        'total_size_bytes': 0,
        'stale_candidates': 0,
        'scanned_artifacts': 0,
        'signed_artifacts': 0,
        'sbom_artifacts': 0,
        'critical_findings': 0,
        'high_findings': 0,
        'runtime_bindings': 0,
        'running_artifacts': 0,
        'critical_runtime_artifacts': 0,
        'tag_only_bindings': 0,
        'runtime_scan_gaps': 0,
        'unsigned_runtime_artifacts': 0,
        'governance_projects_assessed': 0,
        'retention_configured': 0,
        'immutability_configured': 0,
        'metrics_ready': 0,
        'healthy_providers': 0,
        'component_up_providers': 0,
        'request_rate_per_second': 0.0,
        'backend_request_rate_per_second': 0.0,
        'inflight_requests': 0.0,
        'task_queue_size': 0.0,
        'pull_activity': 0.0,
        'metric_capability_gaps': 0,
        'active_alerts': 0,
        'critical_alerts': 0,
        'warning_alerts': 0,
        'info_alerts': 0,
        'suppressed_alerts': 0,
        'alert_sources_ready': 0,
        'alert_source_fallbacks': 0,
    }


def _analytics_sections(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    keys = ('inventory', 'security', 'runtime', 'governance', 'metrics', 'alerts', 'capacity', 'growth')
    return {
        key: value if isinstance((value := payload.get(key)), dict) else {}
        for key in keys
    }


def _accumulate_domain_counts(aggregate: dict[str, Any], sections: dict[str, dict[str, Any]]) -> None:
    inventory = sections['inventory']
    security = sections['security']
    runtime = sections['runtime']
    governance = sections['governance']
    mappings = {
        'projects': (inventory, 'projects'),
        'repositories': (inventory, 'repositories'),
        'artifacts': (inventory, 'artifacts'),
        'total_size_bytes': (inventory, 'total_size_bytes'),
        'stale_candidates': (inventory, 'stale_candidate_count'),
        'scanned_artifacts': (security, 'scanned_artifacts'),
        'signed_artifacts': (security, 'signed_artifacts'),
        'sbom_artifacts': (security, 'sbom_artifacts'),
        'critical_findings': (security, 'critical_findings'),
        'high_findings': (security, 'high_findings'),
        'runtime_bindings': (runtime, 'bindings'),
        'running_artifacts': (runtime, 'running_artifacts'),
        'critical_runtime_artifacts': (runtime, 'critical_runtime_artifacts'),
        'tag_only_bindings': (runtime, 'tag_only_bindings'),
        'runtime_scan_gaps': (runtime, 'runtime_scan_gaps'),
        'unsigned_runtime_artifacts': (runtime, 'unsigned_runtime_artifacts'),
        'governance_projects_assessed': (governance, 'projects_assessed'),
        'retention_configured': (governance, 'retention_configured'),
        'immutability_configured': (governance, 'immutability_configured'),
    }
    for aggregate_key, (source, source_key) in mappings.items():
        aggregate[aggregate_key] += int(source.get(source_key) or 0)


def _accumulate_metrics(
    aggregate: dict[str, Any],
    metrics: dict[str, Any],
    *,
    identity: Any,
    activity_rows: list[dict[str, Any]],
) -> None:
    metrics_ready = metrics.get('status') == 'ready'
    aggregate['metrics_ready'] += int(metrics_ready)
    aggregate['healthy_providers'] += int(
        metrics_ready
        and isinstance(metrics.get('provider_health_value'), (int, float))
        and float(metrics.get('provider_health_value')) > 0
    )
    aggregate['component_up_providers'] += int(
        metrics_ready
        and isinstance(metrics.get('component_up_value'), (int, float))
        and float(metrics.get('component_up_value')) > 0
    )
    for aggregate_key, metric_key in (
        ('request_rate_per_second', 'request_rate_per_second'),
        ('backend_request_rate_per_second', 'backend_request_rate_per_second'),
        ('inflight_requests', 'inflight_requests'),
        ('task_queue_size', 'task_queue_size'),
    ):
        raw_value = metrics.get(metric_key)
        if isinstance(raw_value, (int, float)):
            aggregate[aggregate_key] += float(raw_value)

    pull_activity = metrics.get('project_pull_count')
    if isinstance(pull_activity, dict):
        aggregate['pull_activity'] += sum(
            float(value) for value in pull_activity.values() if isinstance(value, (int, float))
        )
        for project_name, raw_value in pull_activity.items():
            if isinstance(raw_value, (int, float)):
                activity_rows.append(
                    {
                        'registry_name': identity.name,
                        'provider_key': identity.provider_key,
                        'project_name': str(project_name),
                        'pull_count': float(raw_value),
                    }
                )
    capability_gaps = metrics.get('capability_gaps')
    if isinstance(capability_gaps, dict):
        aggregate['metric_capability_gaps'] += len(capability_gaps)


def _accumulate_alerts(
    aggregate: dict[str, Any],
    alerts: dict[str, Any],
    *,
    identity: Any,
    alert_rows: list[dict[str, Any]],
    source_rows: list[dict[str, Any]],
) -> None:
    evidence_rows = alerts.get('rows') if isinstance(alerts.get('rows'), list) else []
    normalized_rows = [row for row in evidence_rows if isinstance(row, dict)]
    aggregate['active_alerts'] += len(normalized_rows)
    aggregate['critical_alerts'] += sum(row.get('severity') == 'critical' for row in normalized_rows)
    aggregate['warning_alerts'] += sum(row.get('severity') == 'warning' for row in normalized_rows)
    aggregate['info_alerts'] += sum(row.get('severity') == 'info' for row in normalized_rows)
    aggregate['suppressed_alerts'] += sum(
        bool(row.get('silenced')) or bool(row.get('inhibited')) for row in normalized_rows
    )
    aggregate['alert_sources_ready'] += int(alerts.get('status') == 'ready')
    aggregate['alert_source_fallbacks'] += int(bool(alerts.get('fallback_used')))
    source_rows.append(
        {
            'registry_name': identity.name,
            'status': str(alerts.get('status') or 'unavailable'),
            'source_label': str(alerts.get('source_label') or 'Unavailable'),
            'resolved_source': str(alerts.get('resolved_source') or 'none'),
            'fallback_used': bool(alerts.get('fallback_used')),
            'detail': str(alerts.get('detail') or ''),
        }
    )
    alert_rows.extend(
        {**row, 'registry_name': identity.name, 'provider_key': identity.provider_key}
        for row in normalized_rows
    )


def _analytics_snapshot_view(identity: Any, snapshot: RegistryAnalyticsSnapshot | None) -> dict[str, Any]:
    if snapshot is None or not isinstance(snapshot.payload_json, dict):
        return {
            'identity': identity,
            'snapshot': None,
            'status_label': 'Not Materialized',
            'tone': 'unknown',
            'inventory': {},
            'security': {},
            'runtime': {},
            'governance': {},
            'metrics': {},
            'alerts': {},
            'growth': {},
        }
    sections = _analytics_sections(snapshot.payload_json)
    expires_at = snapshot.expires_at
    is_stale = False
    if expires_at is not None:
        compare_expiry = expires_at if expires_at.tzinfo is not None else expires_at.replace(tzinfo=UTC)
        is_stale = datetime.now(UTC) > compare_expiry
    return {
        'identity': identity,
        'snapshot': snapshot,
        'status_label': 'Stale Snapshot' if is_stale else 'Current Snapshot',
        'tone': 'warning' if is_stale else 'normal',
        'inventory': sections['inventory'],
        'security': sections['security'],
        'runtime': sections['runtime'],
        'governance': sections['governance'],
        'metrics': sections['metrics'],
        'alerts': sections['alerts'],
        'growth': sections['growth'],
    }


def _collect_analytics_rows(identities: list[Any]) -> dict[str, Any]:
    bundle: dict[str, Any] = {
        'aggregate': _analytics_aggregate(),
        'latest_rows': [],
        'forecast_rows': [],
        'activity_rows': [],
        'growth_rows': [],
        'alert_rows': [],
        'alert_source_rows': [],
    }
    for identity in identities:
        snapshot = (
            RegistryAnalyticsSnapshot.query.filter_by(
                integration_instance_id=identity.id,
                status='ready',
            )
            .order_by(
                RegistryAnalyticsSnapshot.generated_at.desc(),
                RegistryAnalyticsSnapshot.id.desc(),
            )
            .first()
        )
        view = _analytics_snapshot_view(identity, snapshot)
        bundle['latest_rows'].append(view)
        if snapshot is None or not isinstance(snapshot.payload_json, dict):
            continue
        sections = _analytics_sections(snapshot.payload_json)
        _accumulate_domain_counts(bundle['aggregate'], sections)
        _accumulate_metrics(
            bundle['aggregate'],
            sections['metrics'],
            identity=identity,
            activity_rows=bundle['activity_rows'],
        )
        _accumulate_alerts(
            bundle['aggregate'],
            sections['alerts'],
            identity=identity,
            alert_rows=bundle['alert_rows'],
            source_rows=bundle['alert_source_rows'],
        )
        growth = sections['growth']
        if any(
            isinstance(growth.get(key), (int, float))
            for key in ('artifact_growth_per_day', 'size_growth_bytes_per_day')
        ):
            bundle['growth_rows'].append(
                {
                    'registry_name': identity.name,
                    'provider_key': identity.provider_key,
                    'artifact_growth_per_day': growth.get('artifact_growth_per_day'),
                    'size_growth_bytes_per_day': growth.get('size_growth_bytes_per_day'),
                    'artifact_delta': growth.get('artifact_delta'),
                    'size_delta_bytes': growth.get('size_delta_bytes'),
                    'elapsed_days': growth.get('elapsed_days'),
                }
            )
        for forecast in sections['capacity'].get('project_forecasts') or []:
            if isinstance(forecast, dict):
                bundle['forecast_rows'].append(
                    {'registry_name': identity.name, 'provider_key': identity.provider_key, **forecast}
                )
    return bundle


def _analytics_recommendations(active_tab: str) -> list[dict[str, str]]:
    from app.intelligence.service import get_active_recommendation_findings

    findings = get_active_recommendation_findings(domain='registry', limit=5) if active_tab == 'insights' else []
    return [
        {
            'rule_key': str(item.get('rule_key') or ''),
            'title': str(item.get('title') or 'Registry recommendation'),
            'severity': str(item.get('severity') or 'info'),
            'severity_label': str(item.get('severity') or 'info').title(),
            'summary': str(item.get('summary') or ''),
            'asset_key': (
                str((item.get('evidence') or {}).get('asset_key') or '')
                if isinstance(item.get('evidence'), dict)
                else ''
            ),
        }
        for item in findings
    ]


def _analytics_coverage(aggregate: dict[str, Any]) -> dict[str, float | None]:
    artifact_total = max(int(aggregate['artifacts']), 0)
    project_total = max(int(aggregate['projects']), 0)
    return {
        'scan': float(aggregate['scanned_artifacts']) / artifact_total * 100.0 if artifact_total else None,
        'signature': float(aggregate['signed_artifacts']) / artifact_total * 100.0 if artifact_total else None,
        'sbom': float(aggregate['sbom_artifacts']) / artifact_total * 100.0 if artifact_total else None,
        'retention': float(aggregate['retention_configured']) / project_total * 100.0 if project_total else None,
        'immutability': (
            float(aggregate['immutability_configured']) / project_total * 100.0 if project_total else None
        ),
    }


def _analytics_signal_summary(
    aggregate: dict[str, Any],
    latest_rows: list[dict[str, Any]],
) -> tuple[int, int, dict[str, str]]:
    active_signal_count = sum(
        int(aggregate[key])
        for key in (
            'critical_runtime_artifacts',
            'tag_only_bindings',
            'runtime_scan_gaps',
            'unsigned_runtime_artifacts',
            'stale_candidates',
            'metric_capability_gaps',
        )
    )
    risk_candidate_count = sum(
        int(aggregate[key])
        for key in (
            'critical_runtime_artifacts',
            'runtime_scan_gaps',
            'unsigned_runtime_artifacts',
            'stale_candidates',
        )
    )
    if not latest_rows or not any(row.get('snapshot') for row in latest_rows):
        posture = {'label': 'Materialization Required', 'tone': 'warning'}
    elif aggregate['critical_runtime_artifacts']:
        posture = {'label': 'Critical Runtime Exposure', 'tone': 'critical'}
    elif active_signal_count:
        posture = {'label': 'Review Required', 'tone': 'warning'}
    else:
        posture = {'label': 'Evidence Ready', 'tone': 'normal'}
    return active_signal_count, risk_candidate_count, posture


def _analytics_growth_summary(
    aggregate: dict[str, Any],
    growth_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    size_per_day = sum(
        float(row['size_growth_bytes_per_day'])
        for row in growth_rows
        if isinstance(row.get('size_growth_bytes_per_day'), (int, float))
    )
    artifacts_per_day = sum(
        float(row['artifact_growth_per_day'])
        for row in growth_rows
        if isinstance(row.get('artifact_growth_per_day'), (int, float))
    )
    artifact_total = max(int(aggregate['artifacts']), 0)
    return {
        'size_per_day': size_per_day,
        'artifacts_per_day': artifacts_per_day,
        'runtime_usage_percent': (
            float(aggregate['running_artifacts']) / artifact_total * 100.0 if artifact_total else None
        ),
    }


def _analytics_capacity_outlook(
    forecast_rows: list[dict[str, Any]],
    *,
    growth_rows: list[dict[str, Any]],
    growth: dict[str, Any],
) -> dict[str, Any]:
    quota_rows = [
        row
        for row in forecast_rows
        if isinstance(row.get('usage_bytes'), (int, float))
        and isinstance(row.get('quota_bytes'), (int, float))
        and float(row.get('quota_bytes') or 0) > 0
    ]
    quota_usage = sum(float(row['usage_bytes']) for row in quota_rows)
    quota_total = sum(float(row['quota_bytes']) for row in quota_rows)
    quota_headroom = max(quota_total - quota_usage, 0.0) if quota_total else None
    highest_utilization = max(
        (
            float(row['utilization_percent'])
            for row in forecast_rows
            if isinstance(row.get('utilization_percent'), (int, float))
        ),
        default=None,
    )
    nearest_quota_days = min(
        (
            float(row['days_to_quota'])
            for row in forecast_rows
            if isinstance(row.get('days_to_quota'), (int, float))
        ),
        default=None,
    )
    return {
        'nearest_quota_days': nearest_quota_days,
        'highest_utilization': highest_utilization,
        'growth_bytes_per_day': growth['size_per_day'] if growth_rows else None,
        'growth_display': (
            f'{_fmt_bytes(round(growth["size_per_day"]))}/day' if growth_rows else 'N/A'
        ),
        'quota_headroom_bytes': quota_headroom,
        'quota_headroom_display': _fmt_bytes(round(quota_headroom)) if quota_headroom is not None else 'N/A',
    }


def _analytics_summary_cards(
    aggregate: dict[str, Any],
    *,
    growth_rows: list[dict[str, Any]],
    growth: dict[str, Any],
    risk_candidate_count: int,
) -> list[dict[str, Any]]:
    return [
        {
            'icon': 'database',
            'label': 'Storage Footprint',
            'value': _fmt_bytes(int(aggregate['total_size_bytes'])),
            'detail': (
                f'{_fmt_bytes(round(growth["size_per_day"]))}/day materialized growth'
                if growth_rows
                else 'Growth requires another analytics materialization'
            ),
            'tone': 'brand',
        },
        {
            'icon': 'chart-no-axes-combined',
            'label': 'Artifact Growth',
            'value': f'{growth["artifacts_per_day"]:+.1f}/day' if growth_rows else 'N/A',
            'detail': f'{aggregate["artifacts"]} committed artifacts',
            'tone': 'info' if growth_rows else 'unknown',
        },
        {
            'icon': 'boxes',
            'label': 'Runtime-used',
            'value': str(aggregate['running_artifacts']),
            'detail': (
                f'{growth["runtime_usage_percent"]:.1f}% of committed artifact estate'
                if growth['runtime_usage_percent'] is not None
                else 'No committed artifact denominator'
            ),
            'tone': 'normal' if aggregate['running_artifacts'] else 'unknown',
        },
        {
            'icon': 'triangle-alert',
            'label': 'Risk Candidates',
            'value': str(risk_candidate_count),
            'detail': 'Cross-domain review signals; candidates may overlap',
            'tone': 'warning' if risk_candidate_count else 'normal',
        },
    ]


def _analytics_insights(
    aggregate: dict[str, Any],
    *,
    growth_rows: list[dict[str, Any]],
    growth: dict[str, Any],
) -> list[dict[str, str]]:
    insights: list[dict[str, str]] = []
    candidates = (
        (
            bool(growth_rows),
            {
                'icon': 'trending-up',
                'title': 'Registry growth is materialized',
                'detail': (
                    f'{growth["artifacts_per_day"]:+.1f} artifacts/day and '
                    f'{_fmt_bytes(round(growth["size_per_day"]))}/day across current providers.'
                ),
                'tone': 'info',
            },
        ),
        (
            bool(aggregate['critical_runtime_artifacts']),
            {
                'icon': 'shield-alert',
                'title': 'Critical findings intersect runtime usage',
                'detail': (
                    f'{aggregate["critical_runtime_artifacts"]} running artifacts carry '
                    'critical security evidence and require Intelligence review.'
                ),
                'tone': 'critical',
            },
        ),
        (
            bool(aggregate['stale_candidates']),
            {
                'icon': 'archive',
                'title': 'Stale inventory candidates exist',
                'detail': (
                    f'{aggregate["stale_candidates"]} artifacts are review candidates only; '
                    'Analytics never performs automatic cleanup.'
                ),
                'tone': 'warning',
            },
        ),
        (
            bool(aggregate['runtime_scan_gaps']),
            {
                'icon': 'scan-search',
                'title': 'Runtime scan evidence is incomplete',
                'detail': (
                    f'{aggregate["runtime_scan_gaps"]} running artifacts have no normalized successful scan evidence.'
                ),
                'tone': 'warning',
            },
        ),
    )
    insights.extend(item for enabled, item in candidates if enabled)
    return insights or [
        {
            'icon': 'circle-check',
            'title': 'No derived review signal',
            'detail': 'Current committed analytics evidence has no derived review signal.',
            'tone': 'normal',
        }
    ]


def _decorate_analytics_rows(
    growth_rows: list[dict[str, Any]],
    forecast_rows: list[dict[str, Any]],
) -> None:
    for row in growth_rows:
        size_growth = row.get('size_growth_bytes_per_day')
        size_delta = row.get('size_delta_bytes')
        artifact_growth = row.get('artifact_growth_per_day')
        row['size_growth_display'] = (
            f'{_fmt_bytes(round(float(size_growth)))}/day' if isinstance(size_growth, (int, float)) else 'N/A'
        )
        row['size_delta_display'] = (
            _fmt_bytes(round(float(size_delta))) if isinstance(size_delta, (int, float)) else 'N/A'
        )
        row['artifact_growth_display'] = (
            f'{float(artifact_growth):+.1f}/day' if isinstance(artifact_growth, (int, float)) else 'N/A'
        )
    for row in forecast_rows:
        usage = row.get('usage_bytes')
        quota = row.get('quota_bytes')
        growth = row.get('growth_bytes_per_day')
        days = row.get('days_to_quota')
        utilization = row.get('utilization_percent')
        row['usage_display'] = _fmt_bytes(round(float(usage))) if isinstance(usage, (int, float)) else 'N/A'
        row['quota_display'] = _fmt_bytes(round(float(quota))) if isinstance(quota, (int, float)) else 'N/A'
        row['growth_display'] = (
            f'{_fmt_bytes(round(float(growth)))}/day' if isinstance(growth, (int, float)) else 'Insufficient history'
        )
        row['days_to_quota_display'] = (
            f'{float(days):.1f} days' if isinstance(days, (int, float)) else 'No forecast'
        )
        row['utilization_display'] = (
            f'{float(utilization):.1f}%' if isinstance(utilization, (int, float)) else 'N/A'
        )


def _analytics_alert_page(
    alert_rows: list[dict[str, Any]],
    *,
    search: str,
    severity: str,
    state: str,
    source: str,
    page: int,
    per_page: int,
) -> tuple[list[dict[str, Any]], Any, dict[str, str]]:
    severity_value = severity if severity in {'all', 'critical', 'warning', 'info', 'unknown'} else 'all'
    state_value = state if state in {'all', 'firing', 'pending', 'suppressed', 'resolved'} else 'all'
    source_value = source if source in {'all', 'alertmanager', 'metrics_source'} else 'all'
    search_value = search.strip().casefold()
    filtered_rows: list[dict[str, Any]] = []
    for row in alert_rows:
        effective_state = 'suppressed' if row.get('silenced') or row.get('inhibited') else str(row.get('state') or '')
        if severity_value != 'all' and row.get('severity') != severity_value:
            continue
        if state_value != 'all' and effective_state != state_value:
            continue
        if source_value != 'all' and row.get('source_key') != source_value:
            continue
        if search_value:
            haystack = ' '.join(
                str(row.get(key) or '') for key in ('name', 'target', 'summary', 'registry_name', 'source')
            ).casefold()
            if search_value not in haystack:
                continue
        filtered_rows.append({**row, 'effective_state': effective_state})
    page_rows, pagination = paginate_sequence(
        filtered_rows,
        page=page,
        per_page=per_page if per_page in {5, 10, 25, 50} else 5,
    )
    return page_rows, pagination, {
        'search': search,
        'severity': severity_value,
        'state': state_value,
        'source': source_value,
    }


def build_analytics(
    *,
    active_tab: str = 'growth',
    alert_search: str = '',
    alert_severity: str = 'all',
    alert_state: str = 'all',
    alert_source: str = 'all',
    alert_page: int = 1,
    alert_per_page: int = 5,
) -> dict[str, Any]:
    overview = build_overview()
    identities = _providers()
    bundle = _collect_analytics_rows(identities)
    aggregate = bundle['aggregate']
    growth_rows = bundle['growth_rows']
    forecast_rows = bundle['forecast_rows']
    _decorate_analytics_rows(growth_rows, forecast_rows)
    coverage = _analytics_coverage(aggregate)
    active_signal_count, risk_candidate_count, posture = _analytics_signal_summary(
        aggregate,
        bundle['latest_rows'],
    )
    growth = _analytics_growth_summary(aggregate, growth_rows)
    alert_page_rows, alert_pagination, alert_filters = _analytics_alert_page(
        bundle['alert_rows'],
        search=alert_search,
        severity=alert_severity,
        state=alert_state,
        source=alert_source,
        page=alert_page,
        per_page=alert_per_page,
    )
    normalized_tab = (
        active_tab
        if active_tab in {'growth', 'capacity', 'usage', 'risk', 'governance', 'alerts', 'insights'}
        else 'growth'
    )
    recommendation_rows = _analytics_recommendations(active_tab)
    return {
        'setup': overview['setup'],
        'provider_count': len(identities),
        'snapshot_count': sum(bool(row.get('snapshot')) for row in bundle['latest_rows']),
        'aggregate': aggregate,
        'latest_rows': bundle['latest_rows'],
        'active_tab': normalized_tab,
        'summary_cards': _analytics_summary_cards(
            aggregate,
            growth_rows=growth_rows,
            growth=growth,
            risk_candidate_count=risk_candidate_count,
        ),
        'capacity_outlook': _analytics_capacity_outlook(
            forecast_rows,
            growth_rows=growth_rows,
            growth=growth,
        ),
        'insights': _analytics_insights(aggregate, growth_rows=growth_rows, growth=growth)[:5],
        'coverage': coverage,
        'activity_rows': sorted(
            bundle['activity_rows'],
            key=lambda row: (-float(row['pull_count']), row['project_name'].casefold()),
        )[:5],
        'growth_rows': sorted(
            growth_rows,
            key=lambda row: (
                -(
                    float(row['size_growth_bytes_per_day'])
                    if isinstance(row.get('size_growth_bytes_per_day'), (int, float))
                    else float('-inf')
                ),
                row['registry_name'].casefold(),
            ),
        )[:5],
        'forecast_rows': sorted(
            forecast_rows,
            key=lambda row: (
                row.get('days_to_quota') is None,
                float(row.get('days_to_quota') or 1e18),
            ),
        ),
        'alert_rows': alert_page_rows,
        'alert_source_rows': bundle['alert_source_rows'],
        'alert_pagination': alert_pagination,
        'alert_filters': alert_filters,
        'recommendations': recommendation_rows,
        'recommendation_count': len(recommendation_rows),
        'active_signal_count': active_signal_count,
        'posture': posture,
    }
