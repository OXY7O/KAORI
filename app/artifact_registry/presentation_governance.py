from __future__ import annotations

from typing import Any

from sqlalchemy.orm import joinedload

from app.artifact_registry.presentation_common import _aware_datetime, _providers, _state_view
from app.artifact_registry.presentation_overview import build_overview
from app.common.pagination import paginate_sequence
from app.models.registry import (
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


def _governance_project_rows(identity_by_id: dict[int, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    items = (
        RegistryProjectGovernance.query.options(joinedload(RegistryProjectGovernance.project))
        .order_by(
            RegistryProjectGovernance.observed_at.desc(),
            RegistryProjectGovernance.id.desc(),
        )
        .all()
    )
    for item in items:
        identity = identity_by_id.get(int(item.project.integration_instance_id))
        retention = _policy_state_view(item.retention_status)
        immutability = _policy_state_view(item.immutability_status)
        rows.append(
            {
                'project': item.project.name,
                'provider_label': (
                    str((identity.metadata_json or {}).get('provider_label') or identity.provider_key.title())
                    if identity is not None
                    else 'Registry'
                ),
                'retention_status': str(item.retention_status or 'not_collected'),
                'retention_label': retention['label'],
                'retention_tone': retention['tone'],
                'immutability_status': str(item.immutability_status or 'not_collected'),
                'immutability_label': immutability['label'],
                'immutability_tone': immutability['tone'],
                'observed_at': item.observed_at,
            }
        )
    return rows


def _governance_replication_rows(identity_by_id: dict[int, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in RegistryReplicationPolicy.query.order_by(
        RegistryReplicationPolicy.name.asc(),
        RegistryReplicationPolicy.id.asc(),
    ).all():
        identity = identity_by_id.get(int(item.integration_instance_id))
        rows.append(
            {
                'name': item.name,
                'provider_label': (
                    str((identity.metadata_json or {}).get('provider_label') or identity.provider_key.title())
                    if identity is not None
                    else 'Registry'
                ),
                'enabled': item.enabled,
                'trigger_type': item.trigger_type,
                'source_registry': item.source_registry,
                'destination_registry': item.destination_registry,
                'destination_namespace': item.destination_namespace,
                'observed_at': item.observed_at,
            }
        )
    return rows


def _governance_capability_counts(
    governance_states: dict[int, RegistryGovernanceState],
) -> dict[str, dict[str, int]]:
    capability_counts: dict[str, dict[str, int]] = {}
    for capability in ('retention', 'immutability', 'replication'):
        counts = {'observed': 0, 'unavailable': 0, 'unsupported': 0, 'unknown': 0}
        for state in governance_states.values():
            raw = (state.capability_states or {}).get(capability) if isinstance(state.capability_states, dict) else None
            status = str(raw.get('status') or 'unknown') if isinstance(raw, dict) else 'unknown'
            counts[status if status in counts else 'unknown'] += 1
        capability_counts[capability] = counts
    return capability_counts


def _governance_summary(
    identities: list[Any],
    identity_by_id: dict[int, Any],
    governance_states: dict[int, RegistryGovernanceState],
    project_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    provider_count = len(identities)
    project_total = (
        RegistryProject.query.filter(RegistryProject.integration_instance_id.in_(identity_by_id)).count()
        if identity_by_id
        else 0
    )
    ready_count = sum(
        1
        for identity in identities
        if governance_states.get(int(identity.id)) is not None
        and governance_states[int(identity.id)].status == 'ready'
        and governance_states[int(identity.id)].last_committed_at is not None
    )
    state_views = [_state_view(governance_states.get(int(identity.id))) for identity in identities]
    exception_count = sum(
        1 for view in state_views if view['status'] != 'ready' or view.get('is_stale') or view.get('refresh_failed')
    )
    latest_committed_at = max(
        (
            _aware_datetime(state.last_committed_at)
            for state in governance_states.values()
            if state.last_committed_at is not None
        ),
        default=None,
    )
    return {
        'provider_count': provider_count,
        'project_total': project_total,
        'ready_count': ready_count,
        'exception_count': exception_count,
        'latest_committed_at': latest_committed_at,
        'retention_configured': sum(1 for row in project_rows if row['retention_status'] == 'configured'),
        'retention_unavailable': sum(1 for row in project_rows if row['retention_status'] == 'unavailable'),
        'retention_not_configured': sum(1 for row in project_rows if row['retention_status'] == 'not_configured'),
        'immutability_configured': sum(1 for row in project_rows if row['immutability_status'] == 'configured'),
        'immutability_unavailable': sum(1 for row in project_rows if row['immutability_status'] == 'unavailable'),
        'immutability_not_configured': sum(1 for row in project_rows if row['immutability_status'] == 'not_configured'),
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
        'Current'
        if provider_count and ready_count == provider_count and exception_count == 0
        else ('Not Collected' if ready_count == 0 else 'Attention')
    )
    return {
        'source_label': 'Committed Registry Governance Evidence',
        'status': status,
        'tone': 'normal' if status == 'Current' else ('unknown' if status == 'Not Collected' else 'warning'),
        'description': 'Retention, immutability, and replication evidence committed from Registry providers.',
        'latest_collected_at': summary['latest_committed_at'],
        'scope_label': f'{provider_count} Registry Provider' + ('' if provider_count == 1 else 's'),
        'coverage_label': f'{ready_count}/{provider_count} Providers Committed',
        'coverage_supporting': 'Provider-neutral Governance snapshots.',
        'coverage_tone': 'normal' if provider_count and ready_count == provider_count else 'warning',
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


def _governance_posture_cards(
    summary: dict[str, Any],
    *,
    project_rows: list[dict[str, Any]],
    replication_rows: list[dict[str, Any]],
    capability_counts: dict[str, dict[str, int]],
) -> list[dict[str, Any]]:
    project_total = summary['project_total']
    provider_count = summary['provider_count']
    ready_count = summary['ready_count']
    retention_observed = summary['retention_configured'] + summary['retention_not_configured']
    immutability_observed = summary['immutability_configured'] + summary['immutability_not_configured']
    return [
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
            'tone': 'normal' if project_total and retention_observed == project_total else ('warning' if project_total else 'unknown'),
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
            'tone': 'normal' if project_total and immutability_observed == project_total else ('warning' if project_total else 'unknown'),
            'detail': (
                f'{summary["immutability_configured"]} configured · '
                f'{summary["immutability_not_configured"]} not configured · '
                f'{summary["immutability_unavailable"]} unavailable.'
            ),
        },
        {
            'label': 'Replication Coverage',
            'value': f'{capability_counts["replication"]["observed"]}/{provider_count} Providers',
            'status_label': 'Observed' if ready_count else 'Not Collected',
            'tone': (
                'normal'
                if provider_count and capability_counts['replication']['observed'] == provider_count
                else ('warning' if ready_count else 'unknown')
            ),
            'detail': (
                f'{len(replication_rows)} policies · '
                f'{capability_counts["replication"]["unavailable"]} unavailable · '
                f'{capability_counts["replication"]["unsupported"]} unsupported.'
            ),
        },
    ]


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
    governance_states = {int(item.integration_instance_id): item for item in RegistryGovernanceState.query.all()}
    project_rows = _governance_project_rows(identity_by_id)
    replication_rows = _governance_replication_rows(identity_by_id)
    capability_counts = _governance_capability_counts(governance_states)
    summary = _governance_summary(identities, identity_by_id, governance_states, project_rows)
    normalized_tab = active_tab if active_tab in {'policies', 'replication'} else 'policies'
    active_rows = project_rows if normalized_tab == 'policies' else replication_rows
    page_rows, pagination = paginate_sequence(active_rows, page=page, per_page=per_page)
    return {
        'setup': overview['setup'],
        'provider_count': summary['provider_count'],
        'project_count': len(project_rows),
        'replication_count': len(replication_rows),
        'governance_ready_count': summary['ready_count'],
        'posture': _governance_posture(summary),
        'snapshot_context': _governance_snapshot_context(summary),
        'posture_cards': _governance_posture_cards(
            summary,
            project_rows=project_rows,
            replication_rows=replication_rows,
            capability_counts=capability_counts,
        ),
        'active_tab': normalized_tab,
        'rows': page_rows,
        'pagination': pagination,
        'filter_query': {'tab': normalized_tab},
        'sync_state': build_registry_governance_sync_state(),
    }
