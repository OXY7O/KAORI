from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.orm import joinedload

from app.artifact_registry.observability import registry_metrics_readiness
from app.common.pagination import paginate_sequence
from app.models.integration import IntegrationInstance
from app.models.registry import (
    RegistryAnalyticsSnapshot,
    RegistryArtifact,
    RegistryCollectionState,
    RegistryGovernanceState,
    RegistryProject,
    RegistryProjectGovernance,
    RegistryReplicationPolicy,
    RegistryRepository,
    RegistryWebhookEndpoint,
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


def build_overview(
    *,
    provider_id: int | None = None,
    active_tab: str = 'overview',
    provider_health_page: int | str | None = 1,
    provider_health_per_page: int = 5,
) -> dict[str, Any]:
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
    scoped_provider_ids = {int(provider.id) for provider in scoped_providers}

    states_query = RegistryCollectionState.query
    project_query = RegistryProject.query
    repository_query = RegistryRepository.query.join(RegistryProject)
    artifact_query = (
        RegistryArtifact.query.join(RegistryRepository)
        .join(RegistryProject)
        .options(joinedload(RegistryArtifact.tags))
    )
    runtime_query = (
        RegistryWorkloadBinding.query.join(RegistryArtifact)
        .join(RegistryRepository)
        .join(RegistryProject)
    )
    if selected_provider is not None:
        states_query = states_query.filter(
            RegistryCollectionState.integration_instance_id == selected_provider.id
        )
        project_query = project_query.filter(
            RegistryProject.integration_instance_id == selected_provider.id
        )
        repository_query = repository_query.filter(
            RegistryProject.integration_instance_id == selected_provider.id
        )
        artifact_query = artifact_query.filter(
            RegistryProject.integration_instance_id == selected_provider.id
        )
        runtime_query = runtime_query.filter(
            RegistryProject.integration_instance_id == selected_provider.id
        )

    states = states_query.all()
    projects = project_query.all()
    repositories = repository_query.all()
    artifacts = artifact_query.all()
    runtime_bindings = runtime_query.all()
    state_by_provider = {
        int(state.integration_instance_id): state
        for state in states
    }

    metrics_by_provider = {
        int(provider.id): registry_metrics_readiness(provider)
        for provider in scoped_providers
    }
    analytics_by_provider: dict[int, RegistryAnalyticsSnapshot | None] = {}
    for provider in scoped_providers:
        analytics_by_provider[int(provider.id)] = (
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

    ready_states = [
        state
        for state in states
        if state.status == 'ready' and state.last_committed_at is not None
    ]
    latest = max(
        (state.last_committed_at for state in ready_states if state.last_committed_at),
        default=None,
    )
    stale_count = sum(bool(_state_view(state)['is_stale']) for state in ready_states)
    pending_snapshot_count = max(len(scoped_providers) - len(ready_states), 0)

    tag_count = sum(len(item.tags) for item in artifacts)
    total_size_bytes = sum(int(item.size_bytes or 0) for item in artifacts)
    pull_count = sum(int(item.pull_count or 0) for item in repositories)
    public_project_count = sum(item.public is True for item in projects)
    scanned_count = sum(bool(item.scan_status) for item in artifacts)
    critical_findings = high_findings = 0
    for artifact in artifacts:
        summary = (
            artifact.vulnerability_summary
            if isinstance(artifact.vulnerability_summary, dict)
            else {}
        )
        critical_findings += int(summary.get('critical') or 0)
        high_findings += int(summary.get('high') or 0)

    digest_runtime_bindings = sum(
        binding.match_type == 'digest'
        for binding in runtime_bindings
    )
    metrics_ready_count = sum(
        metrics.get('status') == 'ready'
        for metrics in metrics_by_provider.values()
    )
    analytics_ready_count = sum(
        snapshot is not None
        for snapshot in analytics_by_provider.values()
    )

    if not providers:
        posture = {'label': 'Setup Required', 'tone': 'unknown'}
    elif not ready_states:
        posture = {'label': 'Inventory Pending', 'tone': 'warning'}
    elif stale_count:
        posture = {'label': 'Attention Required', 'tone': 'warning'}
    else:
        posture = {'label': 'Ready', 'tone': 'normal'}

    allowed_tabs = {'overview', 'capacity', 'signals', 'reporting'}
    normalized_tab = active_tab if active_tab in allowed_tabs else 'overview'
    scope_label = (
        selected_provider.name
        if selected_provider is not None
        else 'All Registry Providers'
    )
    artifact_total = len(artifacts)
    scan_coverage = round((scanned_count / artifact_total) * 100) if artifact_total else 0

    project_counts: dict[int, int] = {}
    repository_counts: dict[int, int] = {}
    artifact_counts: dict[int, int] = {}
    security_counts: dict[int, dict[str, int]] = {}
    for project in projects:
        key = int(project.integration_instance_id)
        project_counts[key] = project_counts.get(key, 0) + 1
    for repository in repositories:
        key = int(repository.project.integration_instance_id)
        repository_counts[key] = repository_counts.get(key, 0) + 1
    for artifact in artifacts:
        key = int(artifact.repository.project.integration_instance_id)
        artifact_counts[key] = artifact_counts.get(key, 0) + 1
        counts = security_counts.setdefault(key, {'scanned': 0, 'critical': 0, 'high': 0})
        counts['scanned'] += int(bool(artifact.scan_status))
        summary = (
            artifact.vulnerability_summary
            if isinstance(artifact.vulnerability_summary, dict)
            else {}
        )
        counts['critical'] += int(summary.get('critical') or 0)
        counts['high'] += int(summary.get('high') or 0)

    provider_rows: list[dict[str, Any]] = []
    for provider in scoped_providers:
        key = int(provider.id)
        state = state_by_provider.get(key)
        snapshot = _state_view(state)
        metrics = metrics_by_provider.get(key, {})
        security = security_counts.get(
            key,
            {'scanned': 0, 'critical': 0, 'high': 0},
        )
        readiness = str(provider.readiness_status or 'validation_required')
        inventory_ready = bool(
            state is not None
            and state.status == 'ready'
            and state.last_committed_at is not None
        )
        security_ready = bool(security['scanned'])

        if readiness == 'blocked':
            overall_status = 'Critical'
            overall_tone = 'critical'
            status_reason = 'Provider readiness is blocked.'
        elif state is not None and state.status == 'failed':
            overall_status = 'Critical'
            overall_tone = 'critical'
            status_reason = 'Last inventory synchronization failed.'
        elif security['critical'] > 0:
            overall_status = 'Critical'
            overall_tone = 'critical'
            status_reason = f"{security['critical']} critical security finding(s)."
        elif not inventory_ready:
            overall_status = 'Warning'
            overall_tone = 'warning'
            status_reason = 'Committed inventory has not been collected.'
        elif snapshot['is_stale']:
            overall_status = 'Warning'
            overall_tone = 'warning'
            status_reason = 'Committed inventory snapshot is stale.'
        elif readiness == 'degraded':
            overall_status = 'Warning'
            overall_tone = 'warning'
            status_reason = 'Provider is usable with compatibility attention.'
        else:
            overall_status = 'Healthy'
            overall_tone = 'normal'
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
                'artifact_count': artifact_counts.get(key, 0),
                'critical_findings': security['critical'],
                'high_findings': security['high'],
                'inventory_ready': inventory_ready,
                'metrics_ready': metrics.get('status') == 'ready',
                'security_ready': security_ready,
                'snapshot': snapshot,
            }
        )

    visible_provider_rows, provider_health_pagination = paginate_sequence(
        provider_rows,
        page=provider_health_page,
        per_page=provider_health_per_page,
    )

    inventory_items = [
        {
            'label': 'Projects',
            'value': len(projects),
            'icon': 'folder-kanban',
            'role': 'Scope',
        },
        {
            'label': 'Repositories',
            'value': len(repositories),
            'icon': 'package-open',
            'role': 'Catalog',
        },
        {
            'label': 'Artifacts',
            'value': artifact_total,
            'icon': 'fingerprint',
            'role': 'Immutable',
        },
        {
            'label': 'Tags',
            'value': tag_count,
            'icon': 'tags',
            'role': 'Aliases',
        },
        {
            'label': 'Artifact Footprint',
            'value': _fmt_bytes(total_size_bytes),
            'icon': 'database',
            'role': 'Storage',
        },
        {
            'label': 'Public Projects',
            'value': public_project_count,
            'icon': 'globe-2',
            'role': 'Exposure',
        },
    ]

    if selected_provider is not None:
        selected_key = int(selected_provider.id)
        selected_state = _state_view(state_by_provider.get(selected_key))
        selected_metrics = metrics_by_provider.get(selected_key, {})
        selected_analytics = _analytics_snapshot_view(
            analytics_by_provider.get(selected_key)
        )
        if artifact_total == 0 and selected_state['status'] == 'ready':
            security_status = 'No Artifacts'
            security_tone = 'info'
            security_value = 'No committed artifacts to scan'
        elif scanned_count:
            security_status = 'Available'
            security_tone = 'normal'
            security_value = f'{scanned_count} / {artifact_total} artifacts scanned'
        else:
            security_status = 'Required'
            security_tone = 'warning' if artifact_total else 'unknown'
            security_value = 'No committed security evidence'

        freshness = [
            {
                'label': 'Inventory Snapshot',
                'status': selected_state['label'],
                'tone': selected_state['tone'],
                'value': _human_time(selected_state['committed_at']),
                'description': 'Committed projects, repositories, artifacts, tags, and provider provenance.',
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
                'value': _human_time(selected_analytics['generated_at']),
                'description': 'Materialized Registry growth, forecast, runtime, and recommendation evidence.',
                'icon': 'chart-no-axes-combined',
            },
        ]
    else:
        freshness = [
            {
                'label': 'Inventory Fleet',
                'status': (
                    'Ready'
                    if len(ready_states) == len(scoped_providers) and scoped_providers
                    else ('Partial' if ready_states else 'Required')
                ),
                'tone': (
                    'normal'
                    if len(ready_states) == len(scoped_providers) and scoped_providers
                    else ('warning' if ready_states else 'unknown')
                ),
                'value': f'{len(ready_states)} / {len(scoped_providers)} providers',
                'description': 'Registry providers with a committed inventory snapshot.',
                'icon': 'database-zap',
            },
            {
                'label': 'Metrics Fleet',
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
                'value': f'{metrics_ready_count} / {len(scoped_providers)} providers',
                'description': 'Registry providers with an eligible validated Metrics Source binding.',
                'icon': 'activity',
            },
            {
                'label': 'Security Coverage',
                'status': 'Available' if scanned_count else 'Required',
                'tone': 'normal' if scanned_count else 'unknown',
                'value': f'{scanned_count} / {artifact_total} artifacts scanned',
                'description': 'Committed vulnerability scan coverage across the current Registry scope.',
                'icon': 'shield-check',
            },
            {
                'label': 'Analytics Fleet',
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
                'value': f'{analytics_ready_count} / {len(scoped_providers)} providers',
                'description': 'Providers with a ready Registry analytics materialization.',
                'icon': 'chart-no-axes-combined',
            },
        ]

    return {
        'setup': {'is_blocked': not providers, 'provider_count': len(providers)},
        'providers': providers,
        'selected_provider': selected_provider,
        'selected_provider_id': (
            int(selected_provider.id)
            if selected_provider is not None
            else None
        ),
        'scope_label': scope_label,
        'active_tab': normalized_tab,
        'provider_count': len(scoped_providers),
        'project_count': len(projects),
        'repository_count': len(repositories),
        'artifact_count': artifact_total,
        'tag_count': tag_count,
        'latest_committed_at': latest,
        'posture': posture,
        'snapshot_count': len(ready_states),
        'stale_snapshot_count': stale_count,
        'pending_snapshot_count': pending_snapshot_count,
        'total_size_bytes': total_size_bytes,
        'total_size': _fmt_bytes(total_size_bytes),
        'pull_count': pull_count,
        'public_project_count': public_project_count,
        'scanned_count': scanned_count,
        'scan_coverage': scan_coverage,
        'critical_findings': critical_findings,
        'high_findings': high_findings,
        'runtime_binding_count': len(runtime_bindings),
        'digest_runtime_binding_count': digest_runtime_bindings,
        'metrics_ready_count': metrics_ready_count,
        'analytics_ready_count': analytics_ready_count,
        'provider_rows': visible_provider_rows,
        'provider_health_pagination': provider_health_pagination,
        'inventory_items': inventory_items,
        'freshness': freshness,
        'sync_required': pending_snapshot_count > 0,
        'kpis': [
            {
                'label': 'Projects',
                'value': len(projects),
                'description': 'Committed provider-neutral namespaces.',
                'icon': 'folder-kanban',
            },
            {
                'label': 'Repositories',
                'value': len(repositories),
                'description': 'Committed Registry repositories.',
                'icon': 'package-open',
            },
            {
                'label': 'Artifacts',
                'value': artifact_total,
                'description': 'Digest-oriented committed identities.',
                'icon': 'fingerprint',
            },
            {
                'label': 'Tags',
                'value': tag_count,
                'description': 'Mutable aliases linked to committed digests.',
                'icon': 'tags',
            },
        ],
    }


def _project_row(item: RegistryProject) -> dict[str, Any]:
    return {
        'id': item.id,
        'name': item.name,
        'public': item.public,
        'repository_count': item.repository_count if item.repository_count is not None else len(item.repositories),
        'provider': item.integration_instance_id,
        'observed_at': item.observed_at,
    }


def _repository_row(item: RegistryRepository) -> dict[str, Any]:
    return {
        'id': item.id,
        'name': item.name,
        'project': item.project.name,
        'artifact_count': item.artifact_count if item.artifact_count is not None else len(item.artifacts),
        'pull_count': item.pull_count,
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
        'observed_at': item.observed_at,
    }


def build_inventory(*, resource: str, page: int, per_page: int, search: str = '') -> dict[str, Any]:
    resource = resource if resource in {'projects', 'repositories', 'artifacts'} else 'projects'
    search_value = search.strip().lower()
    if resource == 'repositories':
        items = RegistryRepository.query.options(
            joinedload(RegistryRepository.project),
            joinedload(RegistryRepository.artifacts),
        ).all()
        rows = [_repository_row(item) for item in items]
        filtered = [
            row
            for row in rows
            if not search_value or search_value in f"{row['name']} {row['project']}".lower()
        ]
    elif resource == 'artifacts':
        items = RegistryArtifact.query.options(
            joinedload(RegistryArtifact.repository).joinedload(RegistryRepository.project),
            joinedload(RegistryArtifact.tags),
        ).all()
        rows = [_artifact_row(item) for item in items]
        filtered = [
            row
            for row in rows
            if not search_value
            or search_value
            in f"{row['digest']} {row['repository']} {row['project']} {' '.join(row['tags'])}".lower()
        ]
    else:
        items = RegistryProject.query.options(joinedload(RegistryProject.repositories)).all()
        rows = [_project_row(item) for item in items]
        filtered = [row for row in rows if not search_value or search_value in row['name'].lower()]
    paged, pagination = paginate_sequence(filtered, page=page, per_page=per_page)
    overview = build_overview()
    return {
        'resource': resource,
        'rows': paged,
        'pagination': pagination,
        'search': search,
        'total': len(filtered),
        'setup': overview['setup'],
        'overview': overview,
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
        has_scan = bool(artifact.scan_status)
        scanned += int(has_scan)
        signature = str(artifact.signature_status or 'not_observed')
        sbom = str(artifact.sbom_status or 'not_observed')
        signed += int(signature == 'signed')
        sbom_available += int(sbom == 'available')
        scan_status = str(artifact.scan_status or 'not_scanned')
        scan_ready = scan_status in {'success', 'finished', 'completed'}
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
