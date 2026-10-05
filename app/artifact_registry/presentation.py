from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import case, func, or_
from sqlalchemy.orm import joinedload

from app.artifact_registry.correlation_sync_jobs import correlation_prerequisites
from app.artifact_registry.observability import registry_metrics_readiness
from app.artifact_registry.security.contracts import (
    SUCCESSFUL_REGISTRY_SCAN_STATUSES,
    registry_scan_evidence_ready,
)
from app.common.pagination import paginate_query, paginate_sequence
from app.dashboards.common.operational import normalize_operational_tab
from app.intelligence.alert_intelligence.dashboard_cases import active_recommendation_alert_cases
from app.intelligence.catalog import INTELLIGENCE_CATALOG
from app.intelligence.dashboard_recommendations import get_dashboard_recommendation_findings
from app.models.cluster import Cluster
from app.models.integration import IntegrationInstance
from app.models.job import JobExecution
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
    RegistryWorkloadBinding,
)

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
    refresh_failed = bool(state.last_error)
    stale = bool(
        committed_at is not None
        and committed_at < datetime.now(UTC) - timedelta(hours=FRESHNESS_HOURS)
    )
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
                'description': 'Remaining Registry quota headroom.',
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


def _registry_alerts(selected_provider: IntegrationInstance | None) -> dict[str, Any]:
    catalog_rules = sum(
        str(rule.get('domain') or '') == 'registry'
        and str(rule.get('status') or '') == 'available'
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
                'description': str(
                    case.summary
                    or case.target
                    or 'KAORI Registry recommendation alert case.'
                ),
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
                                SUCCESSFUL_REGISTRY_SCAN_STATUSES
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
        elif state is not None and state.last_error:
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
        .filter(
            func.lower(RegistryScanSnapshot.status).in_(SUCCESSFUL_REGISTRY_SCAN_STATUSES)
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
            and selected_collection_state.last_error
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
                    missing='No analytics snapshot',
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
                    missing='No analytics snapshot',
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
            'alerts': _registry_alerts(selected_provider),
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
            'KAORI reads committed provider-neutral Registry inventory.'
        ),
        'latest_collected_at': overview['latest_committed_at'],
        'scope_label': overview['scope_label'],
        'coverage_label': (
            f'{snapshot_count} / {provider_count} Providers' if provider_count else 'No Providers'
        ),
        'coverage_tone': coverage_tone,
        'coverage_supporting': 'Providers with committed evidence.',
        'exceptions_label': ' · '.join(exception_parts) if exception_parts else 'No Exceptions',
        'exceptions_tone': 'warning' if exception_count else 'normal',
        'exceptions_supporting': (
            'Stale, pending, or failed committed snapshot conditions.'
            if exception_count
            else 'No snapshot issues.'
        ),
        'exception_count': exception_count,
    }


def _inventory_fleet_readings(overview: dict[str, Any]) -> list[dict[str, str]]:
    provider_count = int(overview['provider_count'])
    snapshot_count = int(overview['snapshot_count'])
    exception_count = (
        int(overview['stale_snapshot_count'])
        + int(overview['pending_snapshot_count'])
        + int(overview['failed_refresh_count'])
    )
    project_count = int(overview['project_count'])
    visibility_observed = RegistryProject.query.filter(
        RegistryProject.public.is_not(None)
    ).count()
    public_projects = RegistryProject.query.filter(RegistryProject.public.is_(True)).count()

    if provider_count == 0:
        coverage_title, coverage_tone = 'No Registry Providers', 'unknown'
        coverage_description = 'Register a Registry provider to establish committed inventory.'
    elif snapshot_count == provider_count:
        coverage_title, coverage_tone = f'{snapshot_count}/{provider_count} Providers Committed', 'normal'
        coverage_description = 'Every configured Registry provider has retained a committed inventory snapshot as current KAORI evidence.'
    else:
        coverage_title, coverage_tone = f'{snapshot_count}/{provider_count} Providers Committed', 'warning'
        coverage_description = 'One or more Registry providers still require a committed inventory snapshot.'

    if exception_count:
        exception_title, exception_tone = f'{exception_count} Snapshot Attention', 'warning'
        exception_description = 'Review stale, pending, or failed Registry inventory conditions.'
    else:
        exception_title, exception_tone = 'No Snapshot Attention', 'normal'
        exception_description = 'No stale, pending, or failed committed Registry snapshot condition is active.'

    if project_count == 0:
        visibility_title, visibility_tone = 'No Visibility Evidence', 'unknown'
        visibility_description = 'No committed Registry projects are available for visibility assessment.'
    elif visibility_observed < project_count:
        visibility_title, visibility_tone = f'{visibility_observed}/{project_count} Visibility Observed', 'warning'
        visibility_description = (
            f'{public_projects} public project(s); remaining project visibility still requires provider evidence.'
        )
    else:
        visibility_title, visibility_tone = f'{visibility_observed}/{project_count} Visibility Observed', 'normal'
        visibility_description = (
            f'Project visibility evidence is complete; {public_projects} project(s) are declared public.'
        )

    return [
        {
            'title': coverage_title,
            'description': coverage_description,
            'icon': 'database-backup',
            'tone': coverage_tone,
        },
        {
            'title': exception_title,
            'description': exception_description,
            'icon': 'triangle-alert',
            'tone': exception_tone,
        },
        {
            'title': visibility_title,
            'description': visibility_description,
            'icon': 'globe-2',
            'tone': visibility_tone,
        },
    ]


def _inventory_base_context() -> dict[str, Any]:
    overview = build_overview()
    counts = _overview_kpi_values(None)
    overview = {
        **overview,
        'project_count': counts['projects'],
        'repository_count': counts['repositories'],
        'artifact_count': counts['artifacts'],
    }
    resource_catalog = _inventory_resource_catalog(overview)
    return {
        'setup': overview['setup'],
        'overview': overview,
        'snapshot_context': _inventory_snapshot_context(overview),
        'fleet_readings': _inventory_fleet_readings(overview),
        'asset_catalog': list(resource_catalog.values()),
        'resource_catalog': resource_catalog,
    }


def build_inventory_overview() -> dict[str, Any]:
    return _inventory_base_context()


def _inventory_resource_posture_metrics(
    resource: str,
    rows: list[dict[str, Any]],
) -> list[tuple[str, str, Any, str, str]]:
    provider_count = len(
        {int(row['provider_id']) for row in rows if row.get('provider_id') is not None}
    )

    if resource == 'repositories':
        artifact_count = sum(int(row.get('artifact_count') or 0) for row in rows)
        pull_evidence_count = sum(row.get('pull_count') is not None for row in rows)
        return [
            (
                'package-open',
                'Repositories',
                len(rows),
                'Committed Registry repository identities retained across the current provider-neutral inventory snapshot.',
                'brand',
            ),
            (
                'database-backup',
                'Registry Sources',
                provider_count,
                'Registry providers contributing committed repository evidence.',
                'brand',
            ),
            (
                'fingerprint',
                'Artifacts',
                artifact_count,
                'Committed artifact identities referenced by repository inventory.',
                'brand',
            ),
            (
                'activity',
                'Pull Counts Observed',
                pull_evidence_count,
                'Repositories with committed provider pull-count evidence.',
                'info' if pull_evidence_count else 'unknown',
            ),
        ]

    if resource == 'artifacts':
        tagged_artifacts = sum(bool(row.get('tags')) for row in rows)
        untagged_artifacts = max(len(rows) - tagged_artifacts, 0)
        return [
            (
                'fingerprint',
                'Artifacts',
                len(rows),
                'Committed digest-oriented Registry artifact identities.',
                'brand',
            ),
            (
                'database-backup',
                'Registry Sources',
                provider_count,
                'Registry providers contributing committed artifact evidence.',
                'brand',
            ),
            (
                'tags',
                'Tagged Artifacts',
                tagged_artifacts,
                'Artifacts with one or more committed mutable tag references.',
                'info' if tagged_artifacts else 'unknown',
            ),
            (
                'tag',
                'Untagged Artifacts',
                untagged_artifacts,
                'Committed artifacts without a current tag reference.',
                'info' if untagged_artifacts else 'normal',
            ),
        ]

    public_projects = sum(row.get('public') is True for row in rows)
    visibility_missing = sum(row.get('public') is None for row in rows)
    return [
        (
            'folder-kanban',
            'Projects',
            len(rows),
            'Committed Registry project identities.',
            'brand',
        ),
        (
            'database-backup',
            'Registry Sources',
            provider_count,
            'Registry providers contributing committed project evidence.',
            'brand',
        ),
        (
            'globe-2',
            'Public Projects',
            public_projects,
            'Projects marked public by provider evidence.',
            'info' if public_projects else 'normal',
        ),
        (
            'circle-help',
            'Visibility Not Observed',
            visibility_missing,
            'Projects without committed visibility evidence.',
            'warning' if visibility_missing else 'normal',
        ),
    ]


def build_inventory(
    *,
    resource: str,
    page: int,
    per_page: int,
    search: str = '',
    source_id: int | None = None,
    environment: str = '',
    visibility: str = '',
) -> dict[str, Any]:
    resource = resource if resource in {'projects', 'repositories', 'artifacts'} else 'projects'
    search_value = search.strip().lower()
    environment_value = environment.strip()
    visibility_value = visibility.strip().lower()
    if visibility_value not in {'public', 'private', 'not_observed'}:
        visibility_value = ''

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

    source_lookup: dict[int, dict[str, Any]] = {}
    for row in rows:
        provider_id = int(row['provider_id'])
        source_lookup.setdefault(
            provider_id,
            {
                'id': provider_id,
                'name': row['provider_name'],
                'provider_label': row['provider_label'],
                'environment': row['provider_environment'],
            },
        )
    source_options = sorted(
        source_lookup.values(),
        key=lambda item: (str(item['name']).lower(), int(item['id'])),
    )
    environment_options = sorted(
        {
            str(row['provider_environment'])
            for row in rows
            if str(row.get('provider_environment') or '').strip()
        },
        key=str.lower,
    )
    resource_posture_metrics = _inventory_resource_posture_metrics(resource, rows)

    if source_id is not None:
        rows = [row for row in rows if int(row['provider_id']) == int(source_id)]
    if environment_value:
        rows = [
            row
            for row in rows
            if str(row['provider_environment']).lower() == environment_value.lower()
        ]
    if resource == 'projects':
        if visibility_value == 'public':
            rows = [row for row in rows if row['public'] is True]
        elif visibility_value == 'private':
            rows = [row for row in rows if row['public'] is False]
        elif visibility_value == 'not_observed':
            rows = [row for row in rows if row['public'] is None]

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
    posture_copy = {
        'projects': {
            'title': 'Project Inventory Posture',
            'intro': 'Review committed project coverage, Registry-source participation, and visibility evidence.',
            'description': 'Committed project catalog posture across the current Artifact Registry inventory.',
        },
        'repositories': {
            'title': 'Repository Inventory Posture',
            'intro': 'Review committed repository coverage, Registry-source participation, and catalog evidence.',
            'description': 'Committed repository catalog posture across the current Artifact Registry inventory.',
        },
        'artifacts': {
            'title': 'Artifact Inventory Posture',
            'intro': 'Review committed artifact coverage, Registry-source participation, and tag evidence.',
            'description': 'Committed artifact catalog posture across the current Artifact Registry inventory.',
        },
    }[resource]
    snapshot_count = int(context['overview']['snapshot_count'])
    has_filters = bool(
        search_value
        or source_id is not None
        or environment_value
        or (resource == 'projects' and visibility_value)
    )

    if has_filters:
        empty_description = (
            f"No committed {selected_resource['title'].lower()} match the active filters."
        )
    elif snapshot_count == 0:
        empty_description = (
            'Run Artifact Registry inventory sync after the Registry provider read contract is eligible.'
        )
    else:
        empty_description = (
            f"The current committed Registry snapshot contains no {selected_resource['title'].lower()}."
        )

    filter_query: dict[str, Any] = {
        'q': search,
        'source_id': source_id,
        'environment': environment_value,
    }
    if resource == 'projects':
        filter_query['visibility'] = visibility_value

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
        'filters': {
            'source_id': source_id,
            'environment': environment_value,
            'visibility': visibility_value,
        },
        'filter_query': filter_query,
        'has_filters': has_filters,
        'source_options': source_options,
        'environment_options': environment_options,
        'resource_posture_metrics': resource_posture_metrics,
        'resource_posture_title': posture_copy['title'],
        'resource_posture_intro': posture_copy['intro'],
        'resource_posture_description': posture_copy['description'],
        'visibility_options': (
            [
                {'value': 'public', 'label': 'Public'},
                {'value': 'private', 'label': 'Private'},
                {'value': 'not_observed', 'label': 'Not Observed'},
            ]
            if resource == 'projects'
            else []
        ),
    }


def build_inventory_project_detail(project_id: int) -> dict[str, Any] | None:
    project = (
        RegistryProject.query.options(
            joinedload(RegistryProject.repositories).joinedload(RegistryRepository.artifacts)
        )
        .filter(RegistryProject.id == int(project_id))
        .first()
    )
    if project is None:
        return None

    provider = IntegrationInstance.query.filter(
        IntegrationInstance.id == int(project.integration_instance_id)
    ).first()
    state = RegistryCollectionState.query.filter(
        RegistryCollectionState.integration_instance_id == int(project.integration_instance_id)
    ).first()
    snapshot = _state_view(state)
    provider_metadata = (
        dict(project.provider_metadata)
        if isinstance(project.provider_metadata, dict)
        else {}
    )

    if project.public is True:
        visibility_state = {'label': 'Public', 'tone': 'info', 'icon': 'globe-2'}
    elif project.public is False:
        visibility_state = {'label': 'Private', 'tone': 'normal', 'icon': 'lock-keyhole'}
    else:
        visibility_state = {'label': 'Not Observed', 'tone': 'unknown', 'icon': 'circle-help'}

    repositories = [
        {
            'id': int(repository.id),
            'name': repository.name,
            'artifact_count': (
                int(repository.artifact_count)
                if repository.artifact_count is not None
                else len(repository.artifacts)
            ),
            'pull_count': repository.pull_count,
            'observed_at': repository.observed_at,
        }
        for repository in sorted(project.repositories, key=lambda item: item.name.lower())
    ]

    provider_key = str(provider.provider_key or 'registry') if provider is not None else 'registry'
    metadata = (
        provider.metadata_json
        if provider is not None and isinstance(provider.metadata_json, dict)
        else {}
    )

    return {
        'id': int(project.id),
        'name': project.name,
        'provider_native_id': project.provider_native_id or 'Not Collected',
        'visibility': visibility_state,
        'repository_count': (
            int(project.repository_count)
            if project.repository_count is not None
            else len(project.repositories)
        ),
        'provider_id': int(project.integration_instance_id),
        'provider_name': (
            provider.name
            if provider is not None
            else f'Registry #{project.integration_instance_id}'
        ),
        'provider_label': str(
            metadata.get('provider_label') or provider_key.replace('_', ' ').title()
        ),
        'provider_environment': (
            str(provider.environment) if provider is not None and provider.environment else 'Not Set'
        ),
        'observed_at': project.observed_at,
        'snapshot': snapshot,
        'repositories': repositories,
        'repository_preview': repositories[:25],
        'repository_truncated': len(repositories) > 25,
        'provider_metadata': provider_metadata,
    }


def _inventory_detail_provider_context(integration_instance_id: int) -> dict[str, Any]:
    provider = IntegrationInstance.query.filter(
        IntegrationInstance.id == int(integration_instance_id)
    ).first()
    state = RegistryCollectionState.query.filter(
        RegistryCollectionState.integration_instance_id == int(integration_instance_id)
    ).first()
    metadata = (
        provider.metadata_json
        if provider is not None and isinstance(provider.metadata_json, dict)
        else {}
    )
    provider_key = str(provider.provider_key or 'registry') if provider is not None else 'registry'
    return {
        'provider_id': int(integration_instance_id),
        'provider_name': (
            provider.name if provider is not None else f'Registry #{integration_instance_id}'
        ),
        'provider_label': str(
            metadata.get('provider_label') or provider_key.replace('_', ' ').title()
        ),
        'provider_environment': (
            str(provider.environment) if provider is not None and provider.environment else 'Not Set'
        ),
        'snapshot': _state_view(state),
    }


def build_inventory_repository_detail(repository_id: int) -> dict[str, Any] | None:
    repository = (
        RegistryRepository.query.options(
            joinedload(RegistryRepository.project),
            joinedload(RegistryRepository.artifacts).joinedload(RegistryArtifact.tags),
        )
        .filter(RegistryRepository.id == int(repository_id))
        .first()
    )
    if repository is None:
        return None

    source = _inventory_detail_provider_context(repository.project.integration_instance_id)
    artifacts = [
        {
            'id': int(artifact.id),
            'digest': artifact.digest,
            'digest_short': (
                artifact.digest
                if len(artifact.digest) <= 32
                else f'{artifact.digest[:20]}…{artifact.digest[-10:]}'
            ),
            'type': artifact.artifact_type or artifact.media_type or 'OCI Artifact',
            'size': _fmt_bytes(artifact.size_bytes),
            'tag_count': len(artifact.tags),
            'tags': [tag.name for tag in artifact.tags[:3]],
            'observed_at': artifact.observed_at,
        }
        for artifact in sorted(repository.artifacts, key=lambda item: item.digest)
    ]
    provider_metadata = (
        dict(repository.provider_metadata)
        if isinstance(repository.provider_metadata, dict)
        else {}
    )
    return {
        'id': int(repository.id),
        'name': repository.name,
        'provider_native_id': repository.provider_native_id or 'Not Collected',
        'description': repository.description or 'No provider description collected.',
        'project_id': int(repository.project.id),
        'project_name': repository.project.name,
        'artifact_count': (
            int(repository.artifact_count)
            if repository.artifact_count is not None
            else len(repository.artifacts)
        ),
        'pull_count': repository.pull_count,
        'provider_created_at': repository.provider_created_at,
        'provider_updated_at': repository.provider_updated_at,
        'observed_at': repository.observed_at,
        'artifacts': artifacts,
        'artifact_preview': artifacts[:25],
        'artifact_truncated': len(artifacts) > 25,
        'provider_metadata': provider_metadata,
        **source,
    }


def build_inventory_artifact_detail(artifact_id: int) -> dict[str, Any] | None:
    artifact = (
        RegistryArtifact.query.options(
            joinedload(RegistryArtifact.repository).joinedload(RegistryRepository.project),
            joinedload(RegistryArtifact.tags),
        )
        .filter(RegistryArtifact.id == int(artifact_id))
        .first()
    )
    if artifact is None:
        return None

    repository = artifact.repository
    project = repository.project
    source = _inventory_detail_provider_context(project.integration_instance_id)
    tags = [
        {
            'id': int(tag.id),
            'name': tag.name,
            'provider_native_id': tag.provider_native_id or 'Not Collected',
            'push_time': tag.push_time,
            'pull_time': tag.pull_time,
            'observed_at': tag.observed_at,
        }
        for tag in sorted(artifact.tags, key=lambda item: item.name.lower())
    ]
    provider_metadata = (
        dict(artifact.provider_metadata)
        if isinstance(artifact.provider_metadata, dict)
        else {}
    )
    return {
        'id': int(artifact.id),
        'digest': artifact.digest,
        'digest_short': (
            artifact.digest
            if len(artifact.digest) <= 40
            else f'{artifact.digest[:24]}…{artifact.digest[-12:]}'
        ),
        'digest_algorithm': artifact.digest_algorithm or 'unknown',
        'provider_native_id': artifact.provider_native_id or 'Not Collected',
        'type': artifact.artifact_type or 'Not Collected',
        'media_type': artifact.media_type or 'Not Collected',
        'size_bytes': artifact.size_bytes,
        'size': _fmt_bytes(artifact.size_bytes),
        'push_time': artifact.push_time,
        'pull_time': artifact.pull_time,
        'observed_at': artifact.observed_at,
        'repository_id': int(repository.id),
        'repository_name': repository.name,
        'project_id': int(project.id),
        'project_name': project.name,
        'tag_count': len(tags),
        'tags': tags,
        'tag_preview': tags[:25],
        'tag_truncated': len(tags) > 25,
        'provider_metadata': provider_metadata,
        **source,
    }


def build_security(*, page: int = 1, per_page: int = 5) -> dict[str, Any]:
    """Compatibility projection for callers using the aggregate presentation module."""
    from app.artifact_registry.security.presentation import build_security as build_security_workspace

    return build_security_workspace(page=page, per_page=per_page)


def _runtime_match_state(match_type: str, confidence: str) -> dict[str, str]:
    if str(match_type or '').lower() == 'digest':
        return {
            'label': 'Digest Match',
            'tone': 'normal',
            'confidence': 'Strong',
            'description': 'Immutable digest identity match.',
        }
    return {
        'label': 'Tag Match',
        'tone': 'warning',
        'confidence': str(confidence or 'medium').replace('_', ' ').title(),
        'description': 'Mutable reference; lower confidence.',
    }


def _runtime_security_state(
    scan_status: str | None,
    summary: dict[str, Any] | None,
) -> dict[str, Any]:
    normalized = summary if isinstance(summary, dict) else {}
    critical = int(normalized.get('critical') or 0)
    high = int(normalized.get('high') or 0)
    if critical:
        label, tone = f'{critical} Critical', 'critical'
    elif high:
        label, tone = f'{high} High', 'warning'
    elif registry_scan_evidence_ready(scan_status):
        label, tone = 'No Critical/High', 'normal'
    else:
        label, tone = 'Not Scanned', 'unknown'
    return {
        'critical': critical,
        'high': high,
        'label': label,
        'tone': tone,
        'exposed': bool(critical or high),
        'scanned': registry_scan_evidence_ready(scan_status),
    }


def _runtime_security_index() -> tuple[dict[int, dict[str, Any]], set[int], set[int], set[int]]:
    security_by_artifact: dict[int, dict[str, Any]] = {}
    critical_ids: set[int] = set()
    high_ids: set[int] = set()
    scanned_ids: set[int] = set()
    rows = RegistryArtifact.query.with_entities(
        RegistryArtifact.id,
        RegistryArtifact.scan_status,
        RegistryArtifact.vulnerability_summary,
    ).all()
    for artifact_id, scan_status, vulnerability_summary in rows:
        state = _runtime_security_state(scan_status, vulnerability_summary)
        normalized_id = int(artifact_id)
        security_by_artifact[normalized_id] = state
        if state['critical']:
            critical_ids.add(normalized_id)
        if state['high']:
            high_ids.add(normalized_id)
        if state['scanned']:
            scanned_ids.add(normalized_id)
    return security_by_artifact, critical_ids, high_ids, scanned_ids


def _runtime_parse_observed_at(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    text = str(value or '').strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace('Z', '+00:00'))
    except ValueError:
        return None


def _runtime_prerequisite_guidance(
    prerequisites: dict[str, int | bool],
    *,
    has_committed_snapshot: bool,
) -> dict[str, Any]:
    eligible = bool(prerequisites.get('eligible'))
    missing_registry = int(prerequisites.get('artifact_count') or 0) == 0
    missing_kubernetes = int(prerequisites.get('pod_count') or 0) == 0
    review_step = (
        'Review Updated Bindings'
        if has_committed_snapshot
        else 'Review Committed Bindings'
    )

    if missing_registry and missing_kubernetes:
        title = 'Committed Inventories Required'
        description = (
            'Runtime correlation requires committed Artifact Registry artifacts and '
            'current Kubernetes Pod inventory before the first materialization.'
        )
        refresh_description = (
            'Existing committed Runtime Usage remains readable, but correlation refresh '
            'requires committed Artifact Registry artifacts and current Kubernetes Pod inventory.'
        )
        steps = [
            'Sync Artifact Registry Inventory',
            'Sync Kubernetes Inventory',
            'Run Runtime Correlation',
            review_step,
        ]
        action_endpoint = 'artifact_registry.inventory'
        action_label = 'Open Registry Inventory'
        action_icon = 'package-open'
        action_permission = 'artifact_registry.view'
    elif missing_registry:
        title = 'Registry Inventory Required'
        description = (
            'Runtime correlation requires committed Artifact Registry artifacts before '
            'the first materialization.'
        )
        refresh_description = (
            'Existing committed Runtime Usage remains readable, but correlation refresh '
            'requires committed Artifact Registry artifacts.'
        )
        steps = [
            'Sync Artifact Registry Inventory',
            'Run Runtime Correlation',
            review_step,
        ]
        action_endpoint = 'artifact_registry.inventory'
        action_label = 'Open Registry Inventory'
        action_icon = 'package-open'
        action_permission = 'artifact_registry.view'
    elif missing_kubernetes:
        title = 'Kubernetes Inventory Required'
        description = (
            'Runtime correlation requires a current committed Kubernetes Pod inventory '
            'generation before the first materialization.'
        )
        refresh_description = (
            'Existing committed Runtime Usage remains readable, but correlation refresh '
            'requires a current committed Kubernetes Pod inventory generation.'
        )
        steps = [
            'Sync Kubernetes Inventory',
            'Run Runtime Correlation',
            review_step,
        ]
        action_endpoint = 'inventory.overview'
        action_label = 'Open Kubernetes Inventory'
        action_icon = 'boxes'
        action_permission = 'inventory.view'
    else:
        title = 'Correlation Prerequisites Ready'
        description = 'Committed Registry and Kubernetes evidence is ready for correlation.'
        refresh_description = description
        steps = []
        action_endpoint = None
        action_label = None
        action_icon = 'waypoints'
        action_permission = None

    return {
        'is_blocked': bool(not eligible and not has_committed_snapshot),
        'refresh_blocked': bool(not eligible and has_committed_snapshot),
        'missing_registry': missing_registry,
        'missing_kubernetes': missing_kubernetes,
        'title': title,
        'description': description,
        'refresh_description': refresh_description,
        'steps': steps,
        'action_endpoint': action_endpoint,
        'action_label': action_label,
        'action_icon': action_icon,
        'action_permission': action_permission,
    }


def build_runtime_usage(
    *,
    search: str = '',
    source_id: int | None = None,
    cluster_id: str = '',
    namespace: str = '',
    match_type: str = '',
    exposure: str = '',
    artifact_id: int | None = None,
    page: int = 1,
    per_page: int = 5,
) -> dict[str, Any]:
    sources = _providers()
    source_by_id = {int(item.id): item for item in sources}
    clusters = Cluster.query.order_by(Cluster.name.asc()).all()
    cluster_by_id = {str(item.id): item for item in clusters}
    prerequisites = correlation_prerequisites()

    search_value = str(search or '').strip().lower()
    cluster_value = str(cluster_id or '').strip()
    namespace_value = str(namespace or '').strip()
    match_value = str(match_type or '').strip().lower()
    exposure_value = str(exposure or '').strip().lower()

    security_by_artifact, critical_ids, high_ids, scanned_ids = _runtime_security_index()
    exposed_ids = critical_ids | high_ids
    safe_scanned_ids = scanned_ids - exposed_ids

    query = (
        RegistryWorkloadBinding.query.join(
            RegistryArtifact,
            RegistryWorkloadBinding.artifact_id == RegistryArtifact.id,
        )
        .join(
            RegistryRepository,
            RegistryArtifact.repository_id == RegistryRepository.id,
        )
        .join(
            RegistryProject,
            RegistryRepository.project_id == RegistryProject.id,
        )
        .outerjoin(Cluster, RegistryWorkloadBinding.cluster_id == Cluster.id)
        .options(
            joinedload(RegistryWorkloadBinding.artifact)
            .joinedload(RegistryArtifact.repository)
            .joinedload(RegistryRepository.project)
        )
    )

    if source_id is not None:
        query = query.filter(RegistryProject.integration_instance_id == int(source_id))
    if cluster_value:
        query = query.filter(RegistryWorkloadBinding.cluster_id == cluster_value)
    if namespace_value:
        query = query.filter(RegistryWorkloadBinding.namespace == namespace_value)
    if match_value in {'digest', 'tag'}:
        query = query.filter(RegistryWorkloadBinding.match_type == match_value)
    if artifact_id is not None:
        query = query.filter(RegistryWorkloadBinding.artifact_id == int(artifact_id))

    if exposure_value == 'critical':
        query = (
            query.filter(RegistryWorkloadBinding.artifact_id.in_(critical_ids))
            if critical_ids
            else query.filter(RegistryWorkloadBinding.id == -1)
        )
    elif exposure_value == 'high':
        query = (
            query.filter(RegistryWorkloadBinding.artifact_id.in_(high_ids))
            if high_ids
            else query.filter(RegistryWorkloadBinding.id == -1)
        )
    elif exposure_value == 'no_high_risk':
        query = (
            query.filter(RegistryWorkloadBinding.artifact_id.in_(safe_scanned_ids))
            if safe_scanned_ids
            else query.filter(RegistryWorkloadBinding.id == -1)
        )
    elif exposure_value == 'not_scanned' and scanned_ids:
        query = query.filter(~RegistryWorkloadBinding.artifact_id.in_(scanned_ids))

    if search_value:
        pattern = f'%{search_value}%'
        matching_source_ids = [
            int(source.id)
            for source in sources
            if search_value
            in f'{source.name} {source.provider_key} {source.environment or ""}'.lower()
        ]
        search_clauses = [
            func.lower(RegistryArtifact.digest).like(pattern),
            func.lower(RegistryRepository.name).like(pattern),
            func.lower(RegistryProject.name).like(pattern),
            func.lower(RegistryWorkloadBinding.namespace).like(pattern),
            func.lower(func.coalesce(RegistryWorkloadBinding.workload_name, '')).like(pattern),
            func.lower(RegistryWorkloadBinding.pod_name).like(pattern),
            func.lower(func.coalesce(RegistryWorkloadBinding.container_name, '')).like(pattern),
            func.lower(RegistryWorkloadBinding.image_reference).like(pattern),
            func.lower(func.coalesce(Cluster.name, '')).like(pattern),
        ]
        if matching_source_ids:
            search_clauses.append(
                RegistryProject.integration_instance_id.in_(matching_source_ids)
            )
        query = query.filter(or_(*search_clauses))

    binding_total = query.order_by(None).count()
    digest_matches = query.filter(
        RegistryWorkloadBinding.match_type == 'digest'
    ).order_by(None).count()
    tag_matches = query.filter(
        RegistryWorkloadBinding.match_type == 'tag'
    ).order_by(None).count()
    security_exposed = (
        query.filter(
            RegistryWorkloadBinding.artifact_id.in_(exposed_ids)
        ).order_by(None).count()
        if exposed_ids
        else 0
    )
    critical_exposures = (
        query.filter(
            RegistryWorkloadBinding.artifact_id.in_(critical_ids)
        ).order_by(None).count()
        if critical_ids
        else 0
    )
    artifact_count = query.with_entities(
        RegistryWorkloadBinding.artifact_id
    ).distinct().count()

    page_items, pagination = paginate_query(
        query.order_by(
            RegistryWorkloadBinding.namespace.asc(),
            RegistryWorkloadBinding.workload_name.asc(),
            RegistryWorkloadBinding.pod_name.asc(),
            RegistryWorkloadBinding.id.asc(),
        ),
        page=page,
        per_page=per_page,
    )

    rows: list[dict[str, Any]] = []
    for binding in page_items:
        artifact = binding.artifact
        repository = artifact.repository
        project = repository.project
        source = source_by_id.get(int(project.integration_instance_id))
        cluster = cluster_by_id.get(str(binding.cluster_id))
        security = security_by_artifact.get(
            int(artifact.id),
            _runtime_security_state(artifact.scan_status, artifact.vulnerability_summary),
        )
        match = _runtime_match_state(binding.match_type, binding.confidence)
        rows.append(
            {
                'id': int(binding.id),
                'artifact_id': int(artifact.id),
                'project': project.name,
                'repository': repository.name,
                'digest': artifact.digest,
                'digest_short': (
                    artifact.digest
                    if len(artifact.digest) <= 28
                    else f'{artifact.digest[:18]}…{artifact.digest[-8:]}'
                ),
                'source_id': int(project.integration_instance_id),
                'source_name': source.name if source is not None else 'Unknown Registry Source',
                'provider_label': (
                    source.provider_key.replace('_', ' ').title()
                    if source is not None
                    else 'Registry'
                ),
                'cluster_id': str(binding.cluster_id),
                'cluster_name': cluster.name if cluster is not None else str(binding.cluster_id),
                'cluster_environment': cluster.environment if cluster is not None else None,
                'namespace': binding.namespace,
                'workload_type': binding.workload_type or 'Workload',
                'workload_name': binding.workload_name or 'Not Resolved',
                'pod_name': binding.pod_name,
                'container_name': binding.container_name or 'Container',
                'image_reference': binding.image_reference,
                'match': match,
                'match_type': binding.match_type,
                'confidence': binding.confidence,
                'security': security,
                'observed_at': binding.observed_at,
            }
        )

    latest_job = (
        JobExecution.query.filter(
            JobExecution.job_type == 'artifact_registry_runtime_correlation'
        )
        .order_by(JobExecution.created_at.desc(), JobExecution.id.desc())
        .first()
    )
    latest_success = (
        JobExecution.query.filter(
            JobExecution.job_type == 'artifact_registry_runtime_correlation',
            JobExecution.status.in_(('succeeded', 'partially_succeeded')),
        )
        .order_by(JobExecution.completed_at.desc(), JobExecution.created_at.desc())
        .first()
    )
    latest_binding_at = RegistryWorkloadBinding.query.with_entities(
        func.max(RegistryWorkloadBinding.observed_at)
    ).scalar()
    latest_correlated_at = (
        latest_success.completed_at
        if latest_success is not None and latest_success.completed_at is not None
        else latest_binding_at
    )
    latest_correlated_at = _aware_datetime(latest_correlated_at)
    setup = _runtime_prerequisite_guidance(
        prerequisites,
        has_committed_snapshot=latest_correlated_at is not None,
    )
    refresh_failed = bool(
        latest_job is not None
        and latest_job.status == 'failed'
        and (
            latest_success is None
            or latest_job.created_at > latest_success.created_at
        )
    )
    refreshing = bool(latest_job is not None and latest_job.is_active)
    stale = bool(
        latest_correlated_at is not None
        and latest_correlated_at < datetime.now(UTC) - timedelta(hours=FRESHNESS_HOURS)
    )

    if refreshing:
        snapshot_status, snapshot_tone = 'Refreshing', 'info'
        snapshot_description = 'Runtime correlation is rebuilding from committed Registry and Kubernetes evidence.'
    elif setup['refresh_blocked']:
        snapshot_status, snapshot_tone = 'Refresh Unavailable', 'warning'
        snapshot_description = setup['refresh_description']
    elif setup['is_blocked']:
        snapshot_status, snapshot_tone = 'Prerequisites Required', 'warning'
        snapshot_description = setup['description']
    elif latest_correlated_at is None:
        snapshot_status, snapshot_tone = 'Not Materialized', 'unknown'
        snapshot_description = 'No committed runtime correlation snapshot is available yet.'
    elif refresh_failed:
        snapshot_status, snapshot_tone = 'Refresh Failed', 'warning'
        snapshot_description = 'The latest rebuild failed; the previous committed correlation remains readable.'
    elif stale:
        snapshot_status, snapshot_tone = 'Stale', 'warning'
        snapshot_description = 'Committed runtime correlation is older than the current freshness window.'
    else:
        snapshot_status, snapshot_tone = 'Ready', 'normal'
        snapshot_description = 'Committed cross-domain runtime correlation is available for the active scope.'

    selected_source = source_by_id.get(int(source_id)) if source_id is not None else None
    source_scope_label = (
        selected_source.name
        if selected_source is not None
        else ('Selected Registry Source' if source_id is not None else 'All Registry Sources')
    )
    selected_cluster = cluster_by_id.get(cluster_value) if cluster_value else None
    cluster_scope_label = (
        selected_cluster.name
        if selected_cluster is not None
        else ('Selected Kubernetes Cluster' if cluster_value else 'All Kubernetes Clusters')
    )
    scope_label = f'{source_scope_label} × {cluster_scope_label}'
    if namespace_value:
        scope_label = f'{scope_label} · {namespace_value}'

    artifact_filter_label = ''
    if artifact_id is not None:
        artifact_filter = (
            RegistryArtifact.query.options(
                joinedload(RegistryArtifact.repository).joinedload(RegistryRepository.project)
            )
            .filter(RegistryArtifact.id == int(artifact_id))
            .first()
        )
        if artifact_filter is not None:
            artifact_filter_label = (
                f'{artifact_filter.repository.project.name}/'
                f'{artifact_filter.repository.name} · '
                f'{artifact_filter.digest[:18]}…'
            )
            scope_label = f'{scope_label} · Artifact Scoped'

    if critical_exposures:
        posture = {'label': 'Critical Runtime Exposure', 'tone': 'critical'}
    elif security_exposed:
        posture = {'label': 'High-Risk Runtime Exposure', 'tone': 'warning'}
    elif binding_total and tag_matches:
        posture = {'label': 'Tag-Matched Runtime Evidence', 'tone': 'info'}
    elif binding_total:
        posture = {'label': 'Digest-Correlated', 'tone': 'normal'}
    else:
        posture = {'label': 'No Runtime Correlation', 'tone': 'unknown'}

    if tag_matches:
        exceptions_label = (
            f'{tag_matches} Tag Match'
            if tag_matches == 1
            else f'{tag_matches} Tag Matches'
        )
        exceptions_supporting = 'Mutable-reference evidence; lower confidence.'
        exceptions_tone = 'warning'
    elif binding_total:
        exceptions_label = 'Digest-only'
        exceptions_supporting = 'No tag-only correlation in this scope.'
        exceptions_tone = 'normal'
    else:
        exceptions_label = 'No Correlation'
        exceptions_supporting = 'No committed runtime binding in this scope.'
        exceptions_tone = 'unknown'

    has_filters = bool(
        search_value
        or source_id is not None
        or cluster_value
        or namespace_value
        or match_value
        or exposure_value
        or artifact_id is not None
    )
    if artifact_id is not None and not binding_total:
        empty_title = 'Artifact Not Observed at Runtime'
        empty_description = (
            'No committed Kubernetes workload binding currently resolves to this artifact.'
        )
    elif has_filters and not binding_total:
        empty_title = 'No Runtime Bindings Match'
        empty_description = 'No committed runtime correlation matches the active filters.'
    elif latest_correlated_at is None:
        empty_title = 'Runtime Correlation Not Materialized'
        empty_description = (
            'Run the canonical Runtime Correlation job after Registry and Kubernetes inventory are committed.'
        )
    else:
        empty_title = 'No Runtime Usage Observed'
        empty_description = (
            'The latest committed correlation contains no Registry-to-Kubernetes bindings.'
        )

    namespace_options = [
        value
        for (value,) in (
            RegistryWorkloadBinding.query.with_entities(
                RegistryWorkloadBinding.namespace
            )
            .distinct()
            .order_by(RegistryWorkloadBinding.namespace.asc())
            .all()
        )
        if value
    ]

    return {
        'setup': {
            **setup,
            'provider_count': len(sources),
        },
        'prerequisites': prerequisites,
        'total': binding_total,
        'digest_matches': digest_matches,
        'tag_matches': tag_matches,
        'security_exposed': security_exposed,
        'critical_exposures': critical_exposures,
        'artifact_count': artifact_count,
        'posture': posture,
        'rows': rows,
        'pagination': pagination,
        'has_filters': has_filters,
        'filters': {
            'search': search,
            'source_id': source_id,
            'cluster_id': cluster_value,
            'namespace': namespace_value,
            'match_type': match_value,
            'exposure': exposure_value,
            'artifact_id': artifact_id,
        },
        'source_options': sources,
        'cluster_options': clusters,
        'namespace_options': namespace_options,
        'match_options': [
            {'value': 'digest', 'label': 'Digest Match'},
            {'value': 'tag', 'label': 'Tag Match'},
        ],
        'exposure_options': [
            {'value': 'critical', 'label': 'Critical'},
            {'value': 'high', 'label': 'High'},
            {'value': 'no_high_risk', 'label': 'No Critical/High'},
            {'value': 'not_scanned', 'label': 'Not Scanned'},
        ],
        'scope': {
            'label': scope_label,
            'source_label': source_scope_label,
            'cluster_label': cluster_scope_label,
        },
        'artifact_filter_label': artifact_filter_label,
        'snapshot': {
            'source_label': 'Committed Artifact Registry × Kubernetes',
            'status': snapshot_status,
            'tone': snapshot_tone,
            'description': snapshot_description,
            'latest_collected_at': latest_correlated_at,
            'scope_label': scope_label,
            'coverage_label': f'{artifact_count} artifacts · {binding_total} bindings',
            'coverage_supporting': 'Committed runtime usage in the active scope.',
            'coverage_tone': 'normal' if binding_total else 'warning',
            'exceptions_label': exceptions_label,
            'exceptions_supporting': exceptions_supporting,
            'exceptions_tone': exceptions_tone,
        },
        'empty_title': empty_title,
        'empty_description': empty_description,
    }


def build_runtime_binding_detail(binding_id: int) -> dict[str, Any] | None:
    binding = (
        RegistryWorkloadBinding.query.options(
            joinedload(RegistryWorkloadBinding.artifact)
            .joinedload(RegistryArtifact.repository)
            .joinedload(RegistryRepository.project),
            joinedload(RegistryWorkloadBinding.artifact).joinedload(RegistryArtifact.tags),
        )
        .filter(RegistryWorkloadBinding.id == int(binding_id))
        .first()
    )
    if binding is None:
        return None

    artifact = binding.artifact
    repository = artifact.repository
    project = repository.project
    source = _inventory_detail_provider_context(project.integration_instance_id)
    cluster = Cluster.query.filter(Cluster.id == str(binding.cluster_id)).first()
    match = _runtime_match_state(binding.match_type, binding.confidence)
    security = _runtime_security_state(artifact.scan_status, artifact.vulnerability_summary)
    details = dict(binding.details) if isinstance(binding.details, dict) else {}

    return {
        'id': int(binding.id),
        'artifact_id': int(artifact.id),
        'project': project.name,
        'repository': repository.name,
        'digest': artifact.digest,
        'digest_short': (
            artifact.digest
            if len(artifact.digest) <= 40
            else f'{artifact.digest[:24]}…{artifact.digest[-12:]}'
        ),
        'tags': [tag.name for tag in sorted(artifact.tags, key=lambda item: item.name.lower())],
        'image_reference': binding.image_reference,
        'match': match,
        'match_type': binding.match_type,
        'confidence': binding.confidence,
        'cluster_id': str(binding.cluster_id),
        'cluster_name': cluster.name if cluster is not None else str(binding.cluster_id),
        'cluster_environment': cluster.environment if cluster is not None else 'Not Set',
        'namespace': binding.namespace,
        'workload_type': binding.workload_type or 'Workload',
        'workload_name': binding.workload_name or 'Not Resolved',
        'pod_name': binding.pod_name,
        'container_name': binding.container_name or 'Container',
        'source_kind': str(details.get('source_kind') or 'container').replace('_', ' ').title(),
        'registry_host': details.get('registry_host') or 'Not Collected',
        'registry_observed_at': _runtime_parse_observed_at(
            details.get('registry_observed_at')
        ) or artifact.observed_at,
        'kubernetes_observed_at': _runtime_parse_observed_at(
            details.get('pod_collected_at')
        ),
        'correlated_at': binding.observed_at,
        'security': security,
        'scan_status': (
            str(artifact.scan_status).replace('_', ' ').title()
            if artifact.scan_status
            else 'Not Scanned'
        ),
        **source,
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


def build_governance(
    *,
    active_tab: str = 'policies',
    page: int = 1,
    per_page: int = 5,
) -> dict[str, Any]:
    from app.artifact_registry.governance_job_adapter import build_registry_governance_sync_state

    overview = build_overview()
    identities = _providers()
    identity_by_id = {int(item.id): item for item in identities}
    governance_states = {
        int(item.integration_instance_id): item
        for item in RegistryGovernanceState.query.all()
    }

    project_rows: list[dict[str, Any]] = []
    governance_items = RegistryProjectGovernance.query.options(
        joinedload(RegistryProjectGovernance.project),
    ).order_by(
        RegistryProjectGovernance.observed_at.desc(),
        RegistryProjectGovernance.id.desc(),
    ).all()
    for item in governance_items:
        identity = identity_by_id.get(int(item.project.integration_instance_id))
        retention = _policy_state_view(item.retention_status)
        immutability = _policy_state_view(item.immutability_status)
        project_rows.append(
            {
                'project': item.project.name,
                'provider_label': str(
                    (identity.metadata_json or {}).get('provider_label')
                    or identity.provider_key.title()
                )
                if identity is not None
                else 'Registry',
                'retention_status': str(item.retention_status or 'not_collected'),
                'retention_label': retention['label'],
                'retention_tone': retention['tone'],
                'immutability_status': str(item.immutability_status or 'not_collected'),
                'immutability_label': immutability['label'],
                'immutability_tone': immutability['tone'],
                'observed_at': item.observed_at,
            }
        )

    replication_rows: list[dict[str, Any]] = []
    for item in RegistryReplicationPolicy.query.order_by(
        RegistryReplicationPolicy.name.asc(),
        RegistryReplicationPolicy.id.asc(),
    ).all():
        identity = identity_by_id.get(int(item.integration_instance_id))
        replication_rows.append(
            {
                'name': item.name,
                'provider_label': str(
                    (identity.metadata_json or {}).get('provider_label')
                    or identity.provider_key.title()
                )
                if identity is not None
                else 'Registry',
                'enabled': item.enabled,
                'trigger_type': item.trigger_type,
                'source_registry': item.source_registry,
                'destination_registry': item.destination_registry,
                'destination_namespace': item.destination_namespace,
                'observed_at': item.observed_at,
            }
        )

    provider_count = len(identities)
    project_total = (
        RegistryProject.query.filter(
            RegistryProject.integration_instance_id.in_(identity_by_id)
        ).count()
        if identity_by_id
        else 0
    )
    governance_ready_count = sum(
        1
        for identity in identities
        if (governance_states.get(int(identity.id)) is not None)
        and governance_states[int(identity.id)].status == 'ready'
        and governance_states[int(identity.id)].last_committed_at is not None
    )
    state_views = [
        _state_view(governance_states.get(int(identity.id)))
        for identity in identities
    ]
    exception_count = sum(
        1
        for view in state_views
        if view['status'] != 'ready' or view.get('is_stale') or view.get('refresh_failed')
    )
    latest_committed_at = max(
        (
            _aware_datetime(state.last_committed_at)
            for state in governance_states.values()
            if state.last_committed_at is not None
        ),
        default=None,
    )

    retention_configured = sum(
        1 for row in project_rows if row['retention_status'] == 'configured'
    )
    retention_unavailable = sum(
        1 for row in project_rows if row['retention_status'] == 'unavailable'
    )
    retention_not_configured = sum(
        1 for row in project_rows if row['retention_status'] == 'not_configured'
    )
    retention_observed = retention_configured + retention_not_configured
    immutability_configured = sum(
        1 for row in project_rows if row['immutability_status'] == 'configured'
    )
    immutability_unavailable = sum(
        1 for row in project_rows if row['immutability_status'] == 'unavailable'
    )
    immutability_not_configured = sum(
        1 for row in project_rows if row['immutability_status'] == 'not_configured'
    )
    immutability_observed = immutability_configured + immutability_not_configured

    capability_counts: dict[str, dict[str, int]] = {}
    for capability in ('retention', 'immutability', 'replication'):
        counts = {'observed': 0, 'unavailable': 0, 'unsupported': 0, 'unknown': 0}
        for state in governance_states.values():
            raw = (
                (state.capability_states or {}).get(capability)
                if isinstance(state.capability_states, dict)
                else None
            )
            status = str(raw.get('status') or 'unknown') if isinstance(raw, dict) else 'unknown'
            counts[status if status in counts else 'unknown'] += 1
        capability_counts[capability] = counts

    normalized_tab = active_tab if active_tab in {'policies', 'replication'} else 'policies'
    active_rows = project_rows if normalized_tab == 'policies' else replication_rows
    page_rows, pagination = paginate_sequence(active_rows, page=page, per_page=per_page)

    if not identities:
        posture = {'label': 'Setup Required', 'tone': 'unknown'}
    elif governance_ready_count == 0:
        posture = {'label': 'Governance Sync Required', 'tone': 'warning'}
    elif exception_count:
        posture = {'label': 'Evidence Attention', 'tone': 'warning'}
    else:
        posture = {'label': 'Committed Evidence Ready', 'tone': 'normal'}

    snapshot_status = (
        'Current'
        if provider_count and governance_ready_count == provider_count and exception_count == 0
        else ('Not Collected' if governance_ready_count == 0 else 'Attention')
    )
    snapshot_tone = (
        'normal'
        if snapshot_status == 'Current'
        else ('unknown' if snapshot_status == 'Not Collected' else 'warning')
    )
    snapshot_context = {
        'source_label': 'Committed Registry Governance Evidence',
        'status': snapshot_status,
        'tone': snapshot_tone,
        'description': 'Retention, immutability, and replication evidence committed from Registry providers.',
        'latest_collected_at': latest_committed_at,
        'scope_label': f'{provider_count} Registry Provider' + ('' if provider_count == 1 else 's'),
        'coverage_label': f'{governance_ready_count}/{provider_count} Providers Committed',
        'coverage_supporting': 'Provider-neutral Governance snapshots.',
        'coverage_tone': (
            'normal'
            if provider_count and governance_ready_count == provider_count
            else 'warning'
        ),
        'exception_count': exception_count,
        'exceptions_label': (
            'No Exceptions'
            if exception_count == 0
            else f'{exception_count} Evidence Exception' + ('' if exception_count == 1 else 's')
        ),
        'exceptions_supporting': (
            'Missing, stale, or failed Governance collection.'
            if exception_count
            else 'No freshness or collection exceptions.'
        ),
        'exceptions_tone': 'normal' if exception_count == 0 else 'warning',
    }

    posture_cards = [
        {
            'label': 'Policy Coverage',
            'value': f'{len(project_rows)}/{project_total} Projects',
            'status_label': (
                'Committed'
                if project_total and len(project_rows) == project_total
                else ('Partial' if project_rows else 'Not Collected')
            ),
            'tone': (
                'normal'
                if project_total and len(project_rows) == project_total
                else ('warning' if project_rows else 'unknown')
            ),
            'detail': 'Committed project-scoped retention and immutability evidence.',
        },
        {
            'label': 'Retention Coverage',
            'value': f'{retention_observed}/{project_total} Projects',
            'status_label': 'Observed' if retention_observed else 'Not Collected',
            'tone': 'normal' if project_total and retention_observed == project_total else 'warning',
            'detail': (
                f'{retention_configured} configured · {retention_not_configured} not configured · '
                f'{retention_unavailable} unavailable.'
            ),
        },
        {
            'label': 'Immutability Coverage',
            'value': f'{immutability_observed}/{project_total} Projects',
            'status_label': 'Observed' if immutability_observed else 'Not Collected',
            'tone': 'normal' if project_total and immutability_observed == project_total else 'warning',
            'detail': (
                f'{immutability_configured} configured · {immutability_not_configured} not configured · '
                f'{immutability_unavailable} unavailable.'
            ),
        },
        {
            'label': 'Replication Coverage',
            'value': f"{capability_counts['replication']['observed']}/{provider_count} Providers",
            'status_label': 'Observed' if governance_ready_count else 'Not Collected',
            'tone': (
                'normal'
                if provider_count
                and capability_counts['replication']['observed'] == provider_count
                else ('warning' if governance_ready_count else 'unknown')
            ),
            'detail': (
                f"{len(replication_rows)} policies · "
                f"{capability_counts['replication']['unavailable']} unavailable · "
                f"{capability_counts['replication']['unsupported']} unsupported."
            ),
        },
    ]

    return {
        'setup': overview['setup'],
        'provider_count': provider_count,
        'project_count': len(project_rows),
        'replication_count': len(replication_rows),
        'governance_ready_count': governance_ready_count,
        'posture': posture,
        'snapshot_context': snapshot_context,
        'posture_cards': posture_cards,
        'active_tab': normalized_tab,
        'rows': page_rows,
        'pagination': pagination,
        'filter_query': {'tab': normalized_tab},
        'sync_state': build_registry_governance_sync_state(),
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
