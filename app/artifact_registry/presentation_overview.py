from __future__ import annotations

from typing import Any

from sqlalchemy import case, func

from app.artifact_registry.observability import RegistryMetricsReadiness, registry_metrics_readiness
from app.artifact_registry.presentation_common import (
    _analytics_snapshot_view,
    _fmt_bytes,
    _freshness_value,
    _latest_registry_analytics,
    _overview_kpi_values,
    _overview_scope_context,
    _registry_alerts,
    _registry_capacity_views,
    _registry_recommended_actions,
    _registry_reporting,
    _state_view,
)
from app.artifact_registry.security.contracts import SUCCESSFUL_REGISTRY_SCAN_STATUSES
from app.common.pagination import paginate_sequence
from app.dashboards.common.operational import normalize_operational_tab
from app.models.integration import IntegrationInstance
from app.models.registry import (
    RegistryArtifact,
    RegistryCollectionState,
    RegistryProject,
    RegistryRepository,
    RegistryScanSnapshot,
)


def _provider_health_status(
    *,
    readiness: str,
    state: RegistryCollectionState | None,
    snapshot: dict[str, Any],
    security: dict[str, int],
    inventory_ready: bool,
) -> tuple[str, str, str]:
    if readiness == 'blocked':
        return 'Critical', 'critical', 'Provider readiness is blocked.'
    if state is not None and state.status == 'failed' and not inventory_ready:
        return (
            'Critical',
            'critical',
            'Inventory synchronization failed before a committed snapshot was established.',
        )
    if security['critical'] > 0:
        return 'Critical', 'critical', f'{security["critical"]} critical security finding(s).'
    if not inventory_ready:
        return 'Warning', 'warning', 'Committed inventory has not been collected.'
    if snapshot['is_stale']:
        return 'Warning', 'warning', 'Committed inventory snapshot is stale.'
    if state is not None and state.last_error:
        return (
            'Warning',
            'warning',
            'Latest inventory refresh failed; the previous committed snapshot is retained.',
        )
    if readiness == 'degraded':
        return 'Warning', 'warning', 'Provider is usable with compatibility attention.'
    return 'Healthy', 'normal', 'Provider and committed inventory are operational.'


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
    dict[int, RegistryMetricsReadiness],
    dict[int, dict[str, int]],
]:
    state_by_provider = {int(state.integration_instance_id): state for state in states}

    project_counts_query = RegistryProject.query.with_entities(
        RegistryProject.integration_instance_id,
        func.count(RegistryProject.id),
    )
    repository_counts_query = RegistryRepository.query.join(RegistryProject).with_entities(
        RegistryProject.integration_instance_id,
        func.count(RegistryRepository.id),
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
                            func.lower(RegistryArtifact.scan_status).in_(SUCCESSFUL_REGISTRY_SCAN_STATUSES),
                            1,
                        ),
                        else_=0,
                    )
                ),
                0,
            ),
            func.coalesce(
                func.sum(RegistryArtifact.vulnerability_summary['critical'].as_integer()),
                0,
            ),
            func.coalesce(
                func.sum(RegistryArtifact.vulnerability_summary['high'].as_integer()),
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
        for provider_id, count in project_counts_query.group_by(RegistryProject.integration_instance_id).all()
    }
    repository_counts = {
        int(provider_id): int(count)
        for provider_id, count in repository_counts_query.group_by(RegistryProject.integration_instance_id).all()
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

    metrics_by_provider = {int(provider.id): registry_metrics_readiness(provider) for provider in scoped_providers}
    provider_rows: list[dict[str, Any]] = []
    for provider in scoped_providers:
        key = int(provider.id)
        state = state_by_provider.get(key)
        snapshot = _state_view(state)
        metrics = metrics_by_provider[key]
        security = security_counts.get(
            key,
            {'artifacts': 0, 'scanned': 0, 'critical': 0, 'high': 0},
        )
        readiness = str(provider.readiness_status or 'validation_required')
        inventory_ready = bool(state is not None and state.last_committed_at is not None)
        provider_artifact_count = security['artifacts']
        security_ready = bool(security['scanned'])
        security_not_applicable = inventory_ready and provider_artifact_count == 0

        overall_status, overall_tone, status_reason = _provider_health_status(
            readiness=readiness,
            state=state,
            snapshot=snapshot,
            security=security,
            inventory_ready=inventory_ready,
        )

        provider_rows.append(
            {
                'id': key,
                'name': provider.name,
                'provider_label': str(
                    (provider.metadata_json or {}).get('provider_label') or provider.provider_key.title()
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


def _overview_inventory_evidence(
    selected_provider: IntegrationInstance | None,
) -> tuple[int, int, Any]:
    artifact_summary_query = (
        RegistryArtifact.query.join(RegistryRepository)
        .join(RegistryProject)
        .with_entities(func.coalesce(func.sum(RegistryArtifact.size_bytes), 0))
    )
    public_projects_query = RegistryProject.query.filter(RegistryProject.public.is_(True))
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
        .filter(func.lower(RegistryScanSnapshot.status).in_(SUCCESSFUL_REGISTRY_SCAN_STATUSES))
        .with_entities(
            RegistryProject.integration_instance_id,
            func.max(RegistryScanSnapshot.observed_at),
        )
    )
    if selected_provider is not None:
        artifact_summary_query = artifact_summary_query.filter(
            RegistryProject.integration_instance_id == selected_provider.id
        )
        public_projects_query = public_projects_query.filter(
            RegistryProject.integration_instance_id == selected_provider.id
        )
        security_freshness_query = security_freshness_query.filter(
            RegistryProject.integration_instance_id == selected_provider.id
        )
    observed_by_provider = {
        int(provider_id): observed_at
        for provider_id, observed_at in security_freshness_query.group_by(RegistryProject.integration_instance_id).all()
    }
    latest_security_at = max(
        (value for value in observed_by_provider.values() if value is not None),
        default=None,
    )
    return int(artifact_summary_query.one()[0] or 0), public_projects_query.count(), latest_security_at


def _overview_inventory_items(
    counts: dict[str, int],
    *,
    artifact_total: int,
    total_size_bytes: int,
    public_project_count: int,
) -> list[dict[str, Any]]:
    return [
        {'label': 'Projects', 'value': counts['projects'], 'icon': 'folder-kanban', 'role': 'Scope'},
        {'label': 'Repositories', 'value': counts['repositories'], 'icon': 'package-open', 'role': 'Catalog'},
        {'label': 'Artifacts', 'value': artifact_total, 'icon': 'fingerprint', 'role': 'Immutable'},
        {'label': 'Tags', 'value': counts['tags'], 'icon': 'tags', 'role': 'Aliases'},
        {'label': 'Artifact Footprint', 'value': _fmt_bytes(total_size_bytes), 'icon': 'database', 'role': 'Storage'},
        {'label': 'Public Projects', 'value': public_project_count, 'icon': 'globe-2', 'role': 'Exposure'},
    ]


def _security_freshness_status(
    *,
    artifact_total: int,
    scanned_count: int,
    committed_at: Any,
    latest_security_at: Any,
) -> tuple[str, str, str]:
    if artifact_total == 0 and committed_at is not None:
        return 'No Artifacts', 'info', 'No committed artifacts to scan'
    if scanned_count:
        return (
            'Available',
            'normal',
            _freshness_value(latest_security_at, missing='Committed scan evidence available'),
        )
    return (
        'Required',
        'warning' if artifact_total else 'unknown',
        'No committed security snapshot',
    )


def _selected_provider_freshness(
    *,
    selected_provider: IntegrationInstance,
    state_by_provider: dict[int, RegistryCollectionState],
    metrics_by_provider: dict[int, RegistryMetricsReadiness],
    analytics_by_provider: dict[int, Any],
    artifact_total: int,
    scanned_count: int,
    latest_security_at: Any,
) -> list[dict[str, Any]]:
    selected_key = int(selected_provider.id)
    selected_collection_state = state_by_provider.get(selected_key)
    selected_state = _state_view(selected_collection_state)
    selected_metrics = metrics_by_provider[selected_key]
    selected_analytics = _analytics_snapshot_view(analytics_by_provider.get(selected_key))
    security_status, security_tone, security_value = _security_freshness_status(
        artifact_total=artifact_total,
        scanned_count=scanned_count,
        committed_at=selected_state['committed_at'],
        latest_security_at=latest_security_at,
    )
    inventory_description = 'Committed projects, repositories, artifacts, tags, and provider provenance.'
    if selected_collection_state is not None and selected_collection_state.last_error:
        inventory_description += ' Latest refresh failed; KAORI retained the previous committed snapshot.'
    return [
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
            'value': str(selected_metrics.get('selected_source') or 'No validated Metrics Source'),
            'description': 'Validated Registry Metrics Source binding; independent from provider readiness.',
            'icon': 'activity',
        },
        {
            'label': 'Security Snapshot',
            'status': security_status,
            'tone': security_tone,
            'value': security_value,
            'description': 'Committed vulnerability scan evidence attached to immutable artifact digests.',
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
            'description': 'Materialized Registry growth, forecast, runtime, and recommendation evidence.',
            'icon': 'chart-no-axes-combined',
        },
    ]


def _fleet_inventory_status(
    *,
    committed_count: int,
    provider_count: int,
    stale_count: int,
    failed_refresh_count: int,
) -> tuple[str, str]:
    if committed_count == provider_count and provider_count:
        return (
            'Stale' if stale_count else ('Attention' if failed_refresh_count else 'Ready'),
            'warning' if stale_count or failed_refresh_count else 'normal',
        )
    if committed_count:
        return 'Partial', 'warning'
    return 'Required', 'unknown'


def _fleet_freshness(
    *,
    context: dict[str, Any],
    provider_count: int,
    stats: dict[str, Any],
) -> list[dict[str, Any]]:
    inventory_status, inventory_tone = _fleet_inventory_status(
        committed_count=stats['committed_count'],
        provider_count=provider_count,
        stale_count=context['stale_snapshot_count'],
        failed_refresh_count=context['failed_refresh_count'],
    )
    metrics_ready_count = stats['metrics_ready_count']
    analytics_ready_count = stats['analytics_ready_count']
    artifact_total = stats['artifact_total']
    scanned_count = stats['scanned_count']
    metrics_all_ready = bool(provider_count) and metrics_ready_count == provider_count
    analytics_all_ready = bool(provider_count) and analytics_ready_count == provider_count
    return [
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
            'status': 'Ready' if metrics_all_ready else ('Partial' if metrics_ready_count else 'Not Bound'),
            'tone': 'normal' if metrics_all_ready else ('warning' if metrics_ready_count else 'unknown'),
            'value': (
                'Validated Metrics Source available'
                if metrics_all_ready
                else (
                    'Validated Metrics Source partially available'
                    if metrics_ready_count
                    else 'No validated Metrics Source'
                )
            ),
            'description': 'Validated Registry Metrics Source availability across the active scope.',
            'icon': 'activity',
        },
        {
            'label': 'Security Snapshot',
            'status': 'No Artifacts' if artifact_total == 0 else ('Available' if scanned_count else 'Required'),
            'tone': 'info' if artifact_total == 0 else ('normal' if scanned_count else 'warning'),
            'value': (
                'No committed artifacts to scan'
                if artifact_total == 0
                else (
                    _freshness_value(
                        stats['latest_security_at'],
                        missing='Committed scan evidence available',
                    )
                    if scanned_count
                    else 'No committed security snapshot'
                )
            ),
            'description': 'Latest committed vulnerability scan evidence across the active Registry scope.',
            'icon': 'shield-check',
        },
        {
            'label': 'Analytics Snapshot',
            'status': 'Ready' if analytics_all_ready else ('Partial' if analytics_ready_count else 'Required'),
            'tone': 'normal' if analytics_all_ready else ('warning' if analytics_ready_count else 'unknown'),
            'value': _freshness_value(
                stats['latest_analytics_at'],
                missing='No analytics snapshot',
            ),
            'description': 'Latest ready Registry analytics materialization across the active scope.',
            'icon': 'chart-no-axes-combined',
        },
    ]


def _overview_operations_projection(
    *,
    context: dict[str, Any],
    scoped_providers: list[IntegrationInstance],
    states: list[RegistryCollectionState],
    selected_provider: IntegrationInstance | None,
    provider_health_page: int | str | None,
    provider_health_per_page: int,
) -> dict[str, Any]:
    provider_rows, pagination, metrics_by_provider, security_counts = _provider_health_projection(
        scoped_providers=scoped_providers,
        states=states,
        selected_provider=selected_provider,
        provider_health_page=provider_health_page,
        provider_health_per_page=provider_health_per_page,
    )
    counts = _overview_kpi_values(selected_provider)
    total_size_bytes, public_project_count, latest_security_at = _overview_inventory_evidence(selected_provider)
    state_by_provider = {int(state.integration_instance_id): state for state in states}
    committed_states = [state for state in states if state.last_committed_at is not None]
    artifact_total = counts['artifacts']
    scanned_count = sum(item['scanned'] for item in security_counts.values())
    analytics_by_provider = _latest_registry_analytics(scoped_providers)
    metrics_ready_count = sum(metrics.get('status') == 'ready' for metrics in metrics_by_provider.values())
    analytics_ready_count = sum(snapshot is not None for snapshot in analytics_by_provider.values())
    latest_analytics_at = max(
        (
            snapshot.generated_at
            for snapshot in analytics_by_provider.values()
            if snapshot is not None and snapshot.generated_at is not None
        ),
        default=None,
    )
    stats = {
        'artifact_total': artifact_total,
        'scanned_count': scanned_count,
        'committed_count': len(committed_states),
        'metrics_ready_count': metrics_ready_count,
        'analytics_ready_count': analytics_ready_count,
        'latest_security_at': latest_security_at,
        'latest_analytics_at': latest_analytics_at,
    }
    freshness = (
        _selected_provider_freshness(
            selected_provider=selected_provider,
            state_by_provider=state_by_provider,
            metrics_by_provider=metrics_by_provider,
            analytics_by_provider=analytics_by_provider,
            artifact_total=artifact_total,
            scanned_count=scanned_count,
            latest_security_at=latest_security_at,
        )
        if selected_provider is not None
        else _fleet_freshness(
            context=context,
            provider_count=len(scoped_providers),
            stats=stats,
        )
    )
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
        'scan_coverage': round((scanned_count / artifact_total) * 100) if artifact_total else 0,
        'metrics_ready_count': metrics_ready_count,
        'analytics_ready_count': analytics_ready_count,
        'provider_rows': provider_rows,
        'provider_health_pagination': pagination,
        'inventory_items': _overview_inventory_items(
            counts,
            artifact_total=artifact_total,
            total_size_bytes=total_size_bytes,
            public_project_count=public_project_count,
        ),
        'freshness': freshness,
    }


def _overview_capacity_projection(
    *,
    context: dict[str, Any],
    scoped_providers: list[IntegrationInstance],
    selected_provider: IntegrationInstance,
    states: list[RegistryCollectionState],
) -> dict[str, Any]:
    artifact_query = (
        RegistryArtifact.query.join(RegistryRepository)
        .join(RegistryProject)
        .filter(RegistryProject.integration_instance_id == selected_provider.id)
    )
    artifact_total, total_size_bytes = artifact_query.with_entities(
        func.count(RegistryArtifact.id),
        func.coalesce(func.sum(RegistryArtifact.size_bytes), 0),
    ).one()
    artifact_total = int(artifact_total or 0)
    total_size_bytes = int(total_size_bytes or 0)

    metrics_by_provider = {int(provider.id): registry_metrics_readiness(provider) for provider in scoped_providers}
    metrics_ready_count = sum(metrics.get('status') == 'ready' for metrics in metrics_by_provider.values())
    analytics_by_provider = _latest_registry_analytics(scoped_providers)
    capacity, forecast, top_consumers = _registry_capacity_views(
        scoped_providers=scoped_providers,
        analytics_by_provider=analytics_by_provider,
        total_size_bytes=total_size_bytes,
        artifact_total=artifact_total,
        committed_snapshot_count=sum(state.last_committed_at is not None for state in states),
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

    context, _providers_all, selected_provider, scoped_providers, states = _overview_scope_context(
        provider_id=provider_id,
        active_tab=normalize_operational_tab(section),
        provider_health_page=provider_health_page,
        provider_health_per_page=provider_health_per_page,
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
