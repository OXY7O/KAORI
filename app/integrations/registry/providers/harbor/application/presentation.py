from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.common.pagination import paginate_sequence
from app.common.presentation import present_user_datetime
from app.integrations.registry.providers.harbor.capabilities import CAPABILITIES, CAPABILITY_PROFILE
from app.integrations.runtime.presentation import runtime_history_view, runtime_observation_state_view
from app.integrations.runtime.repository import paginate_runtime_history
from app.models.harbor import HarborInstance
from app.models.integration import IntegrationInstance


@dataclass(frozen=True, slots=True)
class HarborIndexQuery:
    query: str = ''
    environment: str = ''
    readiness: str = ''
    compatibility: str = ''
    page: int = 1
    per_page: int = 5


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


def build_index_context(query: HarborIndexQuery | None = None) -> dict[str, Any]:
    query = query or HarborIndexQuery()
    instances = (
        HarborInstance.query.join(HarborInstance.integration_instance)
        .order_by(IntegrationInstance.name.asc())
        .all()
    )
    rows = [
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
        }
        for instance in instances
    ]
    filtered = _filter_rows(
        rows,
        query=query.query,
        environment=query.environment,
        readiness=query.readiness,
        compatibility=query.compatibility,
    )
    page_rows, pagination = paginate_sequence(filtered, page=query.page, per_page=query.per_page)
    ready = sum(1 for item in instances if item.readiness_status == 'ready')
    return {
        'rows': page_rows,
        'pagination': pagination,
        'selected_query': query.query,
        'selected_environment': query.environment,
        'selected_readiness': query.readiness,
        'selected_compatibility': query.compatibility,
        'has_active_filters': bool(query.query or query.environment or query.readiness or query.compatibility),
        'environment_options': sorted({row['environment'] for row in rows if row.get('environment')}),
        'readiness_options': [
            {'value': 'ready', 'label': 'Ready'},
            {'value': 'blocked', 'label': 'Blocked'},
            {'value': 'validation_required', 'label': 'Validation Required'},
        ],
        'compatibility_options': sorted(
            {row['compatibility_profile'] for row in rows if row.get('compatibility_profile')}
        ),
        'stats': {
            'total': len(instances),
            'ready': ready,
            'attention': len(instances) - ready,
        },
    }


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
    return {
        'instance': instance,
        'canonical': instance.integration_instance,
        'runtime_state': runtime_state,
        'runtime_history': runtime_history_view(runtime_rows, pagination=runtime_pagination),
        'capability_registry': capability_registry,
        'validated_at_display': present_user_datetime(instance.last_validated_at, empty='Not validated'),
        'checked_at_display': present_user_datetime(instance.last_checked_at, empty='Not observed'),
        'capability_count': len(instance.capabilities or ()),
    }


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
    rows: list[dict[str, Any]] = []
    for definition in CAPABILITIES:
        available = definition.key in observed
        row_status = 'ready' if available else ('blocked' if definition.required else 'degraded')
        rows.append(
            {
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
                'evidence': (
                    f'Full Validation observed {definition.label} in the persisted Harbor capability snapshot.'
                    if available
                    else (
                        f'Full Validation did not observe required capability {definition.label}.'
                        if definition.required
                        else f'Optional capability {definition.label} is not observed in this foundation validation scope.'
                    )
                ),
                'success_criteria': definition.success_criteria or definition.description,
                'impact': definition.impact or (
                    'Required Harbor provider capability used to establish Registry readiness.'
                    if definition.required
                    else 'Optional read-only evidence that can support future Registry workflows.'
                ),
                'next_action': (
                    'No corrective action is required. Revalidate after Harbor upgrades or credential changes.'
                    if available
                    else (
                        'Verify Harbor endpoint access and read permissions, then rerun Full Validation.'
                        if definition.required
                        else 'No readiness remediation is required; this optional capability belongs to a follow-on Registry workstream.'
                    )
                ),
                'remediation': (
                    []
                    if available or not definition.required
                    else (
                        list(definition.remediation)
                        if definition.remediation
                        else [
                            'Verify the registered Harbor endpoint and read-only credential permissions.',
                            'Rerun Full Validation and confirm this capability becomes Ready.',
                        ]
                    )
                ),
                'technical_checks': [],
            }
        )

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
