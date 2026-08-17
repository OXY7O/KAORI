from __future__ import annotations

from typing import Any

from sqlalchemy.orm import contains_eager

from app.cluster.constants import get_environment_label
from app.integrations.binding_selectors import selector_is_configured, selector_summary
from app.integrations.consumer_assets import registered_consumer_asset_definitions
from app.models.cluster import Cluster
from app.models.integration import IntegrationBinding, IntegrationInstance

_PROVIDER_META = {
    'metrics_source': {
        'key': 'metrics_source',
        'label': 'Metrics',
        'source_label': 'metrics source',
        'icon': 'chart-no-axes-combined',
        'bind_endpoint': 'integrations.bind_metrics_source',
        'registry_endpoint': 'integrations.metrics_sources',
        'register_endpoint': 'integrations.select_metrics_source_provider',
        'detail_endpoint': 'metrics.instance_detail',
        'selector_label': 'Metrics identity',
        'selector_help': 'The selector isolates one managed asset inside a shared metrics source.',
    },
    'alert_source': {
        'key': 'alert_source',
        'label': 'Alert Sources',
        'source_label': 'alert source',
        'icon': 'siren',
        'bind_endpoint': 'integrations.bind_alertmanager_source',
        'registry_endpoint': 'integrations.alertmanager',
        'register_endpoint': 'alertmanager.new_instance',
        'detail_endpoint': 'alertmanager.instance_detail',
        'selector_label': 'Alert identity',
        'selector_help': 'The selector isolates one managed asset inside a shared alert source.',
    },
}


def provider_meta(integration_type: str) -> dict[str, str]:
    try:
        return dict(_PROVIDER_META[integration_type])
    except KeyError as exc:
        raise ValueError(f'Unsupported integration provider: {integration_type}.') from exc


def _provider_binding_indexes(
    integration_type: str,
) -> tuple[list[IntegrationBinding], dict[tuple[str, str], list[IntegrationBinding]], dict[int, int], dict[int, int]]:
    bindings = (
        IntegrationBinding.query.join(IntegrationInstance)
        .filter(IntegrationInstance.integration_type == integration_type)
        .order_by(
            IntegrationBinding.asset_type.asc(),
            IntegrationBinding.asset_key.asc(),
            IntegrationBinding.priority.asc(),
            IntegrationBinding.id.asc(),
        )
        .all()
    )
    by_asset: dict[tuple[str, str], list[IntegrationBinding]] = {}
    sharing_counts: dict[int, int] = {}
    unscoped_counts: dict[int, int] = {}
    for binding in bindings:
        if binding.asset_type in {definition.asset_type for definition in registered_consumer_asset_definitions()}:
            by_asset.setdefault((binding.asset_type, binding.asset_key), []).append(binding)
        if not binding.enabled:
            continue
        sharing_counts[binding.integration_instance_id] = sharing_counts.get(binding.integration_instance_id, 0) + 1
        if not selector_is_configured(binding.selector_json):
            unscoped_counts[binding.integration_instance_id] = (
                unscoped_counts.get(binding.integration_instance_id, 0) + 1
            )
    return bindings, by_asset, sharing_counts, unscoped_counts


def _managed_asset_scopes() -> list[dict[str, Any]]:
    scopes: list[dict[str, Any]] = []
    for definition in registered_consumer_asset_definitions():
        assets = definition.model.query.order_by(definition.model.name.asc(), definition.model.id.asc()).all()
        for asset in assets:
            scopes.append(
                {
                    'scope_type': definition.asset_type,
                    'scope_key': str(asset.id),
                    'scope_name': str(asset.name),
                    'environment': get_environment_label(str(getattr(asset, 'environment', '') or '')),
                    'search_hint': f'{definition.label.lower()} {definition.asset_type.replace("_", " ")}',
                }
            )
    return scopes


def _coverage_row(
    scope: dict[str, Any],
    *,
    bindings_by_asset: dict[tuple[str, str], list[IntegrationBinding]],
    instance_by_canonical: dict[int, Any],
    sharing_counts: dict[int, int],
) -> dict[str, Any]:
    scope_bindings = bindings_by_asset.get((scope['scope_type'], scope['scope_key']), [])
    enabled = sorted(
        (binding for binding in scope_bindings if binding.enabled),
        key=lambda item: (_role_rank(item.binding_role), item.priority, item.id),
    )
    binding = enabled[0] if enabled else None
    source = instance_by_canonical.get(binding.integration_instance_id) if binding is not None else None
    shared = bool(binding is not None and sharing_counts.get(binding.integration_instance_id, 0) > 1)
    selector_configured = bool(binding is not None and selector_is_configured(binding.selector_json))
    status, label, detail = _coverage_status(
        selected_binding=binding,
        selected_source=source,
        shared=shared,
        selector_configured=selector_configured,
    )
    source_name = source.name if source is not None else None
    return {
        **scope,
        'source': source,
        'source_id': source.integration_instance_id if source is not None else None,
        'source_record_id': source.id if source is not None else None,
        'source_name': source_name,
        'source_readiness': (source.readiness_status or 'validation_required')
        if source is not None
        else 'not_configured',
        'binding': binding,
        'binding_role': binding.binding_role if binding is not None else None,
        'binding_priority': binding.priority if binding is not None else None,
        'selector_summary': selector_summary(binding.selector_json) if binding is not None else 'Not configured',
        'selector_configured': selector_configured,
        'shared_source': shared,
        'coverage_status': status,
        'coverage_label': label,
        'coverage_detail': detail,
        'search_text': ' '.join(
            filter(
                None,
                [
                    scope['scope_name'].lower(),
                    scope['scope_key'].lower(),
                    scope['environment'].lower(),
                    (source_name or '').lower(),
                    label.lower(),
                    scope['search_hint'],
                ],
            )
        ),
    }


def _coverage_source_options(
    instances: list[Any],
    *,
    meta: dict[str, str],
    sharing_counts: dict[int, int],
    unscoped_counts: dict[int, int],
) -> list[dict[str, Any]]:
    blocked = {'blocked', 'unavailable', 'disabled', 'incompatible'}
    options: list[dict[str, Any]] = []
    for instance in instances:
        if not instance.enabled:
            continue
        readiness = (instance.readiness_status or 'validation_required').lower()
        canonical_id = instance.integration_instance_id or -1
        unscoped = unscoped_counts.get(canonical_id, 0)
        selectable = readiness not in blocked and unscoped == 0
        options.append(
            {
                'id': instance.integration_instance_id,
                'record_id': instance.id,
                'name': instance.name,
                'readiness': readiness,
                'binding_count': sharing_counts.get(canonical_id, 0),
                'unscoped_binding_count': unscoped,
                'endpoint_product': getattr(instance, 'endpoint_product', None) or meta['label'],
                'selectable': selectable,
                'selection_reason': (
                    'Available for binding; provider and binding validation still apply.'
                    if selectable
                    else (
                        'Configure and validate selectors on existing bindings before sharing this source.'
                        if unscoped
                        else f'Provider readiness {readiness.replace("_", " ")} blocks new bindings.'
                    )
                ),
            }
        )
    return options


def build_provider_coverage(
    integration_type: str,
    *,
    page: int = 1,
    per_page: int = 5,
    query: str = '',
    environment: str = '',
    status: str = '',
) -> dict[str, Any]:
    meta = provider_meta(integration_type)
    instances = _instances(integration_type)
    instance_by_canonical = {
        instance.integration_instance_id: instance
        for instance in instances
        if instance.integration_instance_id is not None
    }
    _, bindings_by_asset, sharing_counts, unscoped_counts = _provider_binding_indexes(integration_type)
    all_rows = [
        _coverage_row(
            scope,
            bindings_by_asset=bindings_by_asset,
            instance_by_canonical=instance_by_canonical,
            sharing_counts=sharing_counts,
        )
        for scope in _managed_asset_scopes()
    ]
    filtered_rows = all_rows
    normalized_query = query.strip().lower()
    if normalized_query:
        filtered_rows = [row for row in filtered_rows if normalized_query in row['search_text']]
    if environment:
        filtered_rows = [row for row in filtered_rows if row['environment'] == environment]
    if status:
        filtered_rows = [row for row in filtered_rows if row['coverage_status'] == status]

    page_rows, pagination = _paginate(filtered_rows, page=page, per_page=per_page)
    return {
        'provider': meta,
        'coverage_rows': page_rows,
        'coverage_pagination': pagination,
        'selected_coverage_query': query,
        'selected_coverage_environment': environment,
        'selected_coverage_status': status,
        'coverage_environment_options': sorted({row['environment'] for row in all_rows}),
        'coverage_status_options': [
            option
            for option in ('ready', 'degraded', 'validation_required', 'blocked', 'uncovered')
            if any(row['coverage_status'] == option for row in all_rows)
        ],
        'source_options': _coverage_source_options(
            instances, meta=meta, sharing_counts=sharing_counts, unscoped_counts=unscoped_counts
        ),
        'coverage_stats': {
            'total': len(all_rows),
            'ready': sum(1 for row in all_rows if row['coverage_status'] == 'ready'),
            'attention': sum(
                1 for row in all_rows if row['coverage_status'] in {'degraded', 'validation_required', 'blocked'}
            ),
            'uncovered': sum(1 for row in all_rows if row['coverage_status'] == 'uncovered'),
        },
    }


def build_binding_workspace(
    integration_type: str,
    *,
    scope_key: str,
    submitted: dict[str, Any] | None = None,
    operation_feedback: dict[str, Any] | None = None,
) -> dict[str, Any]:
    meta = provider_meta(integration_type)
    cluster = Cluster.query.filter_by(id=scope_key).first()
    instances = _instances(integration_type)
    cluster_position = Cluster.query.order_by(Cluster.name.asc(), Cluster.id.asc()).with_entities(Cluster.id).all()
    position = next((index for index, row in enumerate(cluster_position) if str(row[0]) == str(scope_key)), 0)
    coverage = build_provider_coverage(integration_type, page=(position // 50) + 1, per_page=50)
    scope_row = next(
        (row for row in coverage['coverage_rows'] if row['scope_key'] == str(scope_key)),
        None,
    )
    selected_source_id = str((submitted or {}).get('source_id') or '')
    selected_source = next(
        (instance for instance in instances if str(instance.integration_instance_id) == selected_source_id),
        None,
    )
    return {
        'provider': meta,
        'integration_type': integration_type,
        'cluster': cluster,
        'scope_row': scope_row,
        'source_options': coverage['source_options'],
        'selectable_source_count': sum(1 for item in coverage['source_options'] if item['selectable']),
        'selected_source': selected_source,
        'submitted': submitted or {},
        'default_selector_label': str((submitted or {}).get('selector_label') or 'cluster'),
        'default_selector_value': str((submitted or {}).get('selector_value') or (cluster.name if cluster else '')),
        'operation_feedback': operation_feedback,
    }


def bound_sources_for_scopes(
    integration_types: tuple[str, ...] | list[str],
    *,
    scope_type: str,
    scope_keys: tuple[str, ...] | list[str],
) -> dict[tuple[str, str], tuple[Any | None, IntegrationBinding | None]]:
    """Bulk-load preferred provider bindings for multiple scopes.

    Registry pages use this helper to avoid repeating one binding query and one
    provider-registry query for every Kubernetes connection row.
    """
    normalized_providers = tuple(dict.fromkeys(str(value) for value in integration_types if value))
    normalized_scope_keys = tuple(dict.fromkeys(str(value) for value in scope_keys if value))
    if not normalized_providers or not normalized_scope_keys:
        return {}

    bindings = (
        IntegrationBinding.query.join(IntegrationInstance)
        .options(contains_eager(IntegrationBinding.instance))
        .filter(
            IntegrationInstance.integration_type.in_(normalized_providers),
            IntegrationBinding.asset_type == scope_type,
            IntegrationBinding.asset_key.in_(normalized_scope_keys),
            IntegrationBinding.enabled.is_(True),
        )
        .order_by(
            IntegrationBinding.asset_key.asc(),
            IntegrationInstance.integration_type.asc(),
            IntegrationBinding.priority.asc(),
            IntegrationBinding.id.asc(),
        )
        .all()
    )
    candidates: dict[tuple[str, str], list[IntegrationBinding]] = {}
    provider_by_instance: dict[int, str] = {}
    for binding in bindings:
        provider = binding.instance.integration_type
        provider_by_instance[binding.integration_instance_id] = provider
        candidates.setdefault((provider, str(binding.asset_key)), []).append(binding)

    source_maps = {
        provider: {
            instance.integration_instance_id: instance
            for instance in _instances(provider)
            if instance.integration_instance_id is not None
        }
        for provider in normalized_providers
    }
    resolved: dict[tuple[str, str], tuple[Any | None, IntegrationBinding | None]] = {}
    for key, options in candidates.items():
        options.sort(key=lambda item: (_role_rank(item.binding_role), item.priority, item.id))
        binding = options[0]
        provider = provider_by_instance.get(binding.integration_instance_id, key[0])
        source = source_maps.get(provider, {}).get(binding.integration_instance_id)
        resolved[key] = (source, binding)

    for provider in normalized_providers:
        for scope_key in normalized_scope_keys:
            resolved.setdefault((provider, scope_key), (None, None))
    return resolved


def bound_source_for_scope(
    integration_type: str, *, scope_type: str, scope_key: str
) -> tuple[Any | None, IntegrationBinding | None]:
    """Return the preferred persisted source binding without performing live resolution.

    This is used by inventory and navigation surfaces where a blocked or not-yet-
    validated binding must still remain visible and reviewable.
    """
    bindings = (
        IntegrationBinding.query.join(IntegrationInstance)
        .filter(
            IntegrationInstance.integration_type == integration_type,
            IntegrationBinding.asset_type == scope_type,
            IntegrationBinding.asset_key == str(scope_key),
            IntegrationBinding.enabled.is_(True),
        )
        .order_by(
            IntegrationBinding.priority.asc(),
            IntegrationBinding.id.asc(),
        )
        .all()
    )
    bindings.sort(key=lambda item: (_role_rank(item.binding_role), item.priority, item.id))
    binding = bindings[0] if bindings else None
    if binding is None:
        return None, None
    source = next(
        (
            instance
            for instance in _instances(integration_type)
            if instance.integration_instance_id == binding.integration_instance_id
        ),
        None,
    )
    return source, binding


def _instances(integration_type: str) -> list[Any]:
    from app.integrations.registry import get_integration

    module = get_integration(integration_type)
    identities = (
        IntegrationInstance.query.filter_by(integration_type=integration_type)
        .order_by(IntegrationInstance.name.asc(), IntegrationInstance.id.asc())
        .all()
    )
    records: list[Any] = []
    for identity in identities:
        record = module.get_record_for_canonical(identity.id)
        if record is not None:
            records.append(record)
    return records


def _coverage_status(
    *,
    selected_binding: IntegrationBinding | None,
    selected_source: Any | None,
    shared: bool,
    selector_configured: bool,
) -> tuple[str, str, str]:
    if selected_binding is None:
        return 'uncovered', 'Not Bound', 'Select an existing registered source for this operational scope.'
    if selected_source is None:
        return 'blocked', 'Source Missing', 'The binding points to a provider record that no longer exists.'
    if shared and not selector_configured:
        return (
            'blocked',
            'Isolation Required',
            'This shared source needs a selector before it can safely serve multiple scopes.',
        )
    # Binding validity is explicit state, not a timestamp comparison. Provider
    # runtime/full-validation timestamps can move without changing the binding
    # selector or scope contract. Configuration and selector update paths
    # explicitly invalidate affected bindings.
    binding_status = (selected_binding.validation_status or 'validation_required').lower()
    if binding_status == 'blocked':
        return (
            'blocked',
            'Binding Blocked',
            selected_binding.validation_message or 'The source binding failed scope validation.',
        )
    if binding_status == 'degraded':
        return (
            'degraded',
            'Binding Degraded',
            selected_binding.validation_message
            or 'The selector was accepted but did not return expected scope evidence.',
        )
    if binding_status == 'validation_required':
        return (
            'validation_required',
            'Binding Validation Required',
            selected_binding.validation_message or 'Validate the scope selector before operational use.',
        )
    readiness = (selected_source.readiness_status or 'validation_required').lower()
    if readiness == 'ready':
        return 'ready', 'Ready', 'Source readiness, binding, and scope isolation are available.'
    if readiness == 'degraded':
        return 'degraded', 'Degraded', 'The source is bound but its validation posture needs attention.'
    if readiness == 'blocked':
        return 'blocked', 'Blocked', 'The source is bound but provider readiness currently blocks operational use.'
    return (
        'validation_required',
        'Validation Required',
        'The source is bound; complete provider and binding validation before use.',
    )


def _role_rank(role: str) -> int:
    return {'primary': 0, 'secondary': 1, 'fallback': 2}.get(role, 9)


def _paginate(rows: list[dict[str, Any]], *, page: int, per_page: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    allowed = [5, 10, 25, 50]
    if per_page not in allowed:
        per_page = 5
    page = max(page, 1)
    total_items = len(rows)
    total_pages = max((total_items + per_page - 1) // per_page, 1)
    page = min(page, total_pages)
    start = (page - 1) * per_page
    end = start + per_page
    return rows[start:end], {
        'page': page,
        'per_page': per_page,
        'total_items': total_items,
        'total_pages': total_pages,
        'start_item': start + 1 if total_items else 0,
        'end_item': min(end, total_items),
        'has_prev': page > 1,
        'has_next': page < total_pages,
        'prev_page': page - 1,
        'next_page': page + 1,
        'allowed_per_page': allowed,
    }
