from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import case, func, or_
from sqlalchemy.orm import joinedload

from app.artifact_registry.observability import registry_metrics_readiness
from app.common.pagination import paginate_sequence
from app.dashboards.common.operational import normalize_operational_tab
from app.intelligence.alert_intelligence.dashboard_cases import active_recommendation_alert_cases_by_asset
from app.intelligence.catalog import INTELLIGENCE_CATALOG
from app.intelligence.dashboard_recommendations import get_dashboard_recommendation_findings
from app.models.integration import IntegrationInstance
from app.models.report import Report, ReportSchedule, ReportTemplate
from app.reports.catalog import REPORT_TYPE_SPECS
from app.models.registry import (
    RegistryAnalyticsSnapshot,
    RegistryArtifact,
    RegistryCollectionState,
    RegistryGovernanceState,
    RegistryProject,
    RegistryProjectGovernance,
    RegistryReplicationPolicy,
    RegistryRepository,
    RegistryScanSnapshot,
    RegistryTag,
    RegistryWebhookEndpoint,
    RegistryWorkloadBinding,
)

FRESHNESS_HOURS = 24
_SUCCESSFUL_SCAN_STATES = ('success', 'finished', 'completed')


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


def _scan_evidence_ready(value: str | None) -> bool:
    return str(value or '').strip().lower() in _SUCCESSFUL_SCAN_STATES


def _state_view(state: RegistryCollectionState | None) -> dict[str, Any]:
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
    stale = bool(
        committed_at is not None
        and committed_at < datetime.now(UTC) - timedelta(hours=FRESHNESS_HOURS)
    )
    return {
        'status': state.status,
        'label': 'Stale Snapshot' if stale else 'Current Snapshot',
        'tone': 'warning' if stale else 'normal',
        'observed_at': state.last_observed_at,
        'committed_at': state.last_committed_at,
        'is_stale': stale,
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


def _registry_capacity_views(
    *,
    scoped_providers: list[IntegrationInstance],
    analytics_by_provider: dict[int, RegistryAnalyticsSnapshot | None],
    total_size_bytes: int,
    artifact_total: int,
    committed_snapshot_count: int,
    metrics_ready_count: int,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    provider_names = {int(provider.id): provider.name for provider in scoped_providers}
    project_forecasts: list[dict[str, Any]] = []
    size_growth_per_day = 0.0
    artifact_growth_per_day = 0.0
    growth_observed = False
    analytics_count = 0

    for provider_id, snapshot in analytics_by_provider.items():
        if snapshot is None:
            continue
        analytics_count += 1
        payload = _analytics_payload(snapshot)
        growth = payload.get('growth') if isinstance(payload.get('growth'), dict) else {}
        size_growth = growth.get('size_growth_bytes_per_day')
        artifact_growth = growth.get('artifact_growth_per_day')
        if isinstance(size_growth, (int, float)):
            size_growth_per_day += float(size_growth)
            growth_observed = True
        if isinstance(artifact_growth, (int, float)):
            artifact_growth_per_day += float(artifact_growth)
            growth_observed = True

        capacity = payload.get('capacity') if isinstance(payload.get('capacity'), dict) else {}
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
            project_forecasts.append(
                {
                    'provider_id': provider_id,
                    'provider_name': provider_names.get(provider_id, f'Registry {provider_id}'),
                    'project_name': str(raw.get('project_name') or 'Registry Project'),
                    'usage_bytes': float(usage) if isinstance(usage, (int, float)) else None,
                    'quota_bytes': float(quota) if isinstance(quota, (int, float)) else None,
                    'utilization_percent': (
                        float(utilization) if isinstance(utilization, (int, float)) else None
                    ),
                    'growth_bytes_per_day': (
                        float(raw.get('growth_bytes_per_day'))
                        if isinstance(raw.get('growth_bytes_per_day'), (int, float))
                        else None
                    ),
                    'days_to_quota': float(days) if isinstance(days, (int, float)) else None,
                }
            )

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

    if risk == 'Critical':
        insight = 'Committed project quota evidence shows immediate Registry capacity pressure.'
        risk_detail = 'At least one project is inside the 30-day quota horizon or aggregate utilization is at least 90%.'
        recommended_action = 'Validate growth and ownership, then prepare an approved quota, retention, or cleanup change.'
    elif risk == 'Medium':
        insight = 'Committed Registry analytics shows developing project capacity pressure.'
        risk_detail = 'Quota utilization or projected exhaustion is inside the planning threshold.'
        recommended_action = 'Review top project consumers, stale artifacts, retention policy, and quota ownership.'
    elif risk == 'Low':
        insight = 'Committed quota evidence currently shows usable project headroom.'
        risk_detail = 'No current project quota forecast is inside the warning threshold.'
        recommended_action = 'Continue worker materialization and review growth after major publication changes.'
    else:
        insight = 'Project quota risk cannot be calculated from the currently committed analytics evidence.'
        risk_detail = 'Inventory footprint remains available, but project quota or growth evidence is incomplete.'
        recommended_action = 'Refresh Registry Analytics after validating the Registry Metrics Source binding.'

    capacity = {
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
                    f'{_fmt_bytes(round(total_usage))} used of {_fmt_bytes(round(total_quota))} committed project quota.'
                    if total_quota > 0
                    else 'No committed project quota denominator is available.'
                ),
                'used_percent': quota_utilization,
            },
            {
                'label': 'Quota Headroom',
                'value': _fmt_bytes(round(quota_headroom)) if quota_headroom is not None else 'N/A',
                'description': 'Remaining committed project quota headroom across the active Registry scope.',
                'used_percent': quota_utilization,
            },
        ],
        'risk': risk,
        'insight': insight,
        'risk_detail': risk_detail,
        'recommended_action': recommended_action,
    }
    forecast = {
        'available': analytics_count > 0,
        'source_ready': metrics_ready_count > 0,
        'analytics_count': analytics_count,
        'size_growth_per_day': _fmt_bytes(round(size_growth_per_day)) if growth_observed else 'N/A',
        'artifact_growth_per_day': f'{artifact_growth_per_day:.1f} artifacts/day' if growth_observed else 'N/A',
        'nearest_quota_days': f'{nearest_days:.1f} days' if nearest_days is not None else 'N/A',
        'risk': risk,
        'detail': (
            'Worker-materialized Registry analytics combines committed inventory deltas with bound Metrics Source quota evidence.'
        ),
    }

    top_consumers = sorted(
        project_forecasts,
        key=lambda item: (
            -(float(item['usage_bytes']) if item['usage_bytes'] is not None else -1.0),
            -(float(item['utilization_percent']) if item['utilization_percent'] is not None else -1.0),
            item['project_name'].casefold(),
        ),
    )[:5]
    for item in top_consumers:
        item['usage_display'] = _fmt_bytes(round(float(item['usage_bytes']))) if item['usage_bytes'] is not None else 'N/A'
        item['quota_display'] = _fmt_bytes(round(float(item['quota_bytes']))) if item['quota_bytes'] is not None else 'N/A'
        item['utilization_display'] = (
            f"{float(item['utilization_percent']):.1f}%" if item['utilization_percent'] is not None else 'N/A'
        )
        item['days_to_quota_display'] = (
            f"{float(item['days_to_quota']):.1f} days" if item['days_to_quota'] is not None else 'N/A'
        )
    return capacity, forecast, top_consumers


def _registry_alerts(scoped_providers: list[IntegrationInstance]) -> dict[str, Any]:
    asset_keys = [str(provider.id) for provider in scoped_providers]
    grouped = active_recommendation_alert_cases_by_asset(domain='registry', asset_keys=asset_keys)
    cases = [case for key in asset_keys for case in grouped.get(key, [])]
    cases.sort(
        key=lambda item: _aware_datetime(item.first_seen_at) or datetime.min.replace(tzinfo=UTC),
        reverse=True,
    )
    return {
        'available': True,
        'critical': sum(str(case.severity or '').lower() == 'critical' for case in cases),
        'warning': sum(str(case.severity or '').lower() == 'warning' for case in cases),
        'info': sum(str(case.severity or '').lower() not in {'critical', 'warning'} for case in cases),
        'total': len(cases),
        'catalog_rules': sum(
            str(rule.get('domain') or '') == 'registry' and str(rule.get('status') or '') == 'available'
            for rule in INTELLIGENCE_CATALOG
        ),
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
        (
            provider
            for provider in providers
            if provider_id is not None and int(provider.id) == int(provider_id)
        ),
        None,
    )
    scoped_providers = [selected_provider] if selected_provider is not None else providers

    states_query = RegistryCollectionState.query
    if selected_provider is not None:
        states_query = states_query.filter(
            RegistryCollectionState.integration_instance_id == selected_provider.id
        )
    states = states_query.all()
    committed_states = [state for state in states if state.last_committed_at is not None]
    latest = max(
        (state.last_committed_at for state in committed_states if state.last_committed_at),
        default=None,
    )
    stale_count = sum(bool(_state_view(state)['is_stale']) for state in committed_states)
    pending_snapshot_count = max(len(scoped_providers) - len(committed_states), 0)
    failed_refresh_count = sum(state.status == 'failed' for state in committed_states)

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
    scope_label = (
        selected_provider.name if selected_provider is not None else 'All Registry Providers'
    )
    context = {
        'setup': {'is_blocked': not providers, 'provider_count': len(providers)},
        'providers': providers,
        'selected_provider': selected_provider,
        'selected_provider_id': (
            int(selected_provider.id) if selected_provider is not None else None
        ),
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
    tag_query = (
        RegistryTag.query.join(RegistryArtifact)
        .join(RegistryRepository)
        .join(RegistryProject)
    )
    if selected_provider is not None:
        project_query = project_query.filter(
            RegistryProject.integration_instance_id == selected_provider.id
        )
        repository_query = repository_query.filter(
            RegistryProject.integration_instance_id == selected_provider.id
        )
        artifact_query = artifact_query.filter(
            RegistryProject.integration_instance_id == selected_provider.id
        )
        tag_query = tag_query.filter(
            RegistryProject.integration_instance_id == selected_provider.id
        )
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


def _provider_health_projection(
    *,
    scoped_providers: list[IntegrationInstance],
    states: list[RegistryCollectionState],
    selected_provider: IntegrationInstance | None,
    provider_health_page: int | str | None,
    provider_health_per_page: int,
) -> tuple[
    list[dict[str, Any]],
    Any,
    dict[int, dict[str, Any]],
    dict[int, dict[str, int]],
]:
    state_by_provider = {int(state.integration_instance_id): state for state in states}

    project_counts_query = RegistryProject.query.with_entities(
        RegistryProject.integration_instance_id,
        func.count(RegistryProject.id),
    )
    repository_counts_query = (
        RegistryRepository.query.join(RegistryProject)
        .with_entities(
            RegistryProject.integration_instance_id,
            func.count(RegistryRepository.id),
        )
    )
    security_counts_query = (
        RegistryArtifact.query.join(RegistryRepository)
        .join(RegistryProject)
        .with_entities(
            RegistryProject.integration_instance_id,
            func.count(RegistryArtifact.id),
            func.coalesce(
                func.sum(
                    case(
                        (
                            func.lower(RegistryArtifact.scan_status).in_(
                                _SUCCESSFUL_SCAN_STATES
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ),
                0,
            ),
            func.coalesce(
                func.sum(
                    RegistryArtifact.vulnerability_summary['critical'].as_integer()
                ),
                0,
            ),
            func.coalesce(
                func.sum(
                    RegistryArtifact.vulnerability_summary['high'].as_integer()
                ),
                0,
            ),
        )
    )
    if selected_provider is not None:
        project_counts_query = project_counts_query.filter(
            RegistryProject.integration_instance_id == selected_provider.id
        )
        repository_counts_query = repository_counts_query.filter(
            RegistryProject.integration_instance_id == selected_provider.id
        )
        security_counts_query = security_counts_query.filter(
            RegistryProject.integration_instance_id == selected_provider.id
        )

    project_counts = {
        int(provider_id): int(count)
        for provider_id, count in project_counts_query.group_by(
            RegistryProject.integration_instance_id
        ).all()
    }
    repository_counts = {
        int(provider_id): int(count)
        for provider_id, count in repository_counts_query.group_by(
            RegistryProject.integration_instance_id
        ).all()
    }
    security_counts = {
        int(provider_id): {
            'artifacts': int(artifacts or 0),
            'scanned': int(scanned or 0),
            'critical': int(critical or 0),
            'high': int(high or 0),
        }
        for provider_id, artifacts, scanned, critical, high in security_counts_query.group_by(
            RegistryProject.integration_instance_id
        ).all()
    }

    metrics_by_provider = {
        int(provider.id): registry_metrics_readiness(provider)
        for provider in scoped_providers
    }
    provider_rows: list[dict[str, Any]] = []
    for provider in scoped_providers:
        key = int(provider.id)
        state = state_by_provider.get(key)
        snapshot = _state_view(state)
        metrics = metrics_by_provider.get(key, {})
        security = security_counts.get(
            key,
            {'artifacts': 0, 'scanned': 0, 'critical': 0, 'high': 0},
        )
        readiness = str(provider.readiness_status or 'validation_required')
        inventory_ready = bool(state is not None and state.last_committed_at is not None)
        provider_artifact_count = security['artifacts']
        security_ready = bool(security['scanned'])
        security_not_applicable = inventory_ready and provider_artifact_count == 0

        if readiness == 'blocked':
            overall_status, overall_tone, status_reason = (
                'Critical',
                'critical',
                'Provider readiness is blocked.',
            )
        elif state is not None and state.status == 'failed' and not inventory_ready:
            overall_status, overall_tone = 'Critical', 'critical'
            status_reason = (
                'Inventory synchronization failed before a committed snapshot was established.'
            )
        elif security['critical'] > 0:
            overall_status, overall_tone = 'Critical', 'critical'
            status_reason = f"{security['critical']} critical security finding(s)."
        elif not inventory_ready:
            overall_status, overall_tone, status_reason = (
                'Warning',
                'warning',
                'Committed inventory has not been collected.',
            )
        elif snapshot['is_stale']:
            overall_status, overall_tone, status_reason = (
                'Warning',
                'warning',
                'Committed inventory snapshot is stale.',
            )
        elif state is not None and state.status == 'failed':
            overall_status, overall_tone = 'Warning', 'warning'
            status_reason = (
                'Latest inventory refresh failed; the previous committed snapshot is retained.'
            )
        elif readiness == 'degraded':
            overall_status, overall_tone = 'Warning', 'warning'
            status_reason = 'Provider is usable with compatibility attention.'
        else:
            overall_status, overall_tone = 'Healthy', 'normal'
            status_reason = 'Provider and committed inventory are operational.'

        provider_rows.append(
            {
                'id': key,
                'name': provider.name,
                'provider_label': str(
                    (provider.metadata_json or {}).get('provider_label')
                    or provider.provider_key.title()
                ),
                'environment': provider.environment or 'Not Set',
                'overall_status': overall_status,
                'overall_tone': overall_tone,
                'status_reason': status_reason,
                'readiness': readiness,
                'project_count': project_counts.get(key, 0),
                'repository_count': repository_counts.get(key, 0),
                'artifact_count': provider_artifact_count,
                'critical_findings': security['critical'],
                'high_findings': security['high'],
                'inventory_ready': inventory_ready,
                'metrics_ready': metrics.get('status') == 'ready',
                'security_ready': security_ready,
                'security_not_applicable': security_not_applicable,
                'snapshot': snapshot,
            }
        )

    visible_rows, pagination = paginate_sequence(
        provider_rows,
        page=provider_health_page,
        per_page=provider_health_per_page,
    )
    return visible_rows, pagination, metrics_by_provider, security_counts


def _overview_operations_projection(
    *,
    context: dict[str, Any],
    scoped_providers: list[IntegrationInstance],
    states: list[RegistryCollectionState],
    selected_provider: IntegrationInstance | None,
    provider_health_page: int | str | None,
    provider_health_per_page: int,
) -> dict[str, Any]:
    provider_rows, pagination, metrics_by_provider, security_counts = (
        _provider_health_projection(
            scoped_providers=scoped_providers,
            states=states,
            selected_provider=selected_provider,
            provider_health_page=provider_health_page,
            provider_health_per_page=provider_health_per_page,
        )
    )
    counts = _overview_kpi_values(selected_provider)

    artifact_summary_query = (
        RegistryArtifact.query.join(RegistryRepository)
        .join(RegistryProject)
        .with_entities(func.coalesce(func.sum(RegistryArtifact.size_bytes), 0))
    )
    public_projects_query = RegistryProject.query.filter(RegistryProject.public.is_(True))
    if selected_provider is not None:
        artifact_summary_query = artifact_summary_query.filter(
            RegistryProject.integration_instance_id == selected_provider.id
        )
        public_projects_query = public_projects_query.filter(
            RegistryProject.integration_instance_id == selected_provider.id
        )
    total_size_bytes = int(artifact_summary_query.one()[0] or 0)
    public_project_count = public_projects_query.count()

    security_freshness_query = (
        RegistryScanSnapshot.query.join(
            RegistryArtifact,
            RegistryScanSnapshot.artifact_id == RegistryArtifact.id,
        )
        .join(
            RegistryRepository,
            RegistryArtifact.repository_id == RegistryRepository.id,
        )
        .join(
            RegistryProject,
            RegistryRepository.project_id == RegistryProject.id,
        )
        .with_entities(
            RegistryProject.integration_instance_id,
            func.max(RegistryScanSnapshot.observed_at),
        )
    )
    if selected_provider is not None:
        security_freshness_query = security_freshness_query.filter(
            RegistryProject.integration_instance_id == selected_provider.id
        )
    security_observed_by_provider = {
        int(provider_id): observed_at
        for provider_id, observed_at in security_freshness_query.group_by(
            RegistryProject.integration_instance_id
        ).all()
    }
    latest_security_at = max(
        (value for value in security_observed_by_provider.values() if value is not None),
        default=None,
    )

    state_by_provider = {int(state.integration_instance_id): state for state in states}
    committed_states = [state for state in states if state.last_committed_at is not None]
    stale_count = context['stale_snapshot_count']
    failed_refresh_count = context['failed_refresh_count']
    artifact_total = counts['artifacts']
    scanned_count = sum(item['scanned'] for item in security_counts.values())
    analytics_by_provider = _latest_registry_analytics(scoped_providers)
    metrics_ready_count = sum(
        metrics.get('status') == 'ready'
        for metrics in metrics_by_provider.values()
    )
    analytics_ready_count = sum(
        snapshot is not None for snapshot in analytics_by_provider.values()
    )
    latest_analytics_at = max(
        (
            snapshot.generated_at
            for snapshot in analytics_by_provider.values()
            if snapshot is not None and snapshot.generated_at is not None
        ),
        default=None,
    )

    inventory_items = [
        {'label': 'Projects', 'value': counts['projects'], 'icon': 'folder-kanban', 'role': 'Scope'},
        {'label': 'Repositories', 'value': counts['repositories'], 'icon': 'package-open', 'role': 'Catalog'},
        {'label': 'Artifacts', 'value': artifact_total, 'icon': 'fingerprint', 'role': 'Immutable'},
        {'label': 'Tags', 'value': counts['tags'], 'icon': 'tags', 'role': 'Aliases'},
        {'label': 'Artifact Footprint', 'value': _fmt_bytes(total_size_bytes), 'icon': 'database', 'role': 'Storage'},
        {'label': 'Public Projects', 'value': public_project_count, 'icon': 'globe-2', 'role': 'Exposure'},
    ]

    if selected_provider is not None:
        selected_key = int(selected_provider.id)
        selected_collection_state = state_by_provider.get(selected_key)
        selected_state = _state_view(selected_collection_state)
        selected_metrics = metrics_by_provider.get(selected_key, {})
        selected_analytics = _analytics_snapshot_view(
            analytics_by_provider.get(selected_key)
        )
        if artifact_total == 0 and selected_state['committed_at'] is not None:
            security_status, security_tone, security_value = (
                'No Artifacts',
                'info',
                'No committed artifacts to scan',
            )
        elif scanned_count:
            security_status, security_tone = 'Available', 'normal'
            security_value = _freshness_value(
                latest_security_at,
                missing='Committed scan evidence available',
            )
        else:
            security_status = 'Required'
            security_tone = 'warning' if artifact_total else 'unknown'
            security_value = 'No committed security snapshot'

        inventory_description = (
            'Committed projects, repositories, artifacts, tags, and provider provenance.'
        )
        if (
            selected_collection_state is not None
            and selected_collection_state.status == 'failed'
        ):
            inventory_description += (
                ' Latest refresh failed; KAORI retained the previous committed snapshot.'
            )
        freshness = [
            {
                'label': 'Inventory Snapshot',
                'status': selected_state['label'],
                'tone': selected_state['tone'],
                'value': _freshness_value(
                    selected_state['committed_at'],
                    missing='No committed inventory snapshot',
                ),
                'description': inventory_description,
                'icon': 'database-zap',
            },
            {
                'label': 'Metrics Snapshot',
                'status': str(selected_metrics.get('label') or 'Not Bound'),
                'tone': str(selected_metrics.get('tone') or 'unknown'),
                'value': str(
                    selected_metrics.get('selected_source')
                    or 'No validated Metrics Source'
                ),
                'description': (
                    'Validated Registry Metrics Source binding; independent from provider readiness.'
                ),
                'icon': 'activity',
            },
            {
                'label': 'Security Snapshot',
                'status': security_status,
                'tone': security_tone,
                'value': security_value,
                'description': (
                    'Committed vulnerability scan evidence attached to immutable artifact digests.'
                ),
                'icon': 'shield-check',
            },
            {
                'label': 'Analytics Snapshot',
                'status': selected_analytics['label'],
                'tone': selected_analytics['tone'],
                'value': _freshness_value(
                    selected_analytics['generated_at'],
                    missing='No materialized analytics snapshot',
                ),
                'description': (
                    'Materialized Registry growth, forecast, runtime, and recommendation evidence.'
                ),
                'icon': 'chart-no-axes-combined',
            },
        ]
    else:
        committed_count = len(committed_states)
        if committed_count == len(scoped_providers) and scoped_providers:
            inventory_status = (
                'Stale'
                if stale_count
                else ('Attention' if failed_refresh_count else 'Ready')
            )
            inventory_tone = (
                'warning' if stale_count or failed_refresh_count else 'normal'
            )
        elif committed_count:
            inventory_status, inventory_tone = 'Partial', 'warning'
        else:
            inventory_status, inventory_tone = 'Required', 'unknown'
        freshness = [
            {
                'label': 'Inventory Snapshot',
                'status': inventory_status,
                'tone': inventory_tone,
                'value': _freshness_value(
                    context['latest_committed_at'],
                    missing='No committed inventory snapshot',
                ),
                'description': 'Latest retained committed inventory evidence across the active Registry scope.',
                'icon': 'database-zap',
            },
            {
                'label': 'Metrics Snapshot',
                'status': (
                    'Ready'
                    if metrics_ready_count == len(scoped_providers) and scoped_providers
                    else ('Partial' if metrics_ready_count else 'Not Bound')
                ),
                'tone': (
                    'normal'
                    if metrics_ready_count == len(scoped_providers) and scoped_providers
                    else ('warning' if metrics_ready_count else 'unknown')
                ),
                'value': (
                    'Validated Metrics Source available'
                    if metrics_ready_count == len(scoped_providers) and scoped_providers
                    else (
                        'Validated Metrics Source partially available'
                        if metrics_ready_count
                        else 'No validated Metrics Source'
                    )
                ),
                'description': (
                    'Validated Registry Metrics Source availability across the active scope.'
                ),
                'icon': 'activity',
            },
            {
                'label': 'Security Snapshot',
                'status': (
                    'No Artifacts'
                    if artifact_total == 0
                    else ('Available' if scanned_count else 'Required')
                ),
                'tone': (
                    'info'
                    if artifact_total == 0
                    else ('normal' if scanned_count else 'warning')
                ),
                'value': (
                    'No committed artifacts to scan'
                    if artifact_total == 0
                    else (
                        _freshness_value(
                            latest_security_at,
                            missing='Committed scan evidence available',
                        )
                        if scanned_count
                        else 'No committed security snapshot'
                    )
                ),
                'description': (
                    'Latest committed vulnerability scan evidence across the active Registry scope.'
                ),
                'icon': 'shield-check',
            },
            {
                'label': 'Analytics Snapshot',
                'status': (
                    'Ready'
                    if analytics_ready_count == len(scoped_providers) and scoped_providers
                    else ('Partial' if analytics_ready_count else 'Required')
                ),
                'tone': (
                    'normal'
                    if analytics_ready_count == len(scoped_providers) and scoped_providers
                    else ('warning' if analytics_ready_count else 'unknown')
                ),
                'value': _freshness_value(
                    latest_analytics_at,
                    missing='No materialized analytics snapshot',
                ),
                'description': 'Latest ready Registry analytics materialization across the active scope.',
                'icon': 'chart-no-axes-combined',
            },
        ]

    return {
        **context,
        'project_count': counts['projects'],
        'repository_count': counts['repositories'],
        'artifact_count': artifact_total,
        'tag_count': counts['tags'],
        'total_size_bytes': total_size_bytes,
        'total_size': _fmt_bytes(total_size_bytes),
        'public_project_count': public_project_count,
        'scanned_count': scanned_count,
        'scan_coverage': (
            round((scanned_count / artifact_total) * 100) if artifact_total else 0
        ),
        'metrics_ready_count': metrics_ready_count,
        'analytics_ready_count': analytics_ready_count,
        'provider_rows': provider_rows,
        'provider_health_pagination': pagination,
        'inventory_items': inventory_items,
        'freshness': freshness,
    }


def _overview_capacity_projection(
    *,
    context: dict[str, Any],
    scoped_providers: list[IntegrationInstance],
    selected_provider: IntegrationInstance | None,
    states: list[RegistryCollectionState],
) -> dict[str, Any]:
    artifact_query = RegistryArtifact.query.join(RegistryRepository).join(RegistryProject)
    if selected_provider is not None:
        artifact_query = artifact_query.filter(
            RegistryProject.integration_instance_id == selected_provider.id
        )
    artifact_total, total_size_bytes = artifact_query.with_entities(
        func.count(RegistryArtifact.id),
        func.coalesce(func.sum(RegistryArtifact.size_bytes), 0),
    ).one()
    artifact_total = int(artifact_total or 0)
    total_size_bytes = int(total_size_bytes or 0)

    metrics_by_provider = {
        int(provider.id): registry_metrics_readiness(provider)
        for provider in scoped_providers
    }
    metrics_ready_count = sum(
        metrics.get('status') == 'ready'
        for metrics in metrics_by_provider.values()
    )
    analytics_by_provider = _latest_registry_analytics(scoped_providers)
    capacity, forecast, top_consumers = _registry_capacity_views(
        scoped_providers=scoped_providers,
        analytics_by_provider=analytics_by_provider,
        total_size_bytes=total_size_bytes,
        artifact_total=artifact_total,
        committed_snapshot_count=sum(
            state.last_committed_at is not None for state in states
        ),
        metrics_ready_count=metrics_ready_count,
    )
    return {
        **context,
        'capacity': capacity,
        'forecast': forecast,
        'top_consumers': top_consumers,
    }


def build_overview(
    *,
    provider_id: int | None = None,
    active_tab: str = 'overview',
    provider_health_page: int | str | None = 1,
    provider_health_per_page: int = 5,
) -> dict[str, Any]:
    """Build only the Artifact Registry Fast Shell."""

    context, _providers_all, _selected, _scoped, _states = _overview_scope_context(
        provider_id=provider_id,
        active_tab=active_tab,
        provider_health_page=provider_health_page,
        provider_health_per_page=provider_health_per_page,
    )
    return context


def build_overview_section(
    section: str,
    *,
    provider_id: int | None = None,
    provider_health_page: int | str | None = 1,
    provider_health_per_page: int = 5,
) -> dict[str, Any]:
    """Build one bounded Artifact Registry dashboard section."""

    context, _providers_all, selected_provider, scoped_providers, states = (
        _overview_scope_context(
            provider_id=provider_id,
            active_tab=normalize_operational_tab(section),
            provider_health_page=provider_health_page,
            provider_health_per_page=provider_health_per_page,
        )
    )

    if section == 'kpi_cards':
        counts = _overview_kpi_values(selected_provider)
        return {
            **context,
            'kpis': [
                {
                    'label': 'Projects',
                    'value': counts['projects'],
                    'description': 'Committed provider-neutral namespaces.',
                    'icon': 'folder-kanban',
                },
                {
                    'label': 'Repositories',
                    'value': counts['repositories'],
                    'description': 'Committed Registry repositories.',
                    'icon': 'package-open',
                },
                {
                    'label': 'Artifacts',
                    'value': counts['artifacts'],
                    'description': 'Digest-oriented committed identities.',
                    'icon': 'fingerprint',
                },
                {
                    'label': 'Tags',
                    'value': counts['tags'],
                    'description': 'Mutable aliases linked to committed digests.',
                    'icon': 'tags',
                },
            ],
        }

    if section == 'provider_health':
        provider_rows, pagination, _metrics, _security = _provider_health_projection(
            scoped_providers=scoped_providers,
            states=states,
            selected_provider=selected_provider,
            provider_health_page=provider_health_page,
            provider_health_per_page=provider_health_per_page,
        )
        return {
            **context,
            'provider_rows': provider_rows,
            'provider_health_pagination': pagination,
        }

    if section == 'overview':
        return _overview_operations_projection(
            context=context,
            scoped_providers=scoped_providers,
            states=states,
            selected_provider=selected_provider,
            provider_health_page=provider_health_page,
            provider_health_per_page=provider_health_per_page,
        )

    if section == 'capacity':
        return _overview_capacity_projection(
            context=context,
            scoped_providers=scoped_providers,
            selected_provider=selected_provider,
            states=states,
        )

    if section == 'signals':
        return {
            **context,
            'alerts': _registry_alerts(scoped_providers),
            'recommended_actions': _registry_recommended_actions(selected_provider),
        }

    if section == 'reporting':
        return {
            **context,
            'reporting': _registry_reporting(selected_provider),
        }

    return context


def _project_row(item: RegistryProject) -> dict[str, Any]:
    return {
        'id': item.id,
        'name': item.name,
        'public': item.public,
        'repository_count': item.repository_count if item.repository_count is not None else len(item.repositories),
        'provider': item.integration_instance_id,
        'provider_id': item.integration_instance_id,
        'observed_at': item.observed_at,
    }


def _repository_row(item: RegistryRepository) -> dict[str, Any]:
    return {
        'id': item.id,
        'name': item.name,
        'project': item.project.name,
        'artifact_count': item.artifact_count if item.artifact_count is not None else len(item.artifacts),
        'pull_count': item.pull_count,
        'provider_id': item.project.integration_instance_id,
        'observed_at': item.observed_at,
    }


def _artifact_row(item: RegistryArtifact) -> dict[str, Any]:
    return {
        'id': item.id,
        'digest': item.digest,
        'digest_short': item.digest if len(item.digest) <= 28 else f'{item.digest[:18]}…{item.digest[-8:]}',
        'repository': item.repository.name,
        'project': item.repository.project.name,
        'type': item.artifact_type or item.media_type or 'OCI Artifact',
        'size': _fmt_bytes(item.size_bytes),
        'tags': [tag.name for tag in item.tags],
        'push_time': item.push_time,
        'provider_id': item.repository.project.integration_instance_id,
        'observed_at': item.observed_at,
    }


def _decorate_inventory_provider_provenance(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    provider_ids = {int(row['provider_id']) for row in rows if row.get('provider_id') is not None}
    providers = (
        IntegrationInstance.query.filter(IntegrationInstance.id.in_(sorted(provider_ids))).all()
        if provider_ids
        else []
    )
    provider_lookup = {int(provider.id): provider for provider in providers}
    for row in rows:
        provider_id = int(row['provider_id'])
        provider = provider_lookup.get(provider_id)
        metadata = (
            provider.metadata_json
            if provider is not None and isinstance(provider.metadata_json, dict)
            else {}
        )
        provider_key = str(provider.provider_key or 'registry') if provider is not None else 'registry'
        row['provider_name'] = provider.name if provider is not None else f'Registry #{provider_id}'
        row['provider_label'] = str(
            metadata.get('provider_label') or provider_key.replace('_', ' ').title()
        )
        row['provider_environment'] = (
            str(provider.environment) if provider is not None and provider.environment else 'Not Set'
        )
    return rows


def _inventory_resource_catalog(overview: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        'projects': {
            'key': 'projects',
            'title': 'Projects',
            'description': 'Provider-neutral Registry namespaces and visibility from committed snapshots.',
            'icon': 'folder-kanban',
            'count': overview['project_count'],
            'action_label': 'Browse Projects',
            'search_placeholder': 'Search projects or providers',
            'endpoint': 'artifact_registry.inventory_projects',
        },
        'repositories': {
            'key': 'repositories',
            'title': 'Repositories',
            'description': 'Committed repository catalogs linked to their Registry projects.',
            'icon': 'package-open',
            'count': overview['repository_count'],
            'action_label': 'Browse Repositories',
            'search_placeholder': 'Search repositories, projects, or providers',
            'endpoint': 'artifact_registry.inventory_repositories',
        },
        'artifacts': {
            'key': 'artifacts',
            'title': 'Artifacts',
            'description': 'Digest-oriented OCI identities with mutable tags and provider provenance.',
            'icon': 'fingerprint',
            'count': overview['artifact_count'],
            'action_label': 'Browse Artifacts',
            'search_placeholder': 'Search digests, repositories, tags, or providers',
            'endpoint': 'artifact_registry.inventory_artifacts',
        },
    }


def _inventory_snapshot_context(overview: dict[str, Any]) -> dict[str, Any]:
    provider_count = int(overview['provider_count'])
    snapshot_count = int(overview['snapshot_count'])
    stale_count = int(overview['stale_snapshot_count'])
    pending_count = int(overview['pending_snapshot_count'])
    failed_count = int(overview['failed_refresh_count'])
    exception_count = stale_count + pending_count + failed_count

    exception_parts: list[str] = []
    if stale_count:
        exception_parts.append(f'{stale_count} stale')
    if pending_count:
        exception_parts.append(f'{pending_count} pending')
    if failed_count:
        exception_parts.append(f'{failed_count} failed')

    if provider_count and snapshot_count == provider_count and not exception_count:
        coverage_tone = 'normal'
    elif snapshot_count:
        coverage_tone = 'warning'
    else:
        coverage_tone = 'unknown'

    return {
        'source_label': 'Committed Registry State',
        'status': overview['posture']['label'],
        'tone': overview['posture']['tone'],
        'description': (
            'KAORI reads retained provider-neutral Registry inventory without a live provider render dependency.'
        ),
        'latest_collected_at': overview['latest_committed_at'],
        'scope_label': overview['scope_label'],
        'coverage_label': (
            f'{snapshot_count} / {provider_count} Providers' if provider_count else 'No Providers'
        ),
        'coverage_tone': coverage_tone,
        'coverage_supporting': 'Providers with retained committed inventory evidence.',
        'exceptions_label': ' · '.join(exception_parts) if exception_parts else 'No Exceptions',
        'exceptions_tone': 'warning' if exception_count else 'normal',
        'exceptions_supporting': (
            'Stale, pending, or failed committed snapshot conditions.'
            if exception_count
            else 'No stale, pending, or failed snapshot conditions.'
        ),
        'exception_count': exception_count,
    }


def _inventory_base_context() -> dict[str, Any]:
    overview = build_overview()
    resource_catalog = _inventory_resource_catalog(overview)
    return {
        'setup': overview['setup'],
        'overview': overview,
        'snapshot_context': _inventory_snapshot_context(overview),
        'asset_catalog': list(resource_catalog.values()),
        'resource_catalog': resource_catalog,
    }


def build_inventory_overview() -> dict[str, Any]:
    return _inventory_base_context()


def build_inventory(*, resource: str, page: int, per_page: int, search: str = '') -> dict[str, Any]:
    resource = resource if resource in {'projects', 'repositories', 'artifacts'} else 'projects'
    search_value = search.strip().lower()

    if resource == 'repositories':
        items = RegistryRepository.query.options(
            joinedload(RegistryRepository.project),
            joinedload(RegistryRepository.artifacts),
        ).all()
        rows = [_repository_row(item) for item in items]
    elif resource == 'artifacts':
        items = RegistryArtifact.query.options(
            joinedload(RegistryArtifact.repository).joinedload(RegistryRepository.project),
            joinedload(RegistryArtifact.tags),
        ).all()
        rows = [_artifact_row(item) for item in items]
    else:
        items = RegistryProject.query.options(joinedload(RegistryProject.repositories)).all()
        rows = [_project_row(item) for item in items]

    rows = _decorate_inventory_provider_provenance(rows)
    if resource == 'repositories':
        filtered = [
            row
            for row in rows
            if not search_value
            or search_value
            in (
                f"{row['name']} {row['project']} {row['provider_name']} "
                f"{row['provider_label']} {row['provider_environment']}"
            ).lower()
        ]
    elif resource == 'artifacts':
        filtered = [
            row
            for row in rows
            if not search_value
            or search_value
            in (
                f"{row['digest']} {row['repository']} {row['project']} "
                f"{' '.join(row['tags'])} {row['provider_name']} "
                f"{row['provider_label']} {row['provider_environment']}"
            ).lower()
        ]
    else:
        filtered = [
            row
            for row in rows
            if not search_value
            or search_value
            in (
                f"{row['name']} {row['provider_name']} "
                f"{row['provider_label']} {row['provider_environment']}"
            ).lower()
        ]

    paged, pagination = paginate_sequence(filtered, page=page, per_page=per_page)
    context = _inventory_base_context()
    selected_resource = context['resource_catalog'][resource]
    snapshot_count = int(context['overview']['snapshot_count'])

    if search_value:
        empty_description = f"No committed {selected_resource['title'].lower()} match this search."
    elif snapshot_count == 0:
        empty_description = (
            'Run Artifact Registry inventory sync after the Registry provider read contract is eligible.'
        )
    else:
        empty_description = (
            f"The current committed Registry snapshot contains no {selected_resource['title'].lower()}."
        )

    return {
        **context,
        'resource': resource,
        'resource_label': selected_resource['title'],
        'resource_icon': selected_resource['icon'],
        'resource_description': selected_resource['description'],
        'resource_endpoint': selected_resource['endpoint'],
        'search_placeholder': selected_resource['search_placeholder'],
        'rows': paged,
        'pagination': pagination,
        'search': search,
        'total': len(filtered),
        'empty_description': empty_description,
    }


def build_security(*, page: int = 1, per_page: int = 5) -> dict[str, Any]:
    artifacts = RegistryArtifact.query.options(
        joinedload(RegistryArtifact.repository).joinedload(RegistryRepository.project),
    ).all()
    rows: list[dict[str, Any]] = []
    critical_total = high_total = scanned = signed = sbom_available = 0
    for artifact in artifacts:
        summary = artifact.vulnerability_summary if isinstance(artifact.vulnerability_summary, dict) else {}
        critical = int(summary.get('critical') or 0)
        high = int(summary.get('high') or 0)
        critical_total += critical
        high_total += high
        has_scan = _scan_evidence_ready(artifact.scan_status)
        scanned += int(has_scan)
        signature = str(artifact.signature_status or 'not_observed')
        sbom = str(artifact.sbom_status or 'not_observed')
        signed += int(signature == 'signed')
        sbom_available += int(sbom == 'available')
        scan_status = str(artifact.scan_status or 'not_scanned')
        scan_ready = _scan_evidence_ready(scan_status)
        rows.append(
            {
                'id': artifact.id,
                'digest': artifact.digest,
                'digest_short': artifact.digest if len(artifact.digest) <= 28 else f'{artifact.digest[:18]}…{artifact.digest[-8:]}',
                'repository': artifact.repository.name,
                'project': artifact.repository.project.name,
                'critical': critical,
                'high': high,
                'scan_label': scan_status.replace('_', ' ').title(),
                'scan_tone': 'normal' if scan_ready else ('unknown' if not has_scan else 'warning'),
                'signature_label': signature.replace('_', ' ').title(),
                'signature_tone': 'normal' if signature == 'signed' else ('warning' if signature == 'unsigned' else 'unknown'),
                'sbom_label': sbom.replace('_', ' ').title(),
                'sbom_tone': 'normal' if sbom == 'available' else ('info' if sbom == 'observed' else 'unknown'),
                'observed_at': artifact.observed_at,
            }
        )
    rows.sort(key=lambda item: (-item['critical'], -item['high'], item['project'], item['repository']))
    paged, pagination = paginate_sequence(rows, page=page, per_page=per_page)
    total = len(artifacts)
    coverage = round((scanned / total) * 100) if total else 0
    sbom_coverage = round((sbom_available / total) * 100) if total else 0
    if critical_total:
        posture = {'label': 'Critical Findings', 'tone': 'critical'}
    elif high_total:
        posture = {'label': 'Review Required', 'tone': 'warning'}
    elif total and scanned < total:
        posture = {'label': 'Coverage Incomplete', 'tone': 'warning'}
    elif total:
        posture = {'label': 'No High-Risk Findings', 'tone': 'normal'}
    else:
        posture = {'label': 'No Evidence', 'tone': 'unknown'}
    return {
        'setup': build_overview()['setup'],
        'total': total,
        'scanned': scanned,
        'scan_coverage': coverage,
        'critical': critical_total,
        'high': high_total,
        'signed': signed,
        'sbom_available': sbom_available,
        'sbom_coverage': sbom_coverage,
        'posture': posture,
        'rows': paged,
        'pagination': pagination,
    }



def build_runtime_usage(*, page: int = 1, per_page: int = 5) -> dict[str, Any]:
    bindings = RegistryWorkloadBinding.query.options(
        joinedload(RegistryWorkloadBinding.artifact)
        .joinedload(RegistryArtifact.repository)
        .joinedload(RegistryRepository.project),
    ).order_by(
        RegistryWorkloadBinding.namespace.asc(),
        RegistryWorkloadBinding.workload_name.asc(),
        RegistryWorkloadBinding.pod_name.asc(),
    ).all()
    rows: list[dict[str, Any]] = []
    digest_matches = tag_matches = critical_exposures = 0
    for binding in bindings:
        artifact = binding.artifact
        summary = artifact.vulnerability_summary if isinstance(artifact.vulnerability_summary, dict) else {}
        critical = int(summary.get('critical') or 0)
        high = int(summary.get('high') or 0)
        digest_matches += int(binding.match_type == 'digest')
        tag_matches += int(binding.match_type == 'tag')
        critical_exposures += int(critical > 0)
        if critical:
            vulnerability_label, vulnerability_tone = f'{critical} Critical', 'critical'
        elif high:
            vulnerability_label, vulnerability_tone = f'{high} High', 'warning'
        elif artifact.scan_status:
            vulnerability_label, vulnerability_tone = 'No Critical/High', 'normal'
        else:
            vulnerability_label, vulnerability_tone = 'Not Scanned', 'unknown'
        rows.append(
            {
                'id': binding.id,
                'project': artifact.repository.project.name,
                'repository': artifact.repository.name,
                'digest': artifact.digest,
                'digest_short': artifact.digest if len(artifact.digest) <= 28 else f'{artifact.digest[:18]}…{artifact.digest[-8:]}',
                'image_reference': binding.image_reference,
                'match_label': 'Digest Match' if binding.match_type == 'digest' else 'Tag Match',
                'match_tone': 'normal' if binding.match_type == 'digest' else 'info',
                'confidence': binding.confidence,
                'cluster_id': binding.cluster_id,
                'namespace': binding.namespace,
                'workload_type': binding.workload_type,
                'workload_name': binding.workload_name,
                'pod_name': binding.pod_name,
                'container_name': binding.container_name,
                'vulnerability_label': vulnerability_label,
                'vulnerability_tone': vulnerability_tone,
                'observed_at': binding.observed_at,
            }
        )
    paged, pagination = paginate_sequence(rows, page=page, per_page=per_page)
    if critical_exposures:
        posture = {'label': 'Critical Runtime Exposure', 'tone': 'critical'}
    elif rows and tag_matches:
        posture = {'label': 'Tag-Matched Runtime Evidence', 'tone': 'info'}
    elif rows:
        posture = {'label': 'Digest-Correlated', 'tone': 'normal'}
    else:
        posture = {'label': 'No Runtime Correlation', 'tone': 'unknown'}
    return {
        'setup': build_overview()['setup'],
        'total': len(rows),
        'digest_matches': digest_matches,
        'tag_matches': tag_matches,
        'critical_exposures': critical_exposures,
        'posture': posture,
        'rows': paged,
        'pagination': pagination,
    }



def _policy_state_view(value: str | None) -> dict[str, str]:
    key = str(value or 'not_collected').strip().lower()
    if key == 'configured':
        return {'label': 'Configured', 'tone': 'normal'}
    if key == 'not_configured':
        return {'label': 'Not Configured', 'tone': 'info'}
    if key == 'unsupported':
        return {'label': 'Unsupported', 'tone': 'unknown'}
    if key == 'unavailable':
        return {'label': 'Unavailable', 'tone': 'warning'}
    return {'label': 'Not Collected', 'tone': 'unknown'}


def build_governance() -> dict[str, Any]:
    from flask import url_for

    overview = build_overview()
    identities = _providers()
    identity_by_id = {int(item.id): item for item in identities}
    collection_states = {
        int(item.integration_instance_id): item
        for item in RegistryCollectionState.query.all()
    }
    governance_states = {
        int(item.integration_instance_id): item
        for item in RegistryGovernanceState.query.all()
    }
    webhook_endpoints = {
        int(item.integration_instance_id): item
        for item in RegistryWebhookEndpoint.query.all()
    }

    project_rows: list[dict[str, Any]] = []
    governance_items = RegistryProjectGovernance.query.options(
        joinedload(RegistryProjectGovernance.project),
    ).order_by(RegistryProjectGovernance.observed_at.desc()).all()
    for item in governance_items:
        identity = identity_by_id.get(int(item.project.integration_instance_id))
        retention = _policy_state_view(item.retention_status)
        immutability = _policy_state_view(item.immutability_status)
        project_rows.append(
            {
                'project': item.project.name,
                'provider_label': str((identity.metadata_json or {}).get('provider_label') or identity.provider_key.title())
                if identity is not None else 'Registry',
                'retention_label': retention['label'],
                'retention_tone': retention['tone'],
                'immutability_label': immutability['label'],
                'immutability_tone': immutability['tone'],
                'observed_at': item.observed_at,
            }
        )

    replication_rows: list[dict[str, Any]] = []
    for item in RegistryReplicationPolicy.query.order_by(RegistryReplicationPolicy.name.asc()).all():
        identity = identity_by_id.get(int(item.integration_instance_id))
        replication_rows.append(
            {
                'name': item.name,
                'provider_label': str((identity.metadata_json or {}).get('provider_label') or identity.provider_key.title())
                if identity is not None else 'Registry',
                'enabled': item.enabled,
                'trigger_type': item.trigger_type,
                'destination_registry': item.destination_registry,
                'destination_namespace': item.destination_namespace,
                'observed_at': item.observed_at,
            }
        )

    metrics_by_id = {int(identity.id): registry_metrics_readiness(identity) for identity in identities}
    webhook_rows: list[dict[str, Any]] = []
    for identity in identities:
        endpoint = webhook_endpoints.get(int(identity.id))
        enabled = bool(endpoint and endpoint.enabled and endpoint.token_digest)
        webhook_rows.append(
            {
                'id': int(identity.id),
                'name': identity.name,
                'enabled': enabled,
                'status_label': 'Ready' if enabled else 'Not Configured',
                'tone': 'normal' if enabled else 'unknown',
                'last_event_at': endpoint.last_event_at if endpoint else None,
                'url': url_for(
                    'artifact_registry.webhook_receive',
                    integration_instance_id=identity.id,
                    _external=True,
                ),
            }
        )

    inventory_ready_count = sum(
        1
        for identity in identities
        if (collection_states.get(int(identity.id)) is not None)
        and collection_states[int(identity.id)].status == 'ready'
    )
    governance_ready_count = sum(
        1
        for identity in identities
        if (governance_states.get(int(identity.id)) is not None)
        and governance_states[int(identity.id)].status == 'ready'
    )
    metrics_ready_count = sum(
        1 for item in metrics_by_id.values() if item.get('status') == 'ready'
    )
    webhook_ready_count = sum(1 for row in webhook_rows if row['enabled'])

    readiness_cards = [
        {
            'label': 'Provider Readiness',
            'value': f"{sum(identity.readiness_status == 'ready' for identity in identities)}/{len(identities)} Ready",
            'status_label': 'Independent',
            'tone': 'info',
            'detail': 'Harbor/API provider validation remains separate from inventory, metrics, and webhook readiness.',
        },
        {
            'label': 'Inventory Readiness',
            'value': f'{inventory_ready_count}/{len(identities)} Ready',
            'status_label': 'Committed',
            'tone': 'normal' if inventory_ready_count == len(identities) and identities else 'warning',
            'detail': 'Scheduled reconciliation commits Registry truth and remains available during metrics outages.',
        },
        {
            'label': 'Metrics Readiness',
            'value': f'{metrics_ready_count}/{len(identities)} Ready',
            'status_label': 'Optional Dependency',
            'tone': 'normal' if metrics_ready_count else 'unknown',
            'detail': 'Metrics Source binding is independently validated; it never controls Registry provider readiness.',
        },
        {
            'label': 'Webhook Readiness',
            'value': f'{webhook_ready_count}/{len(identities)} Ready',
            'status_label': 'Fast Path',
            'tone': 'normal' if webhook_ready_count else 'unknown',
            'detail': 'Authenticated idempotent events accelerate refresh; scheduled reconciliation repairs missed events.',
        },
    ]

    if not identities:
        posture = {'label': 'Setup Required', 'tone': 'unknown'}
    elif inventory_ready_count < len(identities):
        posture = {'label': 'Inventory Attention', 'tone': 'warning'}
    elif governance_ready_count < len(identities):
        posture = {'label': 'Governance Pending', 'tone': 'warning'}
    else:
        posture = {'label': 'Committed Evidence Ready', 'tone': 'normal'}

    return {
        'setup': overview['setup'],
        'provider_count': len(identities),
        'project_count': len(project_rows),
        'replication_count': len(replication_rows),
        'inventory_ready_count': inventory_ready_count,
        'governance_ready_count': governance_ready_count,
        'metrics_ready_count': metrics_ready_count,
        'webhook_ready_count': webhook_ready_count,
        'posture': posture,
        'readiness_cards': readiness_cards,
        'project_rows': project_rows,
        'replication_rows': replication_rows,
        'webhook_rows': webhook_rows,
        'metrics_by_id': metrics_by_id,
    }



def build_analytics() -> dict[str, Any]:
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
        'critical_findings': 0,
        'high_findings': 0,
        'critical_runtime_artifacts': 0,
        'tag_only_bindings': 0,
        'runtime_scan_gaps': 0,
        'metrics_ready': 0,
    }
    forecast_rows: list[dict[str, Any]] = []

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
                }
            )
            continue
        payload = snapshot.payload_json
        inventory = payload.get('inventory') if isinstance(payload.get('inventory'), dict) else {}
        security = payload.get('security') if isinstance(payload.get('security'), dict) else {}
        runtime = payload.get('runtime') if isinstance(payload.get('runtime'), dict) else {}
        metrics = payload.get('metrics') if isinstance(payload.get('metrics'), dict) else {}
        capacity = payload.get('capacity') if isinstance(payload.get('capacity'), dict) else {}

        aggregate['projects'] += int(inventory.get('projects') or 0)
        aggregate['repositories'] += int(inventory.get('repositories') or 0)
        aggregate['artifacts'] += int(inventory.get('artifacts') or 0)
        aggregate['total_size_bytes'] += int(inventory.get('total_size_bytes') or 0)
        aggregate['stale_candidates'] += int(inventory.get('stale_candidate_count') or 0)
        aggregate['critical_findings'] += int(security.get('critical_findings') or 0)
        aggregate['high_findings'] += int(security.get('high_findings') or 0)
        aggregate['critical_runtime_artifacts'] += int(runtime.get('critical_runtime_artifacts') or 0)
        aggregate['tag_only_bindings'] += int(runtime.get('tag_only_bindings') or 0)
        aggregate['runtime_scan_gaps'] += int(runtime.get('runtime_scan_gaps') or 0)
        aggregate['metrics_ready'] += int(metrics.get('status') == 'ready')

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
                'metrics': metrics,
                'growth': payload.get('growth') if isinstance(payload.get('growth'), dict) else {},
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

    recommendations = get_active_recommendation_findings(domain='registry', limit=5)
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
    active_signal_count = (
        aggregate['critical_runtime_artifacts']
        + aggregate['tag_only_bindings']
        + aggregate['runtime_scan_gaps']
        + aggregate['stale_candidates']
    )
    if not latest_rows or not any(row.get('snapshot') for row in latest_rows):
        posture = {'label': 'Materialization Required', 'tone': 'warning'}
    elif aggregate['critical_runtime_artifacts']:
        posture = {'label': 'Critical Runtime Exposure', 'tone': 'critical'}
    elif active_signal_count:
        posture = {'label': 'Review Required', 'tone': 'warning'}
    else:
        posture = {'label': 'No Active Analytics Signals', 'tone': 'normal'}

    return {
        'setup': overview['setup'],
        'provider_count': len(identities),
        'snapshot_count': sum(bool(row.get('snapshot')) for row in latest_rows),
        'aggregate': aggregate,
        'latest_rows': latest_rows,
        'forecast_rows': sorted(
            forecast_rows,
            key=lambda row: (
                row.get('days_to_quota') is None,
                float(row.get('days_to_quota') or 1e18),
            ),
        ),
        'recommendations': recommendation_rows,
        'recommendation_count': len(recommendation_rows),
        'active_signal_count': active_signal_count,
        'posture': posture,
    }
