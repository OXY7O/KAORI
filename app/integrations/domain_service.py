from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import selectinload

from app.common.pagination import paginate_sequence
from app.integrations.binding_selectors import selector_summary
from app.integrations.contracts import IntegrationNotRegistered
from app.integrations.registry import IntegrationModule, registry
from app.integrations.taxonomy import (
    asset_types_for_domain,
    capability_definitions_for_domain,
    domain_key_for_asset_type,
    get_domain_definition,
)
from app.models.integration import IntegrationBinding, IntegrationInstance


def build_integration_domain_page(
    domain_key: str,
    *,
    active_tab: str = 'registry',
    provider_page: int = 1,
    provider_per_page: int = 5,
    binding_page: int = 1,
    binding_per_page: int = 5,
) -> dict[str, Any]:
    """Build one taxonomy-owned Integration domain page from canonical identities."""

    domain = get_domain_definition(domain_key)
    modules = tuple(module for module in registry.all() if module.domain_key == domain.key)
    instances = _load_domain_instances(modules)
    related_bindings = _load_related_bindings(domain.key, modules)

    provider_types = _provider_type_rows(modules, instances)
    capability_rows = _capability_rows(domain.key, modules, provider_types, related_bindings)
    provider_registry_rows = _provider_registry_rows(modules, instances)
    binding_registry_rows = _binding_registry_rows(related_bindings)

    provider_rows, provider_pagination = paginate_sequence(
        provider_registry_rows,
        page=provider_page,
        per_page=provider_per_page,
    )
    binding_rows, binding_pagination = paginate_sequence(
        binding_registry_rows,
        page=binding_page,
        per_page=binding_per_page,
    )

    stats, posture_status = _domain_stats(
        modules,
        instances,
        capability_rows,
        related_bindings,
    )
    normalized_tab = active_tab if active_tab in {'registry', 'bindings'} else 'registry'
    return {
        'domain': domain,
        'providers': provider_types,
        'capabilities': capability_rows,
        'provider_registry_rows': provider_rows,
        'provider_registry_pagination': provider_pagination,
        'binding_registry_rows': binding_rows,
        'binding_registry_pagination': binding_pagination,
        'active_tab': normalized_tab,
        'stats': stats,
        'posture_status': posture_status,
    }


def _load_domain_instances(modules: tuple[IntegrationModule, ...]) -> list[IntegrationInstance]:
    provider_types = tuple(module.provider_type for module in modules)
    if not provider_types:
        return []
    return (
        IntegrationInstance.query.options(selectinload(IntegrationInstance.bindings))
        .filter(IntegrationInstance.provider_type.in_(provider_types))
        .order_by(IntegrationInstance.provider_type.asc(), IntegrationInstance.name.asc())
        .all()
    )


def _load_related_bindings(
    domain_key: str,
    modules: tuple[IntegrationModule, ...],
) -> list[IntegrationBinding]:
    provider_types = tuple(module.provider_type for module in modules)
    owned_asset_types = asset_types_for_domain(domain_key)
    clauses = []
    if provider_types:
        clauses.append(IntegrationInstance.provider_type.in_(provider_types))
    if owned_asset_types:
        clauses.append(IntegrationBinding.asset_type.in_(owned_asset_types))
    if not clauses:
        return []

    return (
        IntegrationBinding.query.options(selectinload(IntegrationBinding.instance))
        .join(
            IntegrationInstance,
            IntegrationBinding.integration_instance_id == IntegrationInstance.id,
        )
        .filter(or_(*clauses))
        .order_by(
            IntegrationBinding.asset_type.asc(),
            IntegrationBinding.asset_key.asc(),
            IntegrationBinding.priority.asc(),
            IntegrationBinding.id.asc(),
        )
        .all()
    )


def _provider_type_rows(
    modules: tuple[IntegrationModule, ...],
    instances: list[IntegrationInstance],
) -> list[dict[str, Any]]:
    instances_by_provider: dict[str, list[IntegrationInstance]] = {}
    for instance in instances:
        instances_by_provider.setdefault(instance.provider_type, []).append(instance)
    return [_provider_type_row(module, instances_by_provider.get(module.provider_type, [])) for module in modules]


def _provider_type_row(module: IntegrationModule, targets: list[IntegrationInstance]) -> dict[str, Any]:
    enabled_targets = _enabled_targets(targets)
    ready = sum(1 for item in enabled_targets if item.readiness_status == 'ready')
    attention = len(enabled_targets) - ready
    bindings = _enabled_binding_count(enabled_targets)
    return {
        'key': module.provider_type,
        'label': module.label,
        'runtime_label': module.runtime_label or module.label,
        'icon': module.icon,
        'description': module.description,
        'capability_key': module.capability_key,
        'capability_label': module.capability.label,
        'workspace_endpoint': module.workspace_endpoint,
        'registered': len(targets),
        'enabled': len(enabled_targets),
        'ready': ready,
        'attention': attention,
        'bindings': bindings,
        'status': _readiness_posture(enabled=len(enabled_targets), ready=ready),
    }


def _provider_registry_rows(
    modules: tuple[IntegrationModule, ...],
    instances: list[IntegrationInstance],
) -> list[dict[str, Any]]:
    module_by_provider = {module.provider_type: module for module in modules}
    rows: list[dict[str, Any]] = []
    for instance in instances:
        module = module_by_provider.get(instance.provider_type)
        if module is None:
            continue
        record = module.get_record_for_canonical(instance.id)
        detail_url = None
        if record is not None:
            detail_url = module.detail_url(record.id, section='').rstrip('#')
        enabled_bindings = sum(1 for binding in instance.bindings if binding.enabled)
        readiness = _instance_readiness(instance)
        rows.append(
            {
                'id': instance.id,
                'name': instance.name,
                'environment': _humanize(instance.environment, empty='Environment not specified'),
                'provider_label': module.runtime_label or module.label,
                'provider_type': module.provider_type,
                'provider_icon': module.icon,
                'capability_label': module.capability.label,
                'readiness': readiness,
                'health': _humanize(instance.health_status, empty='Not observed'),
                'enabled': bool(instance.enabled and instance.lifecycle_status == 'active'),
                'bindings': enabled_bindings,
                'last_checked': _format_timestamp(instance.last_checked_at),
                'detail_url': detail_url,
                'workspace_endpoint': module.workspace_endpoint,
            }
        )
    return rows


def _binding_registry_rows(bindings: list[IntegrationBinding]) -> list[dict[str, Any]]:
    asset_labels = _asset_identity_labels(bindings)
    rows: list[dict[str, Any]] = []
    for binding in bindings:
        instance = binding.instance
        try:
            module = registry.get(instance.provider_type)
        except IntegrationNotRegistered:
            continue
        record = module.get_record_for_canonical(instance.id)
        detail_url = None
        if record is not None:
            detail_url = module.detail_url(record.id, section='').rstrip('#')
        asset_identity = (binding.asset_type, str(binding.asset_key))
        rows.append(
            {
                'id': binding.id,
                'consumer_label': asset_labels.get(asset_identity) or _humanize(binding.asset_type),
                'asset_type_label': _humanize(binding.asset_type),
                'asset_key': str(binding.asset_key),
                'source_name': instance.name,
                'source_provider': module.runtime_label or module.label,
                'source_icon': module.icon,
                'role': _humanize(binding.binding_role, empty='Primary'),
                'priority': binding.priority,
                'profile': binding.validation_profile or 'Native Provider Contract',
                'selector': selector_summary(binding.selector_json, empty='Native / unscoped'),
                'validation_status': _binding_status(binding),
                'validation_message': binding.validation_message or 'Binding validation has not reported detail.',
                'last_validated': _format_timestamp(binding.last_validated_at),
                'enabled': bool(binding.enabled),
                'detail_url': detail_url,
                'workspace_endpoint': module.workspace_endpoint,
            }
        )
    return rows


def _asset_identity_labels(bindings: list[IntegrationBinding]) -> dict[tuple[str, str], str]:
    labels: dict[tuple[str, str], str] = {}
    for binding in bindings:
        owner_domain = domain_key_for_asset_type(binding.asset_type)
        if owner_domain is None:
            continue
        try:
            module = registry.get(binding.instance.provider_type)
        except IntegrationNotRegistered:
            continue
        if module.domain_key != owner_domain:
            continue
        labels[(binding.asset_type, str(binding.asset_key))] = binding.instance.name
    return labels


def _capability_rows(
    domain_key: str,
    modules: tuple[IntegrationModule, ...],
    provider_rows: list[dict[str, Any]],
    related_bindings: list[IntegrationBinding],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for capability in capability_definitions_for_domain(domain_key):
        capability_modules = tuple(module for module in modules if module.capability_key == capability.key)
        providers = [row for row in provider_rows if row['capability_key'] == capability.key]
        counts = _sum_provider_counts(providers)
        relevant_bindings = _capability_binding_count(capability.asset_types, capability_modules, related_bindings)
        rows.append(
            {
                'key': capability.key,
                'label': capability.label,
                'description': capability.description,
                'provider_count': len(capability_modules),
                'provider_labels': [module.runtime_label or module.label for module in capability_modules],
                **counts,
                'bindings': relevant_bindings,
                'availability': 'available' if capability_modules else 'not_registered',
                'status': _readiness_posture(enabled=counts['enabled'], ready=counts['ready']),
            }
        )
    return rows


def _capability_binding_count(
    asset_types: tuple[str, ...],
    modules: tuple[IntegrationModule, ...],
    bindings: list[IntegrationBinding],
) -> int:
    provider_types = {module.provider_type for module in modules}
    return sum(
        1
        for binding in bindings
        if binding.enabled
        and ((asset_types and binding.asset_type in asset_types) or binding.instance.provider_type in provider_types)
    )


def _sum_provider_counts(rows: Iterable[dict[str, Any]]) -> dict[str, int]:
    materialized = tuple(rows)
    return {key: sum(int(row[key]) for row in materialized) for key in ('registered', 'enabled', 'ready', 'attention')}


def _domain_stats(
    modules: tuple[IntegrationModule, ...],
    instances: list[IntegrationInstance],
    capability_rows: list[dict[str, Any]],
    related_bindings: list[IntegrationBinding],
) -> tuple[dict[str, int], str]:
    enabled_targets = _enabled_targets(instances)
    ready_targets = sum(1 for item in enabled_targets if item.readiness_status == 'ready')
    attention_targets = len(enabled_targets) - ready_targets
    stats = {
        'provider_types': len(modules),
        'capability_types': len(capability_rows),
        'registered_targets': len(instances),
        'enabled_targets': len(enabled_targets),
        'ready_targets': ready_targets,
        'attention_targets': attention_targets,
        'bindings': sum(1 for binding in related_bindings if binding.enabled),
    }
    return stats, _readiness_posture(enabled=len(enabled_targets), ready=ready_targets)


def _enabled_targets(instances: Iterable[IntegrationInstance]) -> list[IntegrationInstance]:
    return [item for item in instances if item.enabled and item.lifecycle_status == 'active']


def _enabled_binding_count(instances: Iterable[IntegrationInstance]) -> int:
    return sum(sum(1 for binding in item.bindings if binding.enabled) for item in instances)


def _instance_readiness(instance: IntegrationInstance) -> str:
    if not instance.enabled or instance.lifecycle_status != 'active':
        return 'disabled'
    return str(instance.readiness_status or 'validation_required').strip().lower()


def _binding_status(binding: IntegrationBinding) -> str:
    if not binding.enabled:
        return 'disabled'
    return str(binding.validation_status or 'validation_required').strip().lower()


def _humanize(value: Any, *, empty: str = 'Not configured') -> str:
    normalized = str(value or '').strip()
    if not normalized:
        return empty
    return normalized.replace('_', ' ').replace('-', ' ').title()


def _format_timestamp(value: Any) -> str:
    if value is None:
        return 'Not yet'
    try:
        return value.strftime('%Y-%m-%d %H:%M UTC')
    except (AttributeError, ValueError):
        return str(value)


def _readiness_posture(*, enabled: int, ready: int) -> str:
    if enabled <= 0:
        return 'not_configured'
    if ready == enabled:
        return 'ready'
    return 'attention'
