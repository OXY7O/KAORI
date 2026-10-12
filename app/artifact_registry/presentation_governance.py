from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, or_
from sqlalchemy.orm import joinedload

from app.artifact_registry.presentation_common import _aware_datetime, _providers, _state_view
from app.artifact_registry.presentation_overview import build_overview
from app.common.pagination import paginate_query
from app.models.integration import IntegrationInstance
from app.models.registry import (
    RegistryCollectionState,
    RegistryGovernanceState,
    RegistryProject,
    RegistryProjectGovernance,
    RegistryReplicationPolicy,
)


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


def _governance_source_name(identity: Any) -> str:
    return f'{identity.name} · {identity.provider_key.title()}'


def _governance_project_rows(items: list[Any], identity_by_id: dict[int, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in items:
        identity = identity_by_id[int(item.project.integration_instance_id)]
        retention = _policy_state_view(item.retention_status)
        immutability = _policy_state_view(item.immutability_status)
        rows.append({
            'project': item.project.name,
            'provider_label': _governance_source_name(identity),
            'retention_status': str(item.retention_status or 'not_collected'),
            'retention_label': retention['label'],
            'retention_tone': retention['tone'],
            'immutability_status': str(item.immutability_status or 'not_collected'),
            'immutability_label': immutability['label'],
            'immutability_tone': immutability['tone'],
            'observed_at': item.observed_at,
        })
    return rows


def _governance_replication_rows(items: list[Any], identity_by_id: dict[int, Any]) -> list[dict[str, Any]]:
    return [
        {
            'name': item.name,
            'provider_label': _governance_source_name(identity_by_id[int(item.integration_instance_id)]),
            'enabled': item.enabled,
            'trigger_type': item.trigger_type,
            'source_registry': item.source_registry,
            'destination_registry': item.destination_registry,
            'destination_namespace': item.destination_namespace,
            'observed_at': item.observed_at,
        }
        for item in items
    ]


def _governance_capability_counts(
    governance_states: dict[int, RegistryGovernanceState],
    source_ids: list[int],
) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {}
    for capability in ('retention', 'immutability', 'replication'):
        counts = {'observed': 0, 'unavailable': 0, 'unsupported': 0, 'unknown': 0}
        for source_id in source_ids:
            state = governance_states.get(source_id)
            raw = (
                (state.capability_states or {}).get(capability)
                if state and isinstance(state.capability_states, dict)
                else None
            )
            status = str(raw.get('status') or 'unknown') if isinstance(raw, dict) else 'unknown'
            counts[status if status in counts else 'unknown'] += 1
        result[capability] = counts
    return result


def _governance_inventory_changed(
    governance_state: RegistryGovernanceState | None,
    inventory_state: RegistryCollectionState | None,
) -> bool:
    if governance_state is None or governance_state.last_committed_at is None:
        return False
    metadata = governance_state.metadata_json if isinstance(governance_state.metadata_json, dict) else {}
    recorded = metadata.get('inventory_committed_at')
    current = inventory_state.last_committed_at if inventory_state is not None else None
    if not recorded or current is None:
        # Legacy snapshots with no recorded generation are not proven current.
        return True
    try:
        recorded_at = _aware_datetime(datetime.fromisoformat(str(recorded).replace('Z', '+00:00')))
    except ValueError:
        return True
    return recorded_at != _aware_datetime(current)


def _governance_evidence_counts(source_ids: list[int]) -> dict[str, int]:
    counts = {
        'policy_rows': 0,
        'replication_rows': 0,
        'retention_configured': 0,
        'retention_unavailable': 0,
        'retention_not_configured': 0,
        'immutability_configured': 0,
        'immutability_unavailable': 0,
        'immutability_not_configured': 0,
    }
    if not source_ids:
        return counts

    grouped = (
        RegistryProjectGovernance.query.join(
            RegistryProject, RegistryProjectGovernance.project_id == RegistryProject.id
        )
        .filter(RegistryProject.integration_instance_id.in_(source_ids))
        .with_entities(
            RegistryProjectGovernance.retention_status,
            RegistryProjectGovernance.immutability_status,
            func.count(RegistryProjectGovernance.id),
        )
        .group_by(RegistryProjectGovernance.retention_status, RegistryProjectGovernance.immutability_status)
        .all()
    )
    for retention_status, immutability_status, amount in grouped:
        count = int(amount)
        counts['policy_rows'] += count
        if retention_status in {'configured', 'unavailable', 'not_configured'}:
            counts[f'retention_{retention_status}'] += count
        if immutability_status in {'configured', 'unavailable', 'not_configured'}:
            counts[f'immutability_{immutability_status}'] += count
    counts['replication_rows'] = RegistryReplicationPolicy.query.filter(
        RegistryReplicationPolicy.integration_instance_id.in_(source_ids)
    ).count()
    return counts


def _governance_summary(
    identities: list[Any],
    states: dict[int, RegistryGovernanceState],
    inventory_states: dict[int, RegistryCollectionState],
    evidence_counts: dict[str, int],
) -> dict[str, Any]:
    source_ids = [int(source.id) for source in identities]
    provider_count = len(source_ids)
    project_total = RegistryProject.query.filter(
        RegistryProject.integration_instance_id.in_(source_ids)
    ).count() if source_ids else 0
    ready_count = sum(
        1 for source_id in source_ids
        if (state := states.get(source_id)) is not None
        and state.status in {'ready', 'partial'}
        and state.last_committed_at is not None
    )
    state_views = [_state_view(states.get(source_id)) for source_id in source_ids]
    changed_count = sum(
        _governance_inventory_changed(states.get(source_id), inventory_states.get(source_id))
        for source_id in source_ids
    )
    exception_count = 0
    for source_id, view in zip(source_ids, state_views, strict=True):
        source_state = states.get(source_id)
        capabilities = (
            source_state.capability_states
            if source_state is not None and isinstance(source_state.capability_states, dict)
            else {}
        )
        capability_incomplete = any(
            not isinstance(capabilities.get(name), dict)
            or capabilities[name].get('status') in {'unavailable', 'unknown'}
            for name in ('retention', 'immutability', 'replication')
        )
        if (
            view['status'] != 'ready'
            or view.get('is_stale')
            or view.get('refresh_failed')
            or capability_incomplete
            or _governance_inventory_changed(source_state, inventory_states.get(source_id))
        ):
            exception_count += 1
    latest_committed_at = max(
        (
            committed_at
            for source_id in source_ids
            if (state := states.get(source_id)) is not None
            if (committed_at := _aware_datetime(state.last_committed_at)) is not None
        ),
        default=None,
    )
    return {
        'provider_count': provider_count,
        'project_total': project_total,
        'ready_count': ready_count,
        'exception_count': exception_count,
        'inputs_changed_count': changed_count,
        'latest_committed_at': latest_committed_at,
        **evidence_counts,
    }


def _governance_posture(summary: dict[str, Any]) -> dict[str, str]:
    if not summary['provider_count']:
        return {'label': 'Setup Required', 'tone': 'unknown'}
    if summary['ready_count'] == 0:
        return {'label': 'Governance Sync Required', 'tone': 'warning'}
    if summary['exception_count']:
        return {'label': 'Evidence Attention', 'tone': 'warning'}
    return {'label': 'Committed Evidence Ready', 'tone': 'normal'}


def _governance_snapshot_context(summary: dict[str, Any]) -> dict[str, Any]:
    provider_count = summary['provider_count']
    ready_count = summary['ready_count']
    exception_count = summary['exception_count']
    status = (
        'Inputs Changed' if summary['inputs_changed_count']
        else 'Current' if provider_count and ready_count == provider_count and exception_count == 0
        else 'Not Collected' if ready_count == 0
        else 'Attention'
    )
    return {
        'source_label': 'Committed Registry Governance Evidence',
        'status': status,
        'tone': 'normal' if status == 'Current' else ('unknown' if status == 'Not Collected' else 'warning'),
        'description': (
            'Committed Registry Inventory changed since Governance Sync; refresh Governance evidence.'
            if status == 'Inputs Changed'
            else 'Retention, immutability, and replication evidence committed from Registry providers.'
        ),
        'latest_collected_at': summary['latest_committed_at'],
        'scope_label': f'{provider_count} Registry Provider' + ('' if provider_count == 1 else 's'),
        'coverage_label': f'{ready_count}/{provider_count} Providers Committed',
        'coverage_supporting': 'Provider-neutral Governance snapshots.',
        'coverage_tone': (
            'normal' if provider_count and ready_count == provider_count and not exception_count else 'warning'
        ),
        'exception_count': exception_count,
        'exceptions_label': (
            'No Exceptions'
            if provider_count and exception_count == 0
            else f'{exception_count} Evidence Exception' + ('' if exception_count == 1 else 's')
            if exception_count
            else 'Not Collected'
        ),
        'exceptions_supporting': (
            'Missing, stale, partial, unavailable, or superseded Governance collection.'
            if exception_count
            else 'No freshness or collection exceptions.' if provider_count else 'No active Registry providers.'
        ),
        'exceptions_tone': 'normal' if provider_count and exception_count == 0 else 'warning',
    }


def _governance_posture_cards(
    summary: dict[str, Any],
    *,
    capability_counts: dict[str, dict[str, int]],
) -> list[dict[str, Any]]:
    project_total = summary['project_total']
    provider_count = summary['provider_count']
    ready_count = summary['ready_count']
    retention_observed = summary['retention_configured'] + summary['retention_not_configured']
    immutability_observed = summary['immutability_configured'] + summary['immutability_not_configured']
    replication = capability_counts['replication']
    replication_status = (
        'Observed' if replication['observed']
        else 'Unavailable' if replication['unavailable']
        else 'Unsupported' if replication['unsupported'] and replication['unsupported'] == provider_count
        else 'Not Collected'
    )
    return [
        {
            'label': 'Policy Coverage',
            'value': f'{summary["policy_rows"]}/{project_total} Projects',
            'status_label': (
                'Committed'
                if project_total and summary['policy_rows'] == project_total
                else 'Partial' if summary['policy_rows'] else 'Not Collected'
            ),
            'tone': (
                'normal' if project_total and summary['policy_rows'] == project_total
                else 'warning' if summary['policy_rows'] else 'unknown'
            ),
            'detail': 'Committed project retention and immutability evidence.',
        },
        {
            'label': 'Retention Coverage',
            'value': f'{retention_observed}/{project_total} Projects',
            'status_label': 'Observed' if retention_observed else 'Not Collected',
            'tone': 'normal' if project_total and retention_observed == project_total else (
                'warning' if project_total else 'unknown'
            ),
            'detail': (
                f'{summary["retention_configured"]} configured · '
                f'{summary["retention_not_configured"]} not configured · '
                f'{summary["retention_unavailable"]} unavailable.'
            ),
        },
        {
            'label': 'Immutability Coverage',
            'value': f'{immutability_observed}/{project_total} Projects',
            'status_label': 'Observed' if immutability_observed else 'Not Collected',
            'tone': 'normal' if project_total and immutability_observed == project_total else (
                'warning' if project_total else 'unknown'
            ),
            'detail': (
                f'{summary["immutability_configured"]} configured · '
                f'{summary["immutability_not_configured"]} not configured · '
                f'{summary["immutability_unavailable"]} unavailable.'
            ),
        },
        {
            'label': 'Replication Coverage',
            'value': f'{replication["observed"]}/{provider_count} Providers',
            'status_label': replication_status,
            'tone': 'normal' if provider_count and replication['observed'] == provider_count else (
                'warning' if provider_count else 'unknown'
            ),
            'detail': (
                f'{summary["replication_rows"]} policies · '
                f'{replication["unavailable"]} unavailable · '
                f'{replication["unsupported"]} unsupported.'
            ),
        },
    ]


def _governance_filtered_query(
    *,
    active_tab: str,
    source_ids: list[int],
    provider: str,
    search: str,
    retention: str,
    immutability: str,
    state: str,
    identities: list[Any],
) -> Any:
    if active_tab == 'policies':
        query = (
            RegistryProjectGovernance.query.join(
                RegistryProject, RegistryProjectGovernance.project_id == RegistryProject.id
            )
            .options(joinedload(RegistryProjectGovernance.project))
            .filter(RegistryProject.integration_instance_id.in_(source_ids))
        )
        source_col = RegistryProject.integration_instance_id
    else:
        query = RegistryReplicationPolicy.query.filter(
            RegistryReplicationPolicy.integration_instance_id.in_(source_ids)
        )
        source_col = RegistryReplicationPolicy.integration_instance_id
    if provider:
        selected = int(provider) if provider.isdecimal() else -1
        query = query.filter(source_col == selected if selected in source_ids else source_col == -1)
    if active_tab == 'policies':
        if retention:
            query = query.filter(RegistryProjectGovernance.retention_status == retention)
        if immutability:
            query = query.filter(RegistryProjectGovernance.immutability_status == immutability)
    elif state:
        query = query.filter(
            RegistryReplicationPolicy.enabled.is_(True if state == 'enabled' else False)
            if state != 'unknown'
            else RegistryReplicationPolicy.enabled.is_(None)
        )
    if search:
        escaped = search.casefold().replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
        pattern = f'%{escaped}%'
        matched_sources = [
            int(identity.id) for identity in identities
            if search.casefold() in _governance_source_name(identity).casefold()
        ]
        clauses = (
            [
                func.lower(RegistryProject.name).like(pattern, escape='\\'),
                RegistryProject.integration_instance_id.in_(matched_sources),
            ]
            if active_tab == 'policies'
            else [
                func.lower(RegistryReplicationPolicy.name).like(pattern, escape='\\'),
                func.lower(func.coalesce(RegistryReplicationPolicy.trigger_type, '')).like(pattern, escape='\\'),
                func.lower(func.coalesce(RegistryReplicationPolicy.source_registry, '')).like(pattern, escape='\\'),
                func.lower(func.coalesce(RegistryReplicationPolicy.destination_registry, '')).like(pattern, escape='\\'),
                func.lower(func.coalesce(RegistryReplicationPolicy.destination_namespace, '')).like(pattern, escape='\\'),
                RegistryReplicationPolicy.integration_instance_id.in_(matched_sources),
            ]
        )
        query = query.filter(or_(*clauses))
    return (
        query.order_by(RegistryProjectGovernance.observed_at.desc(), RegistryProjectGovernance.id.desc())
        if active_tab == 'policies'
        else query.order_by(RegistryReplicationPolicy.name.asc(), RegistryReplicationPolicy.id.asc())
    )


def _governance_replication_empty_state(
    *, provider_count: int, capability_counts: dict[str, int]
) -> dict[str, str]:
    observed = capability_counts.get('observed', 0)
    unavailable = capability_counts.get('unavailable', 0)
    unsupported = capability_counts.get('unsupported', 0)
    if provider_count and observed == provider_count:
        return {
            'title': 'No Replication Policies Configured',
            'description': (
                'The current committed governance snapshot successfully observed '
                'an empty replication policy inventory across the active Registry sources.'
            ),
        }
    if provider_count and unsupported == provider_count:
        return {
            'title': 'Replication Not Supported',
            'description': 'The active Registry providers report replication as unsupported.',
        }
    if unavailable:
        return {
            'title': 'Replication Evidence Unavailable',
            'description': (
                'Replication collection was unavailable for one or more Registry sources. '
                'Review Governance Sync diagnostics; absence of rows does not prove no policies.'
            ),
        }
    if observed:
        return {
            'title': 'No Replication Policies in Available Evidence',
            'description': (
                'Observed sources report no replication policies, but the remaining Registry '
                'sources are unsupported or have no usable committed evidence.'
            ),
        }
    return {
        'title': 'No Replication Evidence Collected',
        'description': (
            'No committed replication evidence is available for this scope. '
            'Run Governance Sync to collect supported provider evidence.'
        ),
    }


def build_governance(
    *,
    active_tab: str = 'policies',
    page: int = 1,
    per_page: int = 5,
    search: str = '',
    provider: str = '',
    retention: str = '',
    immutability: str = '',
    state: str = '',
) -> dict[str, Any]:
    from app.artifact_registry.governance_job_adapter import build_registry_governance_sync_state

    overview = build_overview()
    identities = _providers()
    identity_by_id = {int(item.id): item for item in identities}
    source_ids = list(identity_by_id)
    governance_states = {
        int(item.integration_instance_id): item
        for item in RegistryGovernanceState.query.filter(
            RegistryGovernanceState.integration_instance_id.in_(source_ids)
        ).all()
    }
    inventory_states = {
        int(item.integration_instance_id): item
        for item in RegistryCollectionState.query.filter(
            RegistryCollectionState.integration_instance_id.in_(source_ids)
        ).all()
    }
    capability_counts = _governance_capability_counts(governance_states, source_ids)
    evidence_counts = _governance_evidence_counts(source_ids)
    summary = _governance_summary(identities, governance_states, inventory_states, evidence_counts)
    normalized_tab = active_tab if active_tab in {'policies', 'replication'} else 'policies'
    search_value = search.strip()
    provider_value = provider.strip()
    policy_states = {'configured', 'not_configured', 'unavailable', 'unsupported', 'not_collected'}
    retention_value = retention.strip().lower() if normalized_tab == 'policies' else ''
    immutability_value = immutability.strip().lower() if normalized_tab == 'policies' else ''
    state_value = state.strip().lower() if normalized_tab == 'replication' else ''
    if retention_value not in policy_states:
        retention_value = ''
    if immutability_value not in policy_states:
        immutability_value = ''
    if state_value not in {'enabled', 'disabled', 'unknown'}:
        state_value = ''
    filters_active = bool(search_value or provider_value or retention_value or immutability_value or state_value)

    query = _governance_filtered_query(
        active_tab=normalized_tab,
        source_ids=source_ids,
        provider=provider_value,
        search=search_value,
        retention=retention_value,
        immutability=immutability_value,
        state=state_value,
        identities=identities,
    )
    items, pagination = paginate_query(query, page=page, per_page=per_page)
    rows = (
        _governance_project_rows(items, identity_by_id)
        if normalized_tab == 'policies'
        else _governance_replication_rows(items, identity_by_id)
    )
    filter_query = {'tab': normalized_tab, 'q': search_value, 'provider': provider_value}
    if normalized_tab == 'policies':
        filter_query.update({'retention': retention_value, 'immutability': immutability_value})
    else:
        filter_query['state'] = state_value
    sync_state = build_registry_governance_sync_state()
    snapshot_context = _governance_snapshot_context(summary)
    posture = _governance_posture(summary)
    if sync_state['label'] == 'Sync Failed':
        # A failed fleet refresh must be visible even if earlier committed
        # evidence is still fresh and readable.
        snapshot_context.update({
            'status': 'Refresh Failed' if summary['ready_count'] else 'Collection Failed',
            'tone': 'warning',
            'description': (
                'The latest Governance Sync failed; the previous committed evidence '
                'remains available where collected.'
            ),
            'exception_count': max(snapshot_context['exception_count'], 1),
            'exceptions_label': 'Latest Sync Failed',
            'exceptions_supporting': 'Review JobExecution errors before trusting freshness.',
            'exceptions_tone': 'warning',
        })
        posture = {'label': 'Evidence Attention', 'tone': 'warning'}
    return {
        'setup': overview['setup'],
        'provider_count': summary['provider_count'],
        'project_count': evidence_counts['policy_rows'],
        'replication_count': evidence_counts['replication_rows'],
        'governance_ready_count': summary['ready_count'],
        'posture': posture,
        'snapshot_context': snapshot_context,
        'posture_cards': _governance_posture_cards(summary, capability_counts=capability_counts),
        'capability_counts': capability_counts,
        'replication_empty': _governance_replication_empty_state(
            provider_count=summary['provider_count'],
            capability_counts=capability_counts['replication'],
        ),
        'active_tab': normalized_tab,
        'rows': rows,
        'pagination': pagination,
        'filter_query': filter_query,
        'filters': {
            'search': search_value,
            'provider': provider_value,
            'retention': retention_value,
            'immutability': immutability_value,
            'state': state_value,
        },
        'has_filters': filters_active,
        'provider_options': [
            {'id': int(identity.id), 'name': _governance_source_name(identity)}
            for identity in identities
        ],
        'sync_state': sync_state,
    }
