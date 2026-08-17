from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import load_only, selectinload

from app.common.pagination import paginate_sequence
from app.integrations.binding_selectors import selector_summary
from app.integrations.contracts import IntegrationNotRegistered
from app.integrations.prometheus.routing import normalize_routing_policy
from app.integrations.registry import IntegrationModule, registry
from app.integrations.taxonomy import (
    asset_types_for_domain,
    capability_definitions_for_domain,
    domain_key_for_asset_type,
    get_domain_definition,
)
from app.models.integration import IntegrationBinding, IntegrationInstance


@dataclass(frozen=True, slots=True)
class ProviderRegistryFilters:
    query: str = ''
    provider_type: str = ''
    readiness: str = ''
    page: int = 1
    per_page: int = 5


@dataclass(frozen=True, slots=True)
class BindingRegistryFilters:
    query: str = ''
    provider: str = ''
    status: str = ''
    page: int = 1
    per_page: int = 5


def build_integration_domain_page(
    domain_key: str,
    *,
    active_tab: str = 'registry',
    provider_filters: ProviderRegistryFilters | None = None,
    binding_filters: BindingRegistryFilters | None = None,
    include_capabilities: bool = True,
) -> dict[str, Any]:
    """Build one taxonomy-owned Integration domain page from canonical identities."""

    provider_filters = provider_filters or ProviderRegistryFilters()
    binding_filters = binding_filters or BindingRegistryFilters()
    domain = get_domain_definition(domain_key)
    normalized_tab = active_tab if active_tab in {'registry', 'bindings'} else 'registry'
    modules = tuple(module for module in registry.all() if module.domain_key == domain.key)
    instances = _load_domain_instances(modules)
    related_bindings = _load_related_bindings(
        domain.key,
        modules,
        include_details=normalized_tab == 'bindings',
    )
    consumer_bindings = [binding for binding in related_bindings if not _is_owner_asset_binding(binding)]

    provider_types = _provider_type_rows(modules, instances, consumer_bindings)
    capability_definitions = capability_definitions_for_domain(domain.key)
    capabilities = (
        _capability_rows(domain.key, modules, provider_types, consumer_bindings) if include_capabilities else []
    )
    stats, posture_status = _domain_stats(
        modules,
        instances,
        capability_types=len(capability_definitions),
        consumer_bindings=consumer_bindings,
    )

    provider_registry_rows: list[dict[str, Any]] = []
    binding_registry_rows: list[dict[str, Any]] = []
    provider_pagination = None
    binding_pagination = None
    provider_filter_options: list[dict[str, str]] = []
    provider_readiness_options: list[dict[str, str]] = []
    binding_provider_options: list[dict[str, str]] = []
    binding_status_options: list[dict[str, str]] = []

    if normalized_tab == 'registry':
        all_provider_rows = _provider_registry_rows(modules, instances, consumer_bindings)
        provider_filter_options = _provider_filter_options(all_provider_rows)
        provider_readiness_options = _status_filter_options(all_provider_rows, 'readiness')
        filtered_provider_rows = _filter_provider_rows(
            all_provider_rows,
            query=provider_filters.query,
            provider_type=provider_filters.provider_type,
            readiness=provider_filters.readiness,
        )
        provider_registry_rows, provider_pagination = paginate_sequence(
            filtered_provider_rows,
            page=provider_filters.page,
            per_page=provider_filters.per_page,
        )
        _resolve_provider_detail_urls(provider_registry_rows)
    else:
        all_binding_rows = _binding_registry_rows(
            consumer_bindings,
            identity_bindings=related_bindings,
            owner_instances=instances,
        )
        binding_provider_options = _binding_provider_filter_options(all_binding_rows)
        binding_status_options = _status_filter_options(all_binding_rows, 'validation_status')
        filtered_binding_rows = _filter_binding_rows(
            all_binding_rows,
            query=binding_filters.query,
            provider=binding_filters.provider,
            status=binding_filters.status,
        )
        binding_registry_rows, binding_pagination = paginate_sequence(
            filtered_binding_rows,
            page=binding_filters.page,
            per_page=binding_filters.per_page,
        )
        _resolve_binding_detail_urls(binding_registry_rows)

    return {
        'domain': domain,
        'providers': provider_types,
        'capabilities': capabilities,
        'provider_registry_rows': provider_registry_rows,
        'provider_registry_pagination': provider_pagination,
        'binding_registry_rows': binding_registry_rows,
        'binding_registry_pagination': binding_pagination,
        'active_tab': normalized_tab,
        'stats': stats,
        'posture_status': posture_status,
        'selected_provider_query': provider_filters.query,
        'selected_provider_type': provider_filters.provider_type,
        'selected_provider_readiness': provider_filters.readiness,
        'selected_binding_query': binding_filters.query,
        'selected_binding_provider': binding_filters.provider,
        'selected_binding_status': binding_filters.status,
        'provider_filter_options': provider_filter_options,
        'provider_readiness_options': provider_readiness_options,
        'binding_provider_options': binding_provider_options,
        'binding_status_options': binding_status_options,
        'provider_per_page': provider_filters.per_page,
        'binding_per_page': binding_filters.per_page,
    }


def _load_domain_instances(modules: tuple[IntegrationModule, ...]) -> list[IntegrationInstance]:
    provider_types = tuple(module.provider_type for module in modules)
    if not provider_types:
        return []
    return (
        IntegrationInstance.query.filter(IntegrationInstance.provider_type.in_(provider_types))
        .order_by(IntegrationInstance.provider_type.asc(), IntegrationInstance.name.asc())
        .all()
    )


def _load_related_bindings(
    domain_key: str,
    modules: tuple[IntegrationModule, ...],
    *,
    include_details: bool,
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

    query = IntegrationBinding.query.options(selectinload(IntegrationBinding.instance))
    if not include_details:
        query = query.options(
            load_only(
                IntegrationBinding.id,
                IntegrationBinding.integration_instance_id,
                IntegrationBinding.asset_type,
                IntegrationBinding.asset_key,
                IntegrationBinding.enabled,
            )
        )

    return (
        query.join(
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
    consumer_bindings: list[IntegrationBinding],
) -> list[dict[str, Any]]:
    instances_by_provider: dict[str, list[IntegrationInstance]] = {}
    for instance in instances:
        instances_by_provider.setdefault(instance.provider_type, []).append(instance)
    return [
        _provider_type_row(module, instances_by_provider.get(module.provider_type, []), consumer_bindings)
        for module in modules
    ]


def _provider_type_row(
    module: IntegrationModule,
    targets: list[IntegrationInstance],
    consumer_bindings: list[IntegrationBinding],
) -> dict[str, Any]:
    enabled_targets = _enabled_targets(targets)
    ready = sum(1 for item in enabled_targets if item.readiness_status == 'ready')
    attention = len(targets) - ready
    bindings = sum(_consumer_binding_count(item, consumer_bindings) for item in enabled_targets)
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
        'status': _readiness_posture(registered=len(targets), enabled=len(enabled_targets), ready=ready),
    }


def _provider_registry_rows(
    modules: tuple[IntegrationModule, ...],
    instances: list[IntegrationInstance],
    consumer_bindings: list[IntegrationBinding],
) -> list[dict[str, Any]]:
    module_by_provider = {module.provider_type: module for module in modules}
    rows: list[dict[str, Any]] = []
    for instance in instances:
        module = module_by_provider.get(instance.provider_type)
        if module is None:
            continue
        enabled_bindings = _consumer_binding_count(instance, consumer_bindings)
        readiness = _instance_readiness(instance)
        provider_label, provider_filter_key = _provider_source_identity(instance, module)
        rows.append(
            {
                'id': instance.id,
                'name': instance.name,
                'environment': _humanize(instance.environment, empty='Environment not specified'),
                'provider_label': provider_label,
                'provider_type': module.provider_type,
                'provider_filter_key': provider_filter_key,
                'provider_icon': module.icon,
                'capability_label': module.capability.label,
                'readiness': readiness,
                'health': _humanize(instance.health_status, empty='Not observed'),
                'enabled': bool(instance.enabled and instance.lifecycle_status == 'active'),
                'bindings': enabled_bindings,
                'last_checked': _format_timestamp(instance.last_checked_at),
                'detail_url': None,
                'workspace_endpoint': module.workspace_endpoint,
                '_instance': instance,
                'search_text': ' '.join(
                    filter(
                        None,
                        [
                            instance.name.lower(),
                            str(instance.environment or '').lower(),
                            provider_label.lower(),
                            module.capability.label.lower(),
                            readiness.lower(),
                            str(instance.health_status or '').lower(),
                        ],
                    )
                ),
            }
        )
    return rows


def _binding_registry_rows(
    bindings: list[IntegrationBinding],
    *,
    identity_bindings: list[IntegrationBinding] | None = None,
    owner_instances: list[IntegrationInstance] | None = None,
) -> list[dict[str, Any]]:
    asset_labels = _asset_identity_labels(
        identity_bindings or bindings,
        owner_instances=owner_instances or [],
    )
    rows: list[dict[str, Any]] = []
    for binding in bindings:
        instance = binding.instance
        try:
            module = registry.get(instance.provider_type)
        except IntegrationNotRegistered:
            continue
        asset_identity = (binding.asset_type, str(binding.asset_key))
        source_provider, source_provider_filter_key = _provider_source_identity(instance, module)
        routing_policy = (
            normalize_routing_policy(binding.routing_policy) if instance.provider_type == 'prometheus' else None
        )
        rows.append(
            {
                'id': binding.id,
                'consumer_label': asset_labels.get(asset_identity) or _humanize(binding.asset_type),
                'asset_type_label': _humanize(binding.asset_type),
                'asset_key': str(binding.asset_key),
                'source_name': instance.name,
                'source_provider': source_provider,
                'source_provider_type': module.provider_type,
                'source_provider_filter_key': source_provider_filter_key,
                'source_icon': module.icon,
                'role': _humanize(binding.binding_role, empty='Primary'),
                'priority': binding.priority,
                'routing_label': _routing_label(routing_policy),
                'profile': binding.validation_profile or 'Consumer Profile Pending',
                'selector': selector_summary(binding.selector_json, empty='Selector not configured'),
                'validation_status': _binding_status(binding),
                'validation_message': binding.validation_message or 'Binding validation has not reported detail.',
                'last_validated': _format_timestamp(binding.last_validated_at),
                'enabled': bool(binding.enabled),
                'detail_url': None,
                'workspace_endpoint': module.workspace_endpoint,
                '_source_instance': instance,
                'search_text': ' '.join(
                    filter(
                        None,
                        [
                            (asset_labels.get(asset_identity) or '').lower(),
                            str(binding.asset_type or '').lower(),
                            str(binding.asset_key or '').lower(),
                            instance.name.lower(),
                            source_provider.lower(),
                            str(binding.validation_profile or '').lower(),
                            selector_summary(binding.selector_json, empty='').lower(),
                            _binding_status(binding).lower(),
                        ],
                    )
                ),
            }
        )
    return rows


def _resolve_provider_detail_urls(rows: list[dict[str, Any]]) -> None:
    for row in rows:
        instance = row.pop('_instance', None)
        if instance is None:
            continue
        try:
            module = registry.get(instance.provider_type)
        except IntegrationNotRegistered:
            continue
        record = module.get_record_for_canonical(instance.id)
        if record is not None:
            row['detail_url'] = module.detail_url_for_record(record, section='').rstrip('#')


def _resolve_binding_detail_urls(rows: list[dict[str, Any]]) -> None:
    for row in rows:
        instance = row.pop('_source_instance', None)
        if instance is None:
            continue
        try:
            module = registry.get(instance.provider_type)
        except IntegrationNotRegistered:
            continue
        record = module.get_record_for_canonical(instance.id)
        if record is not None:
            row['detail_url'] = module.detail_url_for_record(record, section='').rstrip('#')


def _filter_provider_rows(
    rows: list[dict[str, Any]],
    *,
    query: str,
    provider_type: str,
    readiness: str,
) -> list[dict[str, Any]]:
    filtered = rows
    normalized_query = query.strip().lower()
    if normalized_query:
        filtered = [row for row in filtered if normalized_query in row['search_text']]
    if provider_type:
        filtered = [row for row in filtered if row['provider_filter_key'] == provider_type]
    if readiness:
        filtered = [row for row in filtered if row['readiness'] == readiness]
    return filtered


def _filter_binding_rows(
    rows: list[dict[str, Any]],
    *,
    query: str,
    provider: str,
    status: str,
) -> list[dict[str, Any]]:
    filtered = rows
    normalized_query = query.strip().lower()
    if normalized_query:
        filtered = [row for row in filtered if normalized_query in row['search_text']]
    if provider:
        filtered = [row for row in filtered if row['source_provider_filter_key'] == provider]
    if status:
        filtered = [row for row in filtered if row['validation_status'] == status]
    return filtered


def _provider_filter_options(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    labels = {
        str(row['provider_filter_key']): str(row['provider_label']) for row in rows if row.get('provider_filter_key')
    }
    return [{'value': value, 'label': labels[value]} for value in sorted(labels, key=lambda item: labels[item].lower())]


def _routing_label(routing_policy: dict[str, Any] | None) -> str | None:
    if routing_policy is None:
        return None
    horizon = str(routing_policy['query_horizon']).replace('_', ' ').title()
    return f'{horizon} · Weight {routing_policy["weight"]}'


def _provider_source_identity(instance: IntegrationInstance, module: IntegrationModule) -> tuple[str, str]:
    if instance.provider_type != 'prometheus':
        label = module.runtime_label or module.label
        return label, instance.provider_type
    metadata = instance.metadata_json or {}
    source_type = str(metadata.get('metrics_source_type') or 'prometheus').strip().lower()
    if source_type == 'thanos':
        return 'Thanos Query', 'prometheus:thanos'
    return 'Prometheus', 'prometheus:prometheus'


def _status_filter_options(rows: list[dict[str, Any]], key: str) -> list[dict[str, str]]:
    values = sorted({str(row.get(key) or '').strip() for row in rows if str(row.get(key) or '').strip()})
    return [{'value': value, 'label': _humanize(value)} for value in values]


def _binding_provider_filter_options(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    labels = {
        str(row['source_provider_filter_key']): str(row['source_provider'])
        for row in rows
        if row.get('source_provider_filter_key')
    }
    return [{'value': key, 'label': labels[key]} for key in sorted(labels, key=lambda item: labels[item].lower())]


def _is_owner_asset_binding(binding: IntegrationBinding) -> bool:
    """Return True for the provider attachment that owns the managed asset.

    Domain Bindings are a consumer-facing registry. Kubernetes→Cluster and
    MinIO→ObjectStorageSystem owner attachments remain internal ownership evidence
    and must not be presented or counted as consumer bindings.
    """
    owner_domain = domain_key_for_asset_type(binding.asset_type)
    if owner_domain is None:
        return False
    try:
        module = registry.get(binding.instance.provider_type)
    except IntegrationNotRegistered:
        return False
    return module.domain_key == owner_domain


def _consumer_binding_count(
    instance: IntegrationInstance,
    consumer_bindings: list[IntegrationBinding],
) -> int:
    metadata = instance.metadata_json or {}
    asset_type = str(metadata.get('asset_type') or '').strip()
    asset_key = str(metadata.get('asset_key') or '').strip()
    if asset_type and asset_key:
        return sum(
            1
            for binding in consumer_bindings
            if binding.enabled and binding.asset_type == asset_type and str(binding.asset_key) == asset_key
        )
    return sum(1 for binding in consumer_bindings if binding.enabled and binding.integration_instance_id == instance.id)


def _asset_identity_labels(
    bindings: list[IntegrationBinding],
    *,
    owner_instances: list[IntegrationInstance],
) -> dict[tuple[str, str], str]:
    labels: dict[tuple[str, str], str] = {}
    for instance in owner_instances:
        metadata = instance.metadata_json or {}
        asset_type = str(metadata.get('asset_type') or '').strip()
        asset_key = str(metadata.get('asset_key') or '').strip()
        if asset_type and asset_key:
            labels[(asset_type, asset_key)] = instance.name
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
                'asset_types': list(capability.asset_types),
                'provider_count': len(capability_modules),
                'provider_labels': [module.runtime_label or module.label for module in capability_modules],
                **counts,
                'bindings': relevant_bindings,
                'availability': 'available' if capability_modules else 'not_registered',
                'status': _readiness_posture(
                    registered=counts['registered'],
                    enabled=counts['enabled'],
                    ready=counts['ready'],
                ),
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
    *,
    capability_types: int,
    consumer_bindings: list[IntegrationBinding],
) -> tuple[dict[str, int], str]:
    enabled_targets = _enabled_targets(instances)
    ready_targets = sum(1 for item in enabled_targets if item.readiness_status == 'ready')
    attention_targets = len(instances) - ready_targets
    stats = {
        'provider_types': len(modules),
        'capability_types': capability_types,
        'registered_targets': len(instances),
        'enabled_targets': len(enabled_targets),
        'ready_targets': ready_targets,
        'attention_targets': attention_targets,
        'bindings': sum(1 for binding in consumer_bindings if binding.enabled),
    }
    return stats, _readiness_posture(
        registered=len(instances),
        enabled=len(enabled_targets),
        ready=ready_targets,
    )


def _enabled_targets(instances: Iterable[IntegrationInstance]) -> list[IntegrationInstance]:
    return [item for item in instances if item.enabled and item.lifecycle_status == 'active']


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


def _readiness_posture(*, registered: int, enabled: int, ready: int) -> str:
    if registered <= 0:
        return 'not_configured'
    if enabled <= 0:
        return 'attention'
    if ready == enabled:
        return 'ready'
    return 'attention'
