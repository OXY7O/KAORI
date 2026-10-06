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
    from app.intelligence.service import get_active_recommendation_findings
    from app.models.registry import RegistryAnalyticsSnapshot

    overview = build_overview()
    identities = _providers()
    latest_rows: list[dict[str, Any]] = []
    aggregate = {
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
    forecast_rows: list[dict[str, Any]] = []
    activity_rows: list[dict[str, Any]] = []
    growth_rows: list[dict[str, Any]] = []
    alert_rows: list[dict[str, Any]] = []
    alert_source_rows: list[dict[str, Any]] = []

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
        if snapshot is None or not isinstance(snapshot.payload_json, dict):
            latest_rows.append(
                {
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
            )
            continue

        payload = snapshot.payload_json
        inventory = payload.get('inventory') if isinstance(payload.get('inventory'), dict) else {}
        security = payload.get('security') if isinstance(payload.get('security'), dict) else {}
        runtime = payload.get('runtime') if isinstance(payload.get('runtime'), dict) else {}
        governance = payload.get('governance') if isinstance(payload.get('governance'), dict) else {}
        metrics = payload.get('metrics') if isinstance(payload.get('metrics'), dict) else {}
        alerts = payload.get('alerts') if isinstance(payload.get('alerts'), dict) else {}
        capacity = payload.get('capacity') if isinstance(payload.get('capacity'), dict) else {}
        growth = payload.get('growth') if isinstance(payload.get('growth'), dict) else {}

        aggregate['projects'] += int(inventory.get('projects') or 0)
        aggregate['repositories'] += int(inventory.get('repositories') or 0)
        aggregate['artifacts'] += int(inventory.get('artifacts') or 0)
        aggregate['total_size_bytes'] += int(inventory.get('total_size_bytes') or 0)
        aggregate['stale_candidates'] += int(inventory.get('stale_candidate_count') or 0)
        aggregate['scanned_artifacts'] += int(security.get('scanned_artifacts') or 0)
        aggregate['signed_artifacts'] += int(security.get('signed_artifacts') or 0)
        aggregate['sbom_artifacts'] += int(security.get('sbom_artifacts') or 0)
        aggregate['critical_findings'] += int(security.get('critical_findings') or 0)
        aggregate['high_findings'] += int(security.get('high_findings') or 0)
        aggregate['runtime_bindings'] += int(runtime.get('bindings') or 0)
        aggregate['running_artifacts'] += int(runtime.get('running_artifacts') or 0)
        aggregate['critical_runtime_artifacts'] += int(runtime.get('critical_runtime_artifacts') or 0)
        aggregate['tag_only_bindings'] += int(runtime.get('tag_only_bindings') or 0)
        aggregate['runtime_scan_gaps'] += int(runtime.get('runtime_scan_gaps') or 0)
        aggregate['unsigned_runtime_artifacts'] += int(runtime.get('unsigned_runtime_artifacts') or 0)
        aggregate['governance_projects_assessed'] += int(governance.get('projects_assessed') or 0)
        aggregate['retention_configured'] += int(governance.get('retention_configured') or 0)
        aggregate['immutability_configured'] += int(governance.get('immutability_configured') or 0)

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
            provider_pull_total = sum(
                float(value) for value in pull_activity.values() if isinstance(value, (int, float))
            )
            aggregate['pull_activity'] += provider_pull_total
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

        alert_evidence_rows = alerts.get('rows') if isinstance(alerts.get('rows'), list) else []
        normalized_alert_rows = [row for row in alert_evidence_rows if isinstance(row, dict)]
        aggregate['active_alerts'] += len(normalized_alert_rows)
        aggregate['critical_alerts'] += sum(row.get('severity') == 'critical' for row in normalized_alert_rows)
        aggregate['warning_alerts'] += sum(row.get('severity') == 'warning' for row in normalized_alert_rows)
        aggregate['info_alerts'] += sum(row.get('severity') == 'info' for row in normalized_alert_rows)
        aggregate['suppressed_alerts'] += sum(
            bool(row.get('silenced')) or bool(row.get('inhibited')) for row in normalized_alert_rows
        )
        if alerts.get('status') == 'ready':
            aggregate['alert_sources_ready'] += 1
        if alerts.get('fallback_used'):
            aggregate['alert_source_fallbacks'] += 1
        alert_source_rows.append(
            {
                'registry_name': identity.name,
                'status': str(alerts.get('status') or 'unavailable'),
                'source_label': str(alerts.get('source_label') or 'Unavailable'),
                'resolved_source': str(alerts.get('resolved_source') or 'none'),
                'fallback_used': bool(alerts.get('fallback_used')),
                'detail': str(alerts.get('detail') or ''),
            }
        )
        for row in normalized_alert_rows:
            alert_rows.append(
                {
                    **row,
                    'registry_name': identity.name,
                    'provider_key': identity.provider_key,
                }
            )

        expires_at = snapshot.expires_at
        is_stale = False
        if expires_at is not None:
            compare_expiry = expires_at if expires_at.tzinfo is not None else expires_at.replace(tzinfo=UTC)
            is_stale = datetime.now(UTC) > compare_expiry
        latest_rows.append(
            {
                'identity': identity,
                'snapshot': snapshot,
                'status_label': 'Stale Snapshot' if is_stale else 'Current Snapshot',
                'tone': 'warning' if is_stale else 'normal',
                'inventory': inventory,
                'security': security,
                'runtime': runtime,
                'governance': governance,
                'metrics': metrics,
                'alerts': alerts,
                'growth': growth,
            }
        )

        if any(
            isinstance(growth.get(key), (int, float))
            for key in ('artifact_growth_per_day', 'size_growth_bytes_per_day')
        ):
            growth_rows.append(
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

        for forecast in capacity.get('project_forecasts') or []:
            if not isinstance(forecast, dict):
                continue
            forecast_rows.append(
                {
                    'registry_name': identity.name,
                    'provider_key': identity.provider_key,
                    **forecast,
                }
            )

    recommendations = get_active_recommendation_findings(domain='registry', limit=5) if active_tab == 'insights' else []
    recommendation_rows = [
        {
            'rule_key': str(item.get('rule_key') or ''),
            'title': str(item.get('title') or 'Registry recommendation'),
            'severity': str(item.get('severity') or 'info'),
            'severity_label': str(item.get('severity') or 'info').title(),
            'summary': str(item.get('summary') or ''),
            'asset_key': str((item.get('evidence') or {}).get('asset_key') or '')
            if isinstance(item.get('evidence'), dict)
            else '',
        }
        for item in recommendations
    ]

    artifact_total = max(int(aggregate['artifacts']), 0)
    project_total = max(int(aggregate['projects']), 0)
    scan_coverage = float(aggregate['scanned_artifacts']) / artifact_total * 100.0 if artifact_total else None
    signature_coverage = float(aggregate['signed_artifacts']) / artifact_total * 100.0 if artifact_total else None
    sbom_coverage = float(aggregate['sbom_artifacts']) / artifact_total * 100.0 if artifact_total else None
    retention_coverage = float(aggregate['retention_configured']) / project_total * 100.0 if project_total else None
    immutability_coverage = (
        float(aggregate['immutability_configured']) / project_total * 100.0 if project_total else None
    )

    active_signal_count = (
        int(aggregate['critical_runtime_artifacts'])
        + int(aggregate['tag_only_bindings'])
        + int(aggregate['runtime_scan_gaps'])
        + int(aggregate['unsigned_runtime_artifacts'])
        + int(aggregate['stale_candidates'])
        + int(aggregate['metric_capability_gaps'])
    )
    risk_candidate_count = (
        int(aggregate['critical_runtime_artifacts'])
        + int(aggregate['runtime_scan_gaps'])
        + int(aggregate['unsigned_runtime_artifacts'])
        + int(aggregate['stale_candidates'])
    )
    if not latest_rows or not any(row.get('snapshot') for row in latest_rows):
        posture = {'label': 'Materialization Required', 'tone': 'warning'}
    elif aggregate['critical_runtime_artifacts']:
        posture = {'label': 'Critical Runtime Exposure', 'tone': 'critical'}
    elif active_signal_count:
        posture = {'label': 'Review Required', 'tone': 'warning'}
    else:
        posture = {'label': 'Evidence Ready', 'tone': 'normal'}

    growth_size_per_day = sum(
        float(row['size_growth_bytes_per_day'])
        for row in growth_rows
        if isinstance(row.get('size_growth_bytes_per_day'), (int, float))
    )
    growth_artifacts_per_day = sum(
        float(row['artifact_growth_per_day'])
        for row in growth_rows
        if isinstance(row.get('artifact_growth_per_day'), (int, float))
    )
    runtime_usage_percent = float(aggregate['running_artifacts']) / artifact_total * 100.0 if artifact_total else None

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
        (float(row['days_to_quota']) for row in forecast_rows if isinstance(row.get('days_to_quota'), (int, float))),
        default=None,
    )

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

    summary_cards = [
        {
            'icon': 'database',
            'label': 'Storage Footprint',
            'value': _fmt_bytes(int(aggregate['total_size_bytes'])),
            'detail': (
                f'{_fmt_bytes(round(growth_size_per_day))}/day materialized growth'
                if growth_rows
                else 'Growth requires another analytics materialization'
            ),
            'tone': 'brand',
        },
        {
            'icon': 'chart-no-axes-combined',
            'label': 'Artifact Growth',
            'value': (f'{growth_artifacts_per_day:+.1f}/day' if growth_rows else 'N/A'),
            'detail': f'{aggregate["artifacts"]} committed artifacts',
            'tone': 'info' if growth_rows else 'unknown',
        },
        {
            'icon': 'boxes',
            'label': 'Runtime-used',
            'value': str(aggregate['running_artifacts']),
            'detail': (
                f'{runtime_usage_percent:.1f}% of committed artifact estate'
                if runtime_usage_percent is not None
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

    insights: list[dict[str, str]] = []
    if growth_rows:
        insights.append(
            {
                'icon': 'trending-up',
                'title': 'Registry growth is materialized',
                'detail': (
                    f'{growth_artifacts_per_day:+.1f} artifacts/day and '
                    f'{_fmt_bytes(round(growth_size_per_day))}/day across current providers.'
                ),
                'tone': 'info',
            }
        )
    if aggregate['critical_runtime_artifacts']:
        insights.append(
            {
                'icon': 'shield-alert',
                'title': 'Critical findings intersect runtime usage',
                'detail': (
                    f'{aggregate["critical_runtime_artifacts"]} running artifacts carry '
                    'critical security evidence and require Intelligence review.'
                ),
                'tone': 'critical',
            }
        )
    if aggregate['stale_candidates']:
        insights.append(
            {
                'icon': 'archive',
                'title': 'Stale inventory candidates exist',
                'detail': (
                    f'{aggregate["stale_candidates"]} artifacts are review candidates only; '
                    'Analytics never performs automatic cleanup.'
                ),
                'tone': 'warning',
            }
        )
    if aggregate['runtime_scan_gaps']:
        insights.append(
            {
                'icon': 'scan-search',
                'title': 'Runtime scan evidence is incomplete',
                'detail': (
                    f'{aggregate["runtime_scan_gaps"]} running artifacts have no normalized successful scan evidence.'
                ),
                'tone': 'warning',
            }
        )
    if not insights:
        insights.append(
            {
                'icon': 'circle-check',
                'title': 'No derived review signal',
                'detail': 'Current committed analytics evidence has no derived review signal.',
                'tone': 'normal',
            }
        )

    for row in growth_rows:
        size_growth = row.get('size_growth_bytes_per_day')
        size_delta = row.get('size_delta_bytes')
        row['size_growth_display'] = (
            f'{_fmt_bytes(round(float(size_growth)))}/day' if isinstance(size_growth, (int, float)) else 'N/A'
        )
        row['size_delta_display'] = (
            _fmt_bytes(round(float(size_delta))) if isinstance(size_delta, (int, float)) else 'N/A'
        )
        artifact_growth = row.get('artifact_growth_per_day')
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
        row['days_to_quota_display'] = f'{float(days):.1f} days' if isinstance(days, (int, float)) else 'No forecast'
        row['utilization_display'] = f'{float(utilization):.1f}%' if isinstance(utilization, (int, float)) else 'N/A'

    severity_value = alert_severity if alert_severity in {'all', 'critical', 'warning', 'info', 'unknown'} else 'all'
    state_value = alert_state if alert_state in {'all', 'firing', 'pending', 'suppressed', 'resolved'} else 'all'
    source_value = alert_source if alert_source in {'all', 'alertmanager', 'metrics_source'} else 'all'
    search_value = alert_search.strip().casefold()
    filtered_alert_rows = []
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
        filtered_alert_rows.append({**row, 'effective_state': effective_state})
    alert_page_rows, alert_pagination = paginate_sequence(
        filtered_alert_rows,
        page=alert_page,
        per_page=alert_per_page if alert_per_page in {5, 10, 25, 50} else 5,
    )

    return {
        'setup': overview['setup'],
        'provider_count': len(identities),
        'snapshot_count': sum(bool(row.get('snapshot')) for row in latest_rows),
        'aggregate': aggregate,
        'latest_rows': latest_rows,
        'active_tab': normalized_tab,
        'summary_cards': summary_cards,
        'capacity_outlook': {
            'nearest_quota_days': nearest_quota_days,
            'highest_utilization': highest_utilization,
            'growth_bytes_per_day': growth_size_per_day if growth_rows else None,
            'growth_display': (f'{_fmt_bytes(round(growth_size_per_day))}/day' if growth_rows else 'N/A'),
            'quota_headroom_bytes': quota_headroom,
            'quota_headroom_display': (_fmt_bytes(round(quota_headroom)) if quota_headroom is not None else 'N/A'),
        },
        'insights': insights[:5],
        'coverage': {
            'scan': scan_coverage,
            'signature': signature_coverage,
            'sbom': sbom_coverage,
            'retention': retention_coverage,
            'immutability': immutability_coverage,
        },
        'activity_rows': sorted(
            activity_rows,
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
        'alert_source_rows': alert_source_rows,
        'alert_pagination': alert_pagination,
        'alert_filters': {
            'search': alert_search,
            'severity': severity_value,
            'state': state_value,
            'source': source_value,
        },
        'recommendations': recommendation_rows,
        'recommendation_count': len(recommendation_rows),
        'active_signal_count': active_signal_count,
        'posture': posture,
    }
