from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, overload

from sqlalchemy import or_

from app.common.pagination import paginate_sequence
from app.dashboards.common.operational import normalize_operational_tab
from app.intelligence.alert_intelligence.dashboard_cases import active_recommendation_alert_cases
from app.intelligence.catalog import INTELLIGENCE_CATALOG
from app.intelligence.dashboard_recommendations import get_dashboard_recommendation_findings
from app.models.integration import IntegrationInstance
from app.models.registry import (
    RegistryAnalyticsSnapshot,
    RegistryArtifact,
    RegistryCollectionState,
    RegistryGovernanceState,
    RegistryProject,
    RegistryRepository,
    RegistryTag,
)
from app.models.report import Report, ReportSchedule, ReportTemplate
from app.reports.catalog import REPORT_TYPE_SPECS

FRESHNESS_HOURS = 24


def _fmt_bytes(value: int | None) -> str:
    if value is None:
        return 'Not Collected'
    size = float(max(value, 0))
    units = ('B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB')
    index = 0
    while size >= 1024 and index < len(units) - 1:
        size /= 1024
        index += 1
    return f'{int(size)} B' if index == 0 else f'{size:.2f} {units[index]}'


def _providers() -> list[IntegrationInstance]:
    return (
        IntegrationInstance.query.filter(
            IntegrationInstance.integration_type == 'registry',
            IntegrationInstance.lifecycle_status == 'active',
        )
        .order_by(IntegrationInstance.name.asc())
        .all()
    )


@overload
def _aware_datetime(value: None) -> None: ...


@overload
def _aware_datetime(value: datetime) -> datetime: ...


def _aware_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _human_time(value: datetime | None) -> str:
    resolved = _aware_datetime(value)
    if resolved is None:
        return 'Not Collected'
    seconds = max(int((datetime.now(UTC) - resolved).total_seconds()), 0)
    if seconds < 60:
        return 'Just now'
    minutes = seconds // 60
    if minutes < 60:
        return f'{minutes}m ago'
    hours = minutes // 60
    if hours < 24:
        return f'{hours}h ago'
    return f'{hours // 24}d ago'


def _freshness_value(value: datetime | None, *, missing: str) -> str:
    return f'Updated {_human_time(value)}' if value is not None else missing


def _state_view(state: RegistryCollectionState | RegistryGovernanceState | None) -> dict[str, Any]:
    if state is None or state.last_committed_at is None:
        return {
            'status': 'not_collected',
            'label': 'Not Collected',
            'tone': 'unknown',
            'observed_at': None,
            'committed_at': None,
            'is_stale': False,
        }
    committed_at = _aware_datetime(state.last_committed_at)
    refresh_failed = bool(state.last_error)
    stale = bool(committed_at is not None and committed_at < datetime.now(UTC) - timedelta(hours=FRESHNESS_HOURS))
    return {
        'status': state.status,
        'label': 'Stale Snapshot' if stale else 'Current Snapshot',
        'tone': 'warning' if stale or refresh_failed else 'normal',
        'observed_at': state.last_observed_at,
        'committed_at': state.last_committed_at,
        'is_stale': stale,
        'refresh_failed': refresh_failed,
    }


def _analytics_snapshot_view(snapshot: RegistryAnalyticsSnapshot | None) -> dict[str, Any]:
    if snapshot is None:
        return {
            'status': 'not_materialized',
            'label': 'Not Materialized',
            'tone': 'unknown',
            'generated_at': None,
            'is_stale': False,
        }
    expires_at = _aware_datetime(snapshot.expires_at)
    stale = bool(expires_at is not None and datetime.now(UTC) > expires_at)
    return {
        'status': snapshot.status,
        'label': 'Stale Snapshot' if stale else 'Current Snapshot',
        'tone': 'warning' if stale else 'normal',
        'generated_at': snapshot.generated_at,
        'is_stale': stale,
    }


def _analytics_payload(snapshot: RegistryAnalyticsSnapshot | None) -> dict[str, Any]:
    return dict(snapshot.payload_json) if snapshot is not None and isinstance(snapshot.payload_json, dict) else {}


def _collect_registry_capacity_analytics(
    *,
    scoped_providers: list[IntegrationInstance],
    analytics_by_provider: dict[int, RegistryAnalyticsSnapshot | None],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    provider_names = {int(provider.id): provider.name for provider in scoped_providers}
    project_forecasts: list[dict[str, Any]] = []
    growth = {
        'size_per_day': 0.0,
        'artifacts_per_day': 0.0,
        'observed': False,
        'analytics_count': 0,
    }
    for provider_id, snapshot in analytics_by_provider.items():
        if snapshot is None:
            continue
        growth['analytics_count'] += 1
        payload = _analytics_payload(snapshot)
        raw_growth_payload = payload.get('growth')
        growth_payload = raw_growth_payload if isinstance(raw_growth_payload, dict) else {}
        size_growth = growth_payload.get('size_growth_bytes_per_day')
        artifact_growth = growth_payload.get('artifact_growth_per_day')
        if isinstance(size_growth, (int, float)):
            growth['size_per_day'] += float(size_growth)
            growth['observed'] = True
        if isinstance(artifact_growth, (int, float)):
            growth['artifacts_per_day'] += float(artifact_growth)
            growth['observed'] = True

        raw_capacity = payload.get('capacity')
        capacity = raw_capacity if isinstance(raw_capacity, dict) else {}
        rows = capacity.get('project_forecasts')
        if not isinstance(rows, list):
            continue
        for raw in rows:
            if not isinstance(raw, dict):
                continue
            usage = raw.get('usage_bytes')
            quota = raw.get('quota_bytes')
            utilization = raw.get('utilization_percent')
            days = raw.get('days_to_quota')
            growth_bytes = raw.get('growth_bytes_per_day')
            project_forecasts.append(
                {
                    'provider_id': provider_id,
                    'provider_name': provider_names.get(provider_id, f'Registry {provider_id}'),
                    'project_name': str(raw.get('project_name') or 'Registry Project'),
                    'usage_bytes': float(usage) if isinstance(usage, (int, float)) else None,
                    'quota_bytes': float(quota) if isinstance(quota, (int, float)) else None,
                    'utilization_percent': float(utilization) if isinstance(utilization, (int, float)) else None,
                    'growth_bytes_per_day': (float(growth_bytes) if isinstance(growth_bytes, (int, float)) else None),
                    'days_to_quota': float(days) if isinstance(days, (int, float)) else None,
                }
            )
    return project_forecasts, growth


def _registry_capacity_posture(project_forecasts: list[dict[str, Any]]) -> dict[str, Any]:
    quota_rows = [
        item
        for item in project_forecasts
        if item['usage_bytes'] is not None and item['quota_bytes'] is not None and item['quota_bytes'] > 0
    ]
    total_usage = sum(float(item['usage_bytes']) for item in quota_rows)
    total_quota = sum(float(item['quota_bytes']) for item in quota_rows)
    quota_utilization = (total_usage / total_quota * 100.0) if total_quota > 0 else None
    quota_headroom = max(total_quota - total_usage, 0.0) if total_quota > 0 else None
    days_values = [
        float(item['days_to_quota'])
        for item in project_forecasts
        if isinstance(item.get('days_to_quota'), (int, float))
    ]
    nearest_days = min(days_values) if days_values else None

    if nearest_days is not None and nearest_days <= 30:
        risk = 'Critical'
    elif quota_utilization is not None and quota_utilization >= 90:
        risk = 'Critical'
    elif nearest_days is not None and nearest_days <= 90:
        risk = 'Medium'
    elif quota_utilization is not None and quota_utilization >= 75:
        risk = 'Medium'
    elif quota_utilization is not None or nearest_days is not None:
        risk = 'Low'
    else:
        risk = 'Unknown'

    copy = {
        'Critical': (
            'Committed project quota evidence shows immediate Registry capacity pressure.',
            'At least one project is inside the 30-day quota horizon or aggregate utilization is at least 90%.',
            'Validate growth and ownership, then prepare an approved quota, retention, or cleanup change.',
        ),
        'Medium': (
            'Committed Registry analytics shows developing project capacity pressure.',
            'Quota utilization or projected exhaustion is inside the planning threshold.',
            'Review top project consumers, stale artifacts, retention policy, and quota ownership.',
        ),
        'Low': (
            'Committed quota evidence currently shows usable project headroom.',
            'No current project quota forecast is inside the warning threshold.',
            'Continue worker materialization and review growth after major publication changes.',
        ),
        'Unknown': (
            'Project quota risk cannot be calculated from the currently committed analytics evidence.',
            'Inventory footprint remains available, but project quota or growth evidence is incomplete.',
            'Refresh Registry Analytics after validating the Registry Metrics Source binding.',
        ),
    }
    insight, risk_detail, recommended_action = copy[risk]
    return {
        'total_usage': total_usage,
        'total_quota': total_quota,
        'quota_utilization': quota_utilization,
        'quota_headroom': quota_headroom,
        'nearest_days': nearest_days,
        'risk': risk,
        'insight': insight,
        'risk_detail': risk_detail,
        'recommended_action': recommended_action,
    }


def _registry_capacity_summary(
    *,
    scoped_providers: list[IntegrationInstance],
    committed_snapshot_count: int,
    total_size_bytes: int,
    artifact_total: int,
    analytics_count: int,
    posture: dict[str, Any],
) -> dict[str, Any]:
    total_quota = float(posture['total_quota'])
    quota_utilization = posture['quota_utilization']
    quota_headroom = posture['quota_headroom']
    return {
        'available': bool(scoped_providers) and bool(committed_snapshot_count or analytics_count),
        'metrics': [
            {
                'label': 'Artifact Footprint',
                'value': _fmt_bytes(total_size_bytes),
                'description': f'{artifact_total} committed artifact identities.',
                'used_percent': None,
            },
            {
                'label': 'Quota Utilization',
                'value': f'{quota_utilization:.1f}%' if quota_utilization is not None else 'N/A',
                'description': (
                    f'{_fmt_bytes(round(float(posture["total_usage"])))} used of '
                    f'{_fmt_bytes(round(total_quota))} committed project quota.'
                    if total_quota > 0
                    else 'No committed project quota denominator is available.'
                ),
                'used_percent': quota_utilization,
            },
            {
                'label': 'Quota Headroom',
                'value': _fmt_bytes(round(quota_headroom)) if quota_headroom is not None else 'N/A',
                'description': 'Remaining Registry quota headroom.',
                'used_percent': quota_utilization,
            },
        ],
        'risk': posture['risk'],
        'insight': posture['insight'],
        'risk_detail': posture['risk_detail'],
        'recommended_action': posture['recommended_action'],
    }


def _registry_capacity_forecast(
    *,
    growth: dict[str, Any],
    metrics_ready_count: int,
    posture: dict[str, Any],
) -> dict[str, Any]:
    observed = bool(growth['observed'])
    nearest_days = posture['nearest_days']
    return {
        'available': int(growth['analytics_count']) > 0,
        'source_ready': metrics_ready_count > 0,
        'analytics_count': int(growth['analytics_count']),
        'size_growth_per_day': _fmt_bytes(round(float(growth['size_per_day']))) if observed else 'N/A',
        'artifact_growth_per_day': (f'{float(growth["artifacts_per_day"]):.1f} artifacts/day' if observed else 'N/A'),
        'nearest_quota_days': f'{nearest_days:.1f} days' if nearest_days is not None else 'N/A',
        'risk': posture['risk'],
        'detail': (
            'Worker-materialized Registry analytics combines committed inventory deltas with bound Metrics Source quota evidence.'
        ),
    }


def _registry_top_consumers(project_forecasts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    top_consumers = sorted(
        project_forecasts,
        key=lambda item: (
            -(float(item['usage_bytes']) if item['usage_bytes'] is not None else -1.0),
            -(float(item['utilization_percent']) if item['utilization_percent'] is not None else -1.0),
            item['project_name'].casefold(),
        ),
    )[:5]
    for item in top_consumers:
        item['usage_display'] = (
            _fmt_bytes(round(float(item['usage_bytes']))) if item['usage_bytes'] is not None else 'N/A'
        )
        item['quota_display'] = (
            _fmt_bytes(round(float(item['quota_bytes']))) if item['quota_bytes'] is not None else 'N/A'
        )
        item['utilization_display'] = (
            f'{float(item["utilization_percent"]):.1f}%' if item['utilization_percent'] is not None else 'N/A'
        )
        item['days_to_quota_display'] = (
            f'{float(item["days_to_quota"]):.1f} days' if item['days_to_quota'] is not None else 'N/A'
        )
    return top_consumers


def _registry_capacity_views(
    *,
    scoped_providers: list[IntegrationInstance],
    analytics_by_provider: dict[int, RegistryAnalyticsSnapshot | None],
    total_size_bytes: int,
    artifact_total: int,
    committed_snapshot_count: int,
    metrics_ready_count: int,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    project_forecasts, growth = _collect_registry_capacity_analytics(
        scoped_providers=scoped_providers,
        analytics_by_provider=analytics_by_provider,
    )
    posture = _registry_capacity_posture(project_forecasts)
    capacity = _registry_capacity_summary(
        scoped_providers=scoped_providers,
        committed_snapshot_count=committed_snapshot_count,
        total_size_bytes=total_size_bytes,
        artifact_total=artifact_total,
        analytics_count=int(growth['analytics_count']),
        posture=posture,
    )
    forecast = _registry_capacity_forecast(
        growth=growth,
        metrics_ready_count=metrics_ready_count,
        posture=posture,
    )
    return capacity, forecast, _registry_top_consumers(project_forecasts)


def _registry_alerts(selected_provider: IntegrationInstance | None) -> dict[str, Any]:
    catalog_rules = sum(
        str(rule.get('domain') or '') == 'registry' and str(rule.get('status') or '') == 'available'
        for rule in INTELLIGENCE_CATALOG
    )
    if selected_provider is None:
        return {
            'available': False,
            'critical': 0,
            'warning': 0,
            'info': 0,
            'total': 0,
            'catalog_rules': catalog_rules,
            'source_label': 'Alert Intelligence',
            'source_detail': 'Active AlertCase records',
            'rows': [],
        }

    cases = active_recommendation_alert_cases(
        domain='registry',
        asset_key=str(selected_provider.id),
    )
    return {
        'available': True,
        'critical': sum(str(case.severity or '').lower() == 'critical' for case in cases),
        'warning': sum(str(case.severity or '').lower() == 'warning' for case in cases),
        'info': sum(str(case.severity or '').lower() not in {'critical', 'warning'} for case in cases),
        'total': len(cases),
        'catalog_rules': catalog_rules,
        'source_label': 'Alert Intelligence',
        'source_detail': 'Active AlertCase records',
        'rows': [
            {
                'title': str(case.alert_name or 'KAORI Alert Case'),
                'description': str(case.summary or case.target or 'KAORI Registry recommendation alert case.'),
                'severity': str(case.severity or 'info'),
                'state': (
                    'Source Unknown'
                    if case.source_state == 'unknown'
                    else str(case.workflow_state or 'active').replace('_', ' ').title()
                ),
                'age': _human_time(case.first_seen_at),
                'case_id': case.public_id,
            }
            for case in cases[:5]
        ],
    }


def _registry_recommended_actions(selected_provider: IntegrationInstance | None) -> list[dict[str, str]]:
    findings = get_dashboard_recommendation_findings(
        domain='registry',
        asset_key=str(selected_provider.id) if selected_provider is not None else None,
    )
    return [
        {
            'title': str(item.get('title') or 'Review recommendation'),
            'description': str(item.get('recommended_action') or item.get('summary') or ''),
            'category': str(item.get('category_label') or item.get('category') or 'Operations'),
            'severity': str(item.get('severity') or 'info'),
            'priority': str(item.get('priority') or 'P3'),
            'source': str(item.get('signal_source_label') or item.get('signal_source') or 'Intelligence'),
            'rule_key': str(item.get('rule_key') or ''),
            'icon': 'sparkles',
        }
        for item in findings
    ]


def _registry_reporting(selected_provider: IntegrationInstance | None) -> dict[str, Any]:
    reports_query = Report.query.filter(Report.report_domain == 'artifact_registry')
    schedules_query = ReportSchedule.query.filter(ReportSchedule.report_domain == 'artifact_registry')
    if selected_provider is not None:
        reports_query = reports_query.filter(
            or_(Report.scope_asset_id == str(selected_provider.id), Report.scope_asset_id.is_(None))
        )
        schedules_query = schedules_query.filter(
            or_(ReportSchedule.scope_asset_id == str(selected_provider.id), ReportSchedule.scope_asset_id.is_(None))
        )
    recent = reports_query.order_by(Report.created_at.desc()).limit(4).all()
    system_templates = sum(spec.domain == 'artifact_registry' for spec in REPORT_TYPE_SPECS)
    custom_templates = ReportTemplate.query.filter(ReportTemplate.report_domain == 'artifact_registry').count()
    return {
        'source_status': 'Available',
        'generated_reports': reports_query.count(),
        'templates': system_templates + custom_templates,
        'schedules': schedules_query.count(),
        'latest_reports': [
            {
                'title': report.name,
                'status': str(report.status or 'unknown').replace('_', ' ').title(),
                'generated_at': _human_time(report.created_at),
            }
            for report in recent
        ],
    }


def _overview_scope_context(
    *,
    provider_id: int | None = None,
    active_tab: str = 'overview',
    provider_health_page: int | str | None = 1,
    provider_health_per_page: int = 5,
) -> tuple[
    dict[str, Any],
    list[IntegrationInstance],
    IntegrationInstance | None,
    list[IntegrationInstance],
    list[RegistryCollectionState],
]:
    """Build the Artifact Registry Fast Shell from bounded scope/state reads only."""

    providers = _providers()
    selected_provider = next(
        (provider for provider in providers if provider_id is not None and int(provider.id) == int(provider_id)),
        None,
    )
    scoped_providers = [selected_provider] if selected_provider is not None else providers

    states_query = RegistryCollectionState.query
    if selected_provider is not None:
        states_query = states_query.filter(RegistryCollectionState.integration_instance_id == selected_provider.id)
    states = states_query.all()
    committed_states = [state for state in states if state.last_committed_at is not None]
    latest = max(
        (state.last_committed_at for state in committed_states if state.last_committed_at),
        default=None,
    )
    stale_count = sum(bool(_state_view(state)['is_stale']) for state in committed_states)
    pending_snapshot_count = max(len(scoped_providers) - len(committed_states), 0)
    failed_refresh_count = sum(bool(state.last_error) for state in committed_states)

    if not providers:
        posture = {'label': 'Setup Required', 'tone': 'unknown'}
    elif not committed_states:
        posture = {'label': 'Inventory Pending', 'tone': 'warning'}
    elif pending_snapshot_count or stale_count or failed_refresh_count:
        posture = {'label': 'Attention Required', 'tone': 'warning'}
    else:
        posture = {'label': 'Ready', 'tone': 'normal'}

    _visible_providers, provider_health_pagination = paginate_sequence(
        scoped_providers,
        page=provider_health_page,
        per_page=provider_health_per_page,
    )
    scope_label = selected_provider.name if selected_provider is not None else 'All Registry Providers'
    context = {
        'setup': {'is_blocked': not providers, 'provider_count': len(providers)},
        'providers': providers,
        'selected_provider': selected_provider,
        'selected_provider_id': (int(selected_provider.id) if selected_provider is not None else None),
        'scope_label': scope_label,
        'active_tab': normalize_operational_tab(active_tab),
        'provider_count': len(scoped_providers),
        'latest_committed_at': latest,
        'posture': posture,
        'snapshot_count': len(committed_states),
        'stale_snapshot_count': stale_count,
        'pending_snapshot_count': pending_snapshot_count,
        'failed_refresh_count': failed_refresh_count,
        'provider_health_pagination': provider_health_pagination,
        'sync_required': pending_snapshot_count > 0,
    }
    return context, providers, selected_provider, scoped_providers, states


def _overview_kpi_values(
    selected_provider: IntegrationInstance | None,
) -> dict[str, int]:
    project_query = RegistryProject.query
    repository_query = RegistryRepository.query.join(RegistryProject)
    artifact_query = RegistryArtifact.query.join(RegistryRepository).join(RegistryProject)
    tag_query = RegistryTag.query.join(RegistryArtifact).join(RegistryRepository).join(RegistryProject)
    if selected_provider is not None:
        project_query = project_query.filter(RegistryProject.integration_instance_id == selected_provider.id)
        repository_query = repository_query.filter(RegistryProject.integration_instance_id == selected_provider.id)
        artifact_query = artifact_query.filter(RegistryProject.integration_instance_id == selected_provider.id)
        tag_query = tag_query.filter(RegistryProject.integration_instance_id == selected_provider.id)
    return {
        'projects': project_query.count(),
        'repositories': repository_query.count(),
        'artifacts': artifact_query.count(),
        'tags': tag_query.count(),
    }


def _latest_registry_analytics(
    scoped_providers: list[IntegrationInstance],
) -> dict[int, RegistryAnalyticsSnapshot | None]:
    snapshots: dict[int, RegistryAnalyticsSnapshot | None] = {}
    for provider in scoped_providers:
        snapshots[int(provider.id)] = (
            RegistryAnalyticsSnapshot.query.filter_by(
                integration_instance_id=provider.id,
                status='ready',
            )
            .order_by(
                RegistryAnalyticsSnapshot.generated_at.desc(),
                RegistryAnalyticsSnapshot.id.desc(),
            )
            .first()
        )
    return snapshots
