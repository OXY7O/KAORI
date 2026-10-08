from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.common.pagination import paginate_sequence
from app.common.presentation import present_user_datetime
from app.integrations.asset_owner_sources import build_bound_observability_source_rows
from app.integrations.deletion import asset_owner_deletion_guard
from app.integrations.registry.eligibility import RegistryInventoryEligibility, registry_inventory_eligibility
from app.integrations.registry.observability import RegistryMetricsReadiness, registry_metrics_readiness
from app.integrations.registry.providers.harbor.capabilities import CAPABILITIES, CAPABILITY_PROFILE
from app.integrations.runtime.presentation import runtime_history_view, runtime_observation_state_view
from app.integrations.runtime.repository import paginate_runtime_history
from app.models.harbor import HarborInstance
from app.models.integration import IntegrationInstance
from app.models.registry import RegistryCollectionState, RegistryWebhookEndpoint


@dataclass(frozen=True, slots=True)
class HarborIndexQuery:
    tab: str = 'coverage'
    query: str = ''
    environment: str = ''
    readiness: str = ''
    compatibility: str = ''
    page: int = 1
    per_page: int = 5
    coverage_query: str = ''
    coverage_environment: str = ''
    coverage_status: str = ''
    coverage_page: int = 1
    coverage_per_page: int = 5


@dataclass(frozen=True, slots=True)
class HarborDetailQuery:
    capability_query: str = ''
    capability_requirement: str = ''
    capability_status: str = ''
    capability_page: int = 1
    capability_per_page: int = 5
    history_page: int = 1
    history_per_page: int = 5
    history_trigger: str = ''
    history_health: str = ''
    history_readiness: str = ''
    binding_page: int = 1
    binding_per_page: int = 5


def build_index_context(query: HarborIndexQuery | None = None) -> dict[str, Any]:
    query = query or HarborIndexQuery()
    instances = (
        HarborInstance.query.join(HarborInstance.integration_instance).order_by(IntegrationInstance.name.asc()).all()
    )
    identity_ids = [int(instance.integration_instance_id) for instance in instances]
    collection_states = {
        int(state.integration_instance_id): state
        for state in (
            RegistryCollectionState.query.filter(
                RegistryCollectionState.integration_instance_id.in_(identity_ids)
            ).all()
            if identity_ids
            else []
        )
    }
    webhook_endpoints = {
        int(endpoint.integration_instance_id): endpoint
        for endpoint in (
            RegistryWebhookEndpoint.query.filter(
                RegistryWebhookEndpoint.integration_instance_id.in_(identity_ids)
            ).all()
            if identity_ids
            else []
        )
    }

    rows: list[dict[str, Any]] = []
    coverage_rows: list[dict[str, Any]] = []
    total_bindings = 0

    for instance in instances:
        identity = instance.integration_instance
        metrics = registry_metrics_readiness(identity)
        binding_count = int(metrics.get('binding_count') or 0)
        total_bindings += binding_count

        collection = collection_states.get(int(identity.id))
        webhook = webhook_endpoints.get(int(identity.id))
        api_status = _provider_status(instance)
        inventory_eligibility = registry_inventory_eligibility(identity)
        inventory_status = _inventory_status(collection, eligibility=inventory_eligibility)
        metrics_status = _metrics_status(metrics)
        webhook_status = _webhook_status(webhook)

        complete = all(
            item['status'] == 'ready' for item in (api_status, inventory_status, metrics_status, webhook_status)
        )
        coverage_status = 'ready' if complete else 'attention'
        coverage_label = 'Complete' if complete else 'Partial'

        rows.append(
            {
                'id': instance.id,
                'name': instance.name,
                'environment': instance.environment,
                'endpoint': instance.endpoint,
                'auth_type': instance.auth_type,
                'readiness_status': instance.readiness_status or 'validation_required',
                'compatibility_profile': instance.compatibility_profile,
                'detected_version': instance.detected_version,
                'last_checked': present_user_datetime(instance.last_checked_at, empty='Not observed'),
                'binding_count': binding_count,
            }
        )
        coverage_rows.append(
            {
                'instance': instance,
                'identity': identity,
                'name': identity.name,
                'environment': identity.environment,
                'api_status': api_status,
                'inventory_status': inventory_status,
                'metrics_status': metrics_status,
                'webhook_status': webhook_status,
                'coverage_status': coverage_status,
                'coverage_label': coverage_label,
            }
        )

    filtered = _filter_rows(
        rows,
        query=query.query,
        environment=query.environment,
        readiness=query.readiness,
        compatibility=query.compatibility,
    )
    filtered_coverage = _filter_coverage_rows(
        coverage_rows,
        query=query.coverage_query,
        environment=query.coverage_environment,
        status=query.coverage_status,
    )
    page_rows, pagination = paginate_sequence(filtered, page=query.page, per_page=query.per_page)
    coverage_page_rows, coverage_pagination = paginate_sequence(
        filtered_coverage,
        page=query.coverage_page,
        per_page=query.coverage_per_page,
    )
    ready = sum(1 for item in instances if item.readiness_status == 'ready')
    return {
        'rows': page_rows,
        'coverage_rows': coverage_page_rows,
        'pagination': pagination,
        'coverage_pagination': coverage_pagination,
        'active_tab': query.tab if query.tab in {'coverage', 'registry'} else 'coverage',
        'selected_query': query.query,
        'selected_environment': query.environment,
        'selected_readiness': query.readiness,
        'selected_compatibility': query.compatibility,
        'selected_coverage_query': query.coverage_query,
        'selected_coverage_environment': query.coverage_environment,
        'selected_coverage_status': query.coverage_status,
        'registry_has_active_filters': bool(query.query or query.environment or query.readiness or query.compatibility),
        'coverage_has_active_filters': bool(
            query.coverage_query or query.coverage_environment or query.coverage_status
        ),
        'environment_options': sorted({row['environment'] for row in rows if row.get('environment')}),
        'readiness_options': [
            {'value': 'ready', 'label': 'Ready'},
            {'value': 'degraded', 'label': 'Degraded'},
            {'value': 'blocked', 'label': 'Blocked'},
            {'value': 'validation_required', 'label': 'Validation Required'},
        ],
        'compatibility_options': sorted(
            {row['compatibility_profile'] for row in rows if row.get('compatibility_profile')}
        ),
        'coverage_environment_options': sorted({row['environment'] for row in coverage_rows if row.get('environment')}),
        'coverage_status_options': [
            {'value': 'ready', 'label': 'Complete'},
            {'value': 'attention', 'label': 'Partial'},
        ],
        'stats': {
            'total': len(instances),
            'configured': len(instances),
            'ready': ready,
            'attention': len(instances) - ready,
            'bindings': total_bindings,
            'uncovered': sum(1 for row in coverage_rows if row['coverage_status'] != 'ready'),
        },
    }


def _provider_status(instance: HarborInstance) -> dict[str, str]:
    readiness = str(instance.readiness_status or 'validation_required')
    if readiness == 'ready':
        return {'status': 'ready', 'label': 'Ready', 'detail': 'Full Validation ready'}
    if readiness == 'degraded':
        return {
            'status': 'attention',
            'label': 'Degraded',
            'detail': 'Full Validation completed with compatibility attention',
        }
    if readiness == 'blocked':
        return {'status': 'blocked', 'label': 'Blocked', 'detail': 'Provider readiness blocked'}
    return {'status': 'attention', 'label': 'Validation Required', 'detail': 'Run Full Validation'}


def _inventory_status(
    state: RegistryCollectionState | None,
    *,
    eligibility: RegistryInventoryEligibility | None = None,
) -> dict[str, str]:
    if state is None or state.status == 'not_collected':
        if eligibility is not None and not eligibility.eligible:
            return {
                'status': 'blocked' if eligibility.readiness == 'blocked' else 'attention',
                'label': 'No Committed Inventory',
                'detail': eligibility.reason,
            }
        return {
            'status': 'unknown',
            'label': 'No Committed Inventory',
            'detail': 'No committed inventory snapshot; run Artifact Registry inventory synchronization.',
        }
    if state.status == 'ready':
        observed = present_user_datetime(state.last_observed_at, empty='Committed')
        return {'status': 'ready', 'label': 'Committed Snapshot', 'detail': observed}
    if state.status == 'failed':
        return {'status': 'blocked', 'label': 'Collection Failed', 'detail': 'Last reconciliation failed'}
    if state.status == 'collecting':
        return {'status': 'attention', 'label': 'Collecting', 'detail': 'Reconciliation in progress'}
    return {'status': 'unknown', 'label': 'No Committed Inventory', 'detail': 'No committed inventory snapshot'}


def _metrics_status(metrics: RegistryMetricsReadiness) -> dict[str, str]:
    status = str(metrics.get('status') or 'not_bound')
    source = str(metrics.get('selected_source') or '').strip()
    if status == 'ready':
        return {'status': 'ready', 'label': 'Ready', 'detail': source or 'Validated Metrics Source'}
    if status == 'unavailable':
        return {'status': 'attention', 'label': 'Unavailable', 'detail': 'Bound source is not currently eligible'}
    return {'status': 'unknown', 'label': 'Not Bound', 'detail': 'No validated Metrics Source binding'}


def _webhook_status(endpoint: RegistryWebhookEndpoint | None) -> dict[str, str]:
    if endpoint is None or not endpoint.enabled:
        return {'status': 'unknown', 'label': 'Not Enabled', 'detail': 'Scheduled reconciliation remains authoritative'}
    if endpoint.last_status == 'refresh_failed':
        return {'status': 'attention', 'label': 'Degraded', 'detail': 'Last webhook refresh failed'}
    detail = present_user_datetime(endpoint.last_event_at, empty='Awaiting first event')
    return {'status': 'ready', 'label': 'Ready', 'detail': detail}


def _filter_coverage_rows(
    rows: list[dict[str, Any]],
    *,
    query: str,
    environment: str,
    status: str,
) -> list[dict[str, Any]]:
    normalized_query = str(query or '').strip().lower()
    filtered = rows
    if normalized_query:
        filtered = [
            row
            for row in filtered
            if normalized_query
            in ' '.join(
                str(value or '')
                for value in (
                    row.get('name'),
                    row.get('environment'),
                    getattr(row.get('instance'), 'endpoint', ''),
                    row.get('api_status', {}).get('label'),
                    row.get('inventory_status', {}).get('label'),
                    row.get('metrics_status', {}).get('detail'),
                    row.get('webhook_status', {}).get('label'),
                )
            ).lower()
        ]
    if environment:
        filtered = [row for row in filtered if row.get('environment') == environment]
    if status:
        filtered = [row for row in filtered if row.get('coverage_status') == status]
    return filtered


def build_detail_context(
    instance: HarborInstance,
    query: HarborDetailQuery | None = None,
) -> dict[str, Any]:
    query = query or HarborDetailQuery()
    runtime_rows, runtime_pagination = paginate_runtime_history(
        'registry',
        str(instance.id),
        page=query.history_page,
        per_page=query.history_per_page,
        trigger_type=query.history_trigger,
        health_status=query.history_health,
        readiness=query.history_readiness,
    )
    latest_rows, _latest_pagination = paginate_runtime_history('registry', str(instance.id), page=1, per_page=5)
    latest_runtime = latest_rows[0] if latest_rows else None
    runtime_state = runtime_observation_state_view(
        latest_runtime,
        fallback_readiness=instance.readiness_status or 'validation_required',
        fallback_compatibility_profile=instance.compatibility_profile,
        fallback_capabilities=tuple(instance.capabilities or ()),
    )
    if not runtime_state.get('has_observation'):
        runtime_state = {
            **runtime_state,
            'message': 'No persisted Harbor runtime observation is available yet.',
            'summary': 'No persisted Harbor runtime observation is available yet.',
        }
    capability_registry = build_harbor_capability_registry(
        instance,
        query=query.capability_query,
        requirement=query.capability_requirement,
        status=query.capability_status,
        page=query.capability_page,
        per_page=query.capability_per_page,
    )
    identity = instance.integration_instance
    collection_state = RegistryCollectionState.query.filter_by(
        integration_instance_id=identity.id,
    ).first()
    inventory_eligibility = registry_inventory_eligibility(identity)
    webhook_endpoint = RegistryWebhookEndpoint.query.filter_by(
        integration_instance_id=identity.id,
    ).first()
    metrics_readiness = registry_metrics_readiness(identity)
    all_binding_rows = build_bound_observability_source_rows(
        asset_type='registry_instance',
        asset_key=str(identity.id),
    )
    binding_rows, binding_pagination = paginate_sequence(
        all_binding_rows,
        page=query.binding_page,
        per_page=query.binding_per_page,
    )
    raw_counts = collection_state.counts if collection_state and isinstance(collection_state.counts, dict) else {}
    inventory_counts = {key: int(raw_counts.get(key) or 0) for key in ('projects', 'repositories', 'artifacts', 'tags')}
    return {
        'instance': instance,
        'canonical': identity,
        'runtime_state': runtime_state,
        'runtime_history': runtime_history_view(runtime_rows, pagination=runtime_pagination),
        'capability_registry': capability_registry,
        'validated_at_display': present_user_datetime(instance.last_validated_at, empty='Not validated'),
        'checked_at_display': present_user_datetime(instance.last_checked_at, empty='Not observed'),
        'capability_count': len(instance.capabilities or ()),
        'collection_state': collection_state,
        'inventory_status': _inventory_status(collection_state, eligibility=inventory_eligibility),
        'inventory_eligibility': inventory_eligibility,
        'inventory_counts': inventory_counts,
        'inventory_observed_at_display': present_user_datetime(
            collection_state.last_observed_at if collection_state else None,
            empty='Not Collected',
        ),
        'metrics_readiness': metrics_readiness,
        'metrics_status': _metrics_status(metrics_readiness),
        'webhook_endpoint': webhook_endpoint,
        'webhook_status': _webhook_status(webhook_endpoint),
        'binding_rows': binding_rows,
        'binding_total': len(all_binding_rows),
        'binding_pagination': binding_pagination,
        'deletion_guard': asset_owner_deletion_guard(
            integration_type='registry',
            integration_instance_id=int(identity.id),
            asset_type='registry_instance',
            asset_key=str(identity.id),
        ),
    }


def _capability_row(definition: Any, observed: set[str]) -> dict[str, Any]:
    available = definition.key in observed
    row_status = 'ready' if available else ('blocked' if definition.required else 'degraded')
    if available:
        evidence = f'Full Validation observed {definition.label} in the persisted Harbor capability snapshot.'
        next_action = 'No corrective action is required. Revalidate after Harbor upgrades or credential changes.'
    elif definition.required:
        evidence = f'Full Validation did not observe required capability {definition.label}.'
        next_action = 'Verify Harbor endpoint access and read permissions, then rerun Full Validation.'
    else:
        evidence = f'Optional capability {definition.label} is not observed in this foundation validation scope.'
        next_action = (
            'No readiness remediation is required; this optional capability belongs to a follow-on Registry workstream.'
        )

    remediation = []
    if not available and definition.required:
        remediation = (
            list(definition.remediation)
            if definition.remediation
            else [
                'Verify the registered Harbor endpoint and read-only credential permissions.',
                'Rerun Full Validation and confirm this capability becomes Ready.',
            ]
        )
    return {
        'key': definition.key,
        'label': definition.label,
        'description': definition.description,
        'required': bool(definition.required),
        'requirement_label': 'Required' if definition.required else 'Optional',
        'status': row_status,
        'status_label': 'Ready' if available else ('Blocked' if definition.required else 'Not Observed'),
        'available': available,
        'contract': CAPABILITY_PROFILE,
        'category': definition.category,
        'source_owner': 'Harbor API v2.0',
        'evidence': evidence,
        'success_criteria': definition.success_criteria or definition.description,
        'impact': definition.impact
        or (
            'Required Harbor provider capability used to establish Registry readiness.'
            if definition.required
            else 'Optional read-only evidence that can support future Registry workflows.'
        ),
        'next_action': next_action,
        'remediation': remediation,
        'technical_checks': [],
    }


def _filter_capability_rows(
    rows: list[dict[str, Any]],
    *,
    query: str,
    requirement: str,
    status: str,
) -> tuple[list[dict[str, Any]], str, str, str]:
    normalized_query = str(query or '').strip().lower()
    normalized_requirement = str(requirement or '').strip().lower()
    normalized_status = str(status or '').strip().lower()
    if normalized_query:
        rows = [
            row
            for row in rows
            if normalized_query
            in ' '.join(
                str(value or '') for value in (row['key'], row['label'], row['description'], row['contract'])
            ).lower()
        ]
    if normalized_requirement in {'required', 'optional'}:
        want_required = normalized_requirement == 'required'
        rows = [row for row in rows if row['required'] is want_required]
    else:
        normalized_requirement = ''
    if normalized_status in {'ready', 'blocked', 'degraded'}:
        rows = [row for row in rows if row['status'] == normalized_status]
    else:
        normalized_status = ''
    return rows, normalized_query, normalized_requirement, normalized_status


def build_harbor_capability_registry(
    instance: HarborInstance,
    *,
    query: str = '',
    requirement: str = '',
    status: str = '',
    page: int = 1,
    per_page: int = 5,
) -> dict[str, Any]:
    observed = set(instance.capabilities or ())
    rows = [_capability_row(definition, observed) for definition in CAPABILITIES]
    rows, normalized_query, normalized_requirement, normalized_status = _filter_capability_rows(
        rows,
        query=query,
        requirement=requirement,
        status=status,
    )
    page_rows, pagination = paginate_sequence(rows, page=page, per_page=per_page)
    required_keys = {item.key for item in CAPABILITIES if item.required}
    optional_keys = {item.key for item in CAPABILITIES if not item.required}
    required_ready_count = len(observed.intersection(required_keys))
    optional_ready_count = len(observed.intersection(optional_keys))
    return {
        'rows': page_rows,
        'pagination': pagination,
        'filters': {
            'query': normalized_query,
            'requirement': normalized_requirement,
            'status': normalized_status,
        },
        'total_contracts': len(CAPABILITIES),
        'ready_count': len(observed.intersection({item.key for item in CAPABILITIES})),
        'required_count': len(required_keys),
        'required_ready_count': required_ready_count,
        'required_missing_count': len(required_keys) - required_ready_count,
        'optional_count': len(optional_keys),
        'optional_ready_count': optional_ready_count,
    }


def _filter_rows(
    rows: list[dict[str, Any]],
    *,
    query: str,
    environment: str,
    readiness: str,
    compatibility: str,
) -> list[dict[str, Any]]:
    normalized_query = str(query or '').strip().lower()
    filtered = rows
    if normalized_query:
        filtered = [
            row
            for row in filtered
            if normalized_query
            in ' '.join(
                str(value or '')
                for value in (
                    row.get('name'),
                    row.get('environment'),
                    row.get('endpoint'),
                    row.get('compatibility_profile'),
                    row.get('detected_version'),
                )
            ).lower()
        ]
    if environment:
        filtered = [row for row in filtered if row.get('environment') == environment]
    if readiness:
        filtered = [row for row in filtered if row.get('readiness_status') == readiness]
    if compatibility:
        filtered = [row for row in filtered if row.get('compatibility_profile') == compatibility]
    return filtered
