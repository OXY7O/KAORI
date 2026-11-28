"""Central provider-origin read scope; provider adapters retain authorization and evidence ownership."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from flask import abort
from flask.typing import ResponseReturnValue
from flask_login import current_user
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.datastructures import MultiDict

from app.access.scope_policy import ScopeAdmission, evaluate_exact_vault_instance_case_scope
from app.common.pagination import paginate_sequence
from app.extensions.db import db
from app.intelligence.alert_intelligence.vault_case_workspace import (
    read_scoped_vault_cases,
    vault_case_details_response,
)
from app.intelligence.alert_intelligence.vault_delivery_command import read_local_vault_policies
from app.intelligence.alert_intelligence.vault_operator_service import local_reconcile_available, resolve_operator_binding
from app.models.integration import IntegrationInstance
from app.models.scope_access import ScopeAccessPolicy

_MAX_SCOPE_OPTIONS = 32
DOMAIN_OPTIONS = [
    {'value': 'kubernetes', 'label': 'Kubernetes'},
    {'value': 'object_storage', 'label': 'Object Storage'},
    {'value': 'registry', 'label': 'Artifact Registry'},
    {'value': 'secrets_pki', 'label': 'Secrets & PKI'},
]


@dataclass(frozen=True, slots=True)
class ProviderCaseAdapter:
    label: str
    permission: str
    authorize: Callable[..., ScopeAdmission]
    read: Callable[..., dict[str, Any]]
    detail: Callable[..., ResponseReturnValue]


# Registration is a read capability only, not provider admission or lifecycle activation.
_ADAPTERS = {
    'secrets_pki': {
        'vault': ProviderCaseAdapter(
            'HashiCorp Vault',
            'secrets_pki.view',
            evaluate_exact_vault_instance_case_scope,
            read_scoped_vault_cases,
            vault_case_details_response,
        ),
    },
}


def is_provider_case_domain(domain: str) -> bool:
    return domain in _ADAPTERS


def registered_provider_case_adapters() -> frozenset[tuple[str, str]]:
    """Implementation registry only; does not establish source/runtime qualification."""
    return frozenset((domain, provider) for domain, adapters in _ADAPTERS.items() for provider in adapters)


def _authorized_instances(domain: str) -> list[dict[str, str]]:
    """Only enumerate the actor's exact grants, never the provider fleet."""
    actor_id = getattr(current_user, 'id', None)
    if type(actor_id) is not int:
        return []
    adapters = _ADAPTERS[domain]
    try:
        candidate_ids = (
            db.session.query(ScopeAccessPolicy.integration_instance_id)
            .filter(
                ScopeAccessPolicy.principal_user_id == actor_id,
                ScopeAccessPolicy.permission_key.in_({adapter.permission for adapter in adapters.values()}),
                ScopeAccessPolicy.scope_level == 'instance',
                ScopeAccessPolicy.provider_namespace.is_(None),
                ScopeAccessPolicy.mount.is_(None),
            )
            .distinct()
            .order_by(ScopeAccessPolicy.integration_instance_id)
            .limit(_MAX_SCOPE_OPTIONS + 1)
            .all()
        )
        if len(candidate_ids) > _MAX_SCOPE_OPTIONS:
            return []
        options = []
        for (instance_id,) in candidate_ids:
            instance = db.session.get(IntegrationInstance, instance_id)
            adapter = adapters.get(instance.provider_key) if instance and instance.integration_type == domain else None
            if adapter is None or instance is None:
                continue
            decision = adapter.authorize(actor_user_id=actor_id, instance_id=instance_id)
            if decision.status == 'unavailable':
                return []
            if decision.allowed:
                options.append(
                    {
                        'value': str(instance_id),
                        'label': instance.name,
                        'environment': instance.environment or '-',
                        'provider': instance.provider_key,
                    }
                )
        return sorted(options, key=lambda option: (option['label'], option['value']))
    except (SQLAlchemyError, ValueError, TypeError):
        return []
    finally:
        # Selector metadata is not authorization for a case read. Release
        # policy locks; the owning adapter must recheck and commit its audit.
        db.session.rollback()


def provider_scope_context(args: MultiDict[str, str]) -> dict[str, Any]:
    domain = str(args.get('domain') or '')
    adapters = _ADAPTERS[domain]
    options = _authorized_instances(domain)
    provider_options = [
        {'value': key, 'label': adapter.label}
        for key, adapter in adapters.items()
        if any(option['provider'] == key for option in options)
    ]
    requested_asset = str(args.get('asset') or '')
    requested_provider = str(args.get('provider') or '')
    matched = next((option for option in options if option['value'] == requested_asset), None)
    # Existing tab and pagination links already carry the exact instance.
    # Derive its provider only from the authorized option, never from input.
    if not requested_provider and matched:
        requested_provider = matched['provider']
    provider = next((option for option in provider_options if option['value'] == requested_provider), None)
    assets = [option for option in options if provider and option['provider'] == provider['value']]
    selected = next((option for option in assets if option['value'] == requested_asset), None)
    return {
        'provider_options': provider_options,
        'selected_provider': provider['value'] if provider else '',
        'assets': [{'value': '', 'label': 'Select Authorized Instance', 'environment': '-'}, *assets],
        'selected_asset_key': selected['value'] if selected else '',
        'selected_asset_name': selected['label'] if selected else 'Instance Scope Required',
        'provider_label': provider['label'] if provider else 'Provider Scope Required',
    }


def _read_filters(args: MultiDict[str, str]) -> dict[str, str]:
    return {
        key: str(args.get(key) or default)
        for key, default in (
            ('severity', 'all'),
            ('workflow', 'all'),
            ('source', 'all'),
            ('source_state', 'all'),
            ('q', ''),
        )
    }


def _case_record(row: dict[str, Any], scope: dict[str, Any]) -> dict[str, Any]:
    """Map only the adapter's allowlisted projection to the shared registry."""
    return {
        'public_id': row['public_id'],
        'alert_name': row['title'],
        'asset_name': scope['selected_asset_name'],
        'namespace': '-',
        'severity_label': row['severity'].title(),
        'severity_tone': row['severity'],
        'source_type_label': 'Provider Alert · ' + scope['provider_label'],
        'source_state_label': {
            'firing': 'Fresh firing evidence', 'resolved': 'Committed recovery',
            'conflict': 'Source evidence conflict', 'unknown': 'Source unknown'
        }[row['source_state']],
        'source_state_tone': {'firing': 'warning', 'resolved': 'normal', 'conflict': 'critical', 'unknown': 'unknown'}[row['source_state']],
        'workflow_label': row['workflow_state'].replace('_', ' ').title(),
        'workflow_tone': {'open': 'critical', 'acknowledged': 'info', 'mitigating': 'warning',
                          'verification_pending': 'warning', 'closed': 'normal'}[row['workflow_state']],
        'owner': row['owner_label'],
        'duration': '—',
        'delivery_label': 'Explicit only',
        'delivery_tone': 'unknown',
    }


def build_provider_case_payload(args: MultiDict[str, str], *, domain_options: list[dict[str, str]]) -> dict[str, Any]:
    from app.intelligence.alert_intelligence.provider_coverage import provider_coverage_rows

    domain = str(args.get('domain') or '')
    scope = provider_scope_context(args)
    filters = _read_filters(args)
    tab = str(args.get('tab') or 'overview')
    if tab == 'history':
        tab = 'resolved'
    if tab not in {'overview', 'active', 'routing', 'templates', 'silences', 'resolved'}:
        tab = 'overview'
    if tab == 'resolved':
        filters['history'] = '1'
    status = 'scope_required'
    result: dict[str, Any] = {}
    if scope['selected_asset_key']:
        adapter = _ADAPTERS[domain][scope['selected_provider']]
        result = adapter.read(
            instance_id=int(scope['selected_asset_key']),
            page=str(args.get('page') or '1'),
            per_page=str(args.get('per_page') or '5'),
            filters=filters,
        )
        status = result['status']
    _, empty_pagination = paginate_sequence([], page=1, per_page=5)
    summary = result.get('summary', {}) if status == 'ready' else {}
    records = [_case_record(row, scope) for row in result.get('rows', [])] if status == 'ready' else []
    actor_id = getattr(current_user, 'id', None)
    can_reconcile = (
        status == 'ready'
        and domain == 'secrets_pki'
        and scope['selected_provider'] == 'vault'
        and type(actor_id) is int
        and local_reconcile_available(actor_id=actor_id, instance_id=int(scope['selected_asset_key']))
    )
    routing = None
    if tab == 'routing' and status == 'ready' and type(actor_id) is int:
        instance_id = int(scope['selected_asset_key'])
        binding_id = resolve_operator_binding(instance_id)
        if binding_id is not None:
            routing = read_local_vault_policies(
                instance_id=instance_id, binding_id=binding_id, actor_id=actor_id,
                page=str(args.get('routing_page') or '1'), per_page=str(args.get('routing_per_page') or '5'),
            )
    return {
        **scope,
        'local_routing': routing,
        'local_case_reconcile': can_reconcile,
        'domain': domain,
        'domain_label': next(option['label'] for option in domain_options if option['value'] == domain),
        'domain_options': domain_options,
        'provider_coverage': provider_coverage_rows(),
        'provider_case_mode': True,
        'provider_case_status': status,
        'scope_invalid': status != 'ready',
        'tab': tab,
        'snapshot': {
            'available': False,
            'label': (
                ('Committed provider cases · local UAT' if can_reconcile else 'Committed provider cases · read-only')
                if status == 'ready'
                else 'Evidence Review Required'
            ),
            'tone': 'warning',
            'serving_last_good': False,
        },
        'summary': {
            'active': summary.get('active'),
            'critical': summary.get('critical'),
            'source_unknown': summary.get('source_unknown'),
            'resolved_total': summary.get('resolved_total'),
            'verification_pending': summary.get('verification_pending'),
            'closed': summary.get('closed'),
            'source_conflicts': summary.get('source_conflicts'),
        },
        'filters': filters,
        'active_cases': records,
        'active_pagination': result.get('pagination') or empty_pagination,
        'selected_case': None,
    }


def provider_case_detail_response(args: MultiDict[str, str], public_id: str) -> ResponseReturnValue:
    scope = provider_scope_context(args)
    if not scope['selected_asset_key']:
        abort(404)
    adapter = _ADAPTERS[str(args.get('domain'))][scope['selected_provider']]
    return adapter.detail(public_id, instance_id=int(scope['selected_asset_key']), central=True)
