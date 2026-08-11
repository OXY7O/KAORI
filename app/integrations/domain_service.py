from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from sqlalchemy.orm import selectinload

from app.integrations.registry import IntegrationModule, registry
from app.integrations.taxonomy import capability_definitions_for_domain, get_domain_definition
from app.models.integration import IntegrationInstance


def build_integration_domain_page(domain_key: str) -> dict[str, Any]:
    """Build one taxonomy-owned Integration domain page from canonical identities."""

    domain = get_domain_definition(domain_key)
    modules = tuple(module for module in registry.all() if module.domain_key == domain.key)
    instances = _load_domain_instances(modules)
    provider_rows = _provider_rows(modules, instances)
    capability_rows = _capability_rows(domain.key, modules, provider_rows)
    stats, posture_status = _domain_stats(modules, instances, capability_rows)
    return {
        'domain': domain,
        'providers': provider_rows,
        'capabilities': capability_rows,
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


def _provider_rows(
    modules: tuple[IntegrationModule, ...],
    instances: list[IntegrationInstance],
) -> list[dict[str, Any]]:
    instances_by_provider: dict[str, list[IntegrationInstance]] = {}
    for instance in instances:
        instances_by_provider.setdefault(instance.provider_type, []).append(instance)
    return [_provider_row(module, instances_by_provider.get(module.provider_type, [])) for module in modules]


def _provider_row(module: IntegrationModule, targets: list[IntegrationInstance]) -> dict[str, Any]:
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


def _capability_rows(
    domain_key: str,
    modules: tuple[IntegrationModule, ...],
    provider_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for capability in capability_definitions_for_domain(domain_key):
        capability_modules = tuple(module for module in modules if module.capability_key == capability.key)
        providers = [row for row in provider_rows if row['capability_key'] == capability.key]
        counts = _sum_provider_counts(providers)
        rows.append(
            {
                'key': capability.key,
                'label': capability.label,
                'description': capability.description,
                'provider_count': len(capability_modules),
                'provider_labels': [module.runtime_label or module.label for module in capability_modules],
                **counts,
                'availability': 'available' if capability_modules else 'not_registered',
                'status': _readiness_posture(enabled=counts['enabled'], ready=counts['ready']),
            }
        )
    return rows


def _sum_provider_counts(rows: Iterable[dict[str, Any]]) -> dict[str, int]:
    materialized = tuple(rows)
    return {
        key: sum(int(row[key]) for row in materialized)
        for key in ('registered', 'enabled', 'ready', 'attention', 'bindings')
    }


def _domain_stats(
    modules: tuple[IntegrationModule, ...],
    instances: list[IntegrationInstance],
    capability_rows: list[dict[str, Any]],
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
        'bindings': _enabled_binding_count(enabled_targets),
    }
    return stats, _readiness_posture(enabled=len(enabled_targets), ready=ready_targets)


def _enabled_targets(instances: Iterable[IntegrationInstance]) -> list[IntegrationInstance]:
    return [item for item in instances if item.enabled and item.lifecycle_status == 'active']


def _enabled_binding_count(instances: Iterable[IntegrationInstance]) -> int:
    return sum(sum(1 for binding in item.bindings if binding.enabled) for item in instances)


def _readiness_posture(*, enabled: int, ready: int) -> str:
    if enabled <= 0:
        return 'not_configured'
    if ready == enabled:
        return 'ready'
    return 'attention'
