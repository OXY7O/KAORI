from __future__ import annotations

from typing import Any

from sqlalchemy.orm import contains_eager

from app.cluster.constants import get_environment_label
from app.integrations.binding_selectors import selector_is_configured, selector_summary
from app.models.alertmanager import AlertmanagerInstance
from app.models.cluster import Cluster
from app.models.integration import IntegrationBinding, IntegrationInstance
from app.models.prometheus import PrometheusInstance

_PROVIDER_META = {
    'prometheus': {
        'key': 'prometheus',
        'label': 'Prometheus',
        'source_label': 'metrics source',
        'icon': 'chart-no-axes-combined',
        'bind_endpoint': 'integrations.bind_prometheus_source',
        'registry_endpoint': 'integrations.prometheus',
        'register_endpoint': 'prometheus.new_instance',
        'detail_endpoint': 'prometheus.instance_detail',
        'selector_label': 'Metrics identity',
        'selector_help': 'The selector is injected into PromQL so one shared source cannot mix metrics from different clusters.',
    },
    'alertmanager': {
        'key': 'alertmanager',
        'label': 'Alertmanager',
        'source_label': 'alert source',
        'icon': 'siren',
        'bind_endpoint': 'integrations.bind_alertmanager_source',
        'registry_endpoint': 'integrations.alertmanager',
        'register_endpoint': 'alertmanager.new_instance',
        'detail_endpoint': 'alertmanager.instance_detail',
        'selector_label': 'Alert identity',
        'selector_help': 'The selector is appended to Alertmanager alert and silence filters so one shared source remains isolated by cluster.',
    },
}


def provider_meta(provider_type: str) -> dict[str, str]:
    try:
        return dict(_PROVIDER_META[provider_type])
    except KeyError as exc:
        raise ValueError(f'Unsupported integration provider: {provider_type}.') from exc


def build_provider_coverage(
    provider_type: str,
    *,
    page: int = 1,
    per_page: int = 5,
    query: str = '',
    environment: str = '',
    status: str = '',
) -> dict[str, Any]:
    meta = provider_meta(provider_type)
    instances = _instances(provider_type)
    instance_by_canonical = {
        instance.integration_instance_id: instance
        for instance in instances
        if instance.integration_instance_id is not None
    }
    provider_bindings = (
        IntegrationBinding.query.join(IntegrationInstance)
        .filter(IntegrationInstance.provider_type == provider_type)
        .order_by(
            IntegrationBinding.asset_type.asc(),
            IntegrationBinding.asset_key.asc(),
            IntegrationBinding.priority.asc(),
            IntegrationBinding.id.asc(),
        )
        .all()
    )
    bindings_by_scope: dict[str, list[IntegrationBinding]] = {}
    sharing_counts: dict[int, int] = {}
    unscoped_counts: dict[int, int] = {}
    for binding in provider_bindings:
        if binding.asset_type == 'kubernetes_cluster':
            bindings_by_scope.setdefault(binding.asset_key, []).append(binding)
        if binding.enabled:
            sharing_counts[binding.integration_instance_id] = sharing_counts.get(binding.integration_instance_id, 0) + 1
            if not selector_is_configured(binding.selector_json):
                unscoped_counts[binding.integration_instance_id] = (
                    unscoped_counts.get(binding.integration_instance_id, 0) + 1
                )

    rows: list[dict[str, Any]] = []
    clusters = Cluster.query.order_by(Cluster.name.asc(), Cluster.id.asc()).all()
    for cluster in clusters:
        scope_bindings = bindings_by_scope.get(str(cluster.id), [])
        enabled_bindings = [binding for binding in scope_bindings if binding.enabled]
        enabled_bindings.sort(key=lambda item: (_role_rank(item.binding_role), item.priority, item.id))
        selected_binding = enabled_bindings[0] if enabled_bindings else None
        selected_source = (
            instance_by_canonical.get(selected_binding.integration_instance_id)
            if selected_binding is not None
            else None
        )
        shared = bool(
            selected_binding is not None and sharing_counts.get(selected_binding.integration_instance_id, 0) > 1
        )
        selector_configured = bool(
            selected_binding is not None and selector_is_configured(selected_binding.selector_json)
        )
        coverage_status, coverage_label, coverage_detail = _coverage_status(
            selected_binding=selected_binding,
            selected_source=selected_source,
            shared=shared,
            selector_configured=selector_configured,
        )
        rows.append(
            {
                'scope_type': 'kubernetes_cluster',
                'scope_key': str(cluster.id),
                'scope_name': cluster.name,
                'environment': get_environment_label(cluster.environment),
                'source': selected_source,
                'source_id': selected_source.id if selected_source is not None else None,
                'source_name': selected_source.name if selected_source is not None else None,
                'source_readiness': (
                    selected_source.readiness_status or 'validation_required'
                    if selected_source is not None
                    else 'not_configured'
                ),
                'binding': selected_binding,
                'binding_role': selected_binding.binding_role if selected_binding is not None else None,
                'binding_priority': selected_binding.priority if selected_binding is not None else None,
                'selector_summary': (
                    selector_summary(selected_binding.selector_json)
                    if selected_binding is not None
                    else 'Not configured'
                ),
                'selector_configured': selector_configured,
                'shared_source': shared,
                'coverage_status': coverage_status,
                'coverage_label': coverage_label,
                'coverage_detail': coverage_detail,
                'search_text': ' '.join(
                    filter(
                        None,
                        [
                            cluster.name.lower(),
                            str(cluster.id).lower(),
                            get_environment_label(cluster.environment).lower(),
                            (selected_source.name or '').lower() if selected_source is not None else '',
                            coverage_label.lower(),
                        ],
                    )
                ),
            }
        )

    all_rows = rows
    filtered_rows = all_rows
    normalized_query = query.strip().lower()
    if normalized_query:
        filtered_rows = [row for row in filtered_rows if normalized_query in row['search_text']]
    if environment:
        filtered_rows = [row for row in filtered_rows if row['environment'] == environment]
    if status:
        filtered_rows = [row for row in filtered_rows if row['coverage_status'] == status]

    page_rows, pagination = _paginate(filtered_rows, page=page, per_page=per_page)
    source_options = []
    blocked_readiness = {'blocked', 'unavailable', 'disabled', 'incompatible'}
    for instance in instances:
        if not instance.enabled:
            continue
        readiness = (instance.readiness_status or 'validation_required').lower()
        canonical_id = instance.integration_instance_id or -1
        unscoped_binding_count = unscoped_counts.get(canonical_id, 0)
        selectable = readiness not in blocked_readiness and unscoped_binding_count == 0
        source_options.append(
            {
                'id': instance.id,
                'name': instance.name,
                'readiness': readiness,
                'binding_count': sharing_counts.get(canonical_id, 0),
                'unscoped_binding_count': unscoped_binding_count,
                'endpoint_product': getattr(instance, 'endpoint_product', None) or meta['label'],
                'selectable': selectable,
                'selection_reason': (
                    'Available for binding; provider and binding validation still apply.'
                    if selectable
                    else (
                        'Configure and validate selectors on existing bindings before sharing this source.'
                        if unscoped_binding_count
                        else f'Provider readiness {readiness.replace("_", " ")} blocks new bindings.'
                    )
                ),
            }
        )

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
        'source_options': source_options,
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
    provider_type: str,
    *,
    scope_key: str,
    submitted: dict[str, Any] | None = None,
    operation_feedback: dict[str, Any] | None = None,
) -> dict[str, Any]:
    meta = provider_meta(provider_type)
    cluster = Cluster.query.filter_by(id=scope_key).first()
    instances = _instances(provider_type)
    cluster_position = Cluster.query.order_by(Cluster.name.asc(), Cluster.id.asc()).with_entities(Cluster.id).all()
    position = next((index for index, row in enumerate(cluster_position) if str(row[0]) == str(scope_key)), 0)
    coverage = build_provider_coverage(provider_type, page=(position // 50) + 1, per_page=50)
    scope_row = next(
        (row for row in coverage['coverage_rows'] if row['scope_key'] == str(scope_key)),
        None,
    )
    selected_source_id = str((submitted or {}).get('source_id') or '')
    selected_source = next(
        (instance for instance in instances if str(instance.id) == selected_source_id),
        None,
    )
    return {
        'provider': meta,
        'provider_type': provider_type,
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
    provider_types: tuple[str, ...] | list[str],
    *,
    scope_type: str,
    scope_keys: tuple[str, ...] | list[str],
) -> dict[tuple[str, str], tuple[Any | None, IntegrationBinding | None]]:
    """Bulk-load preferred provider bindings for multiple scopes.

    Registry pages use this helper to avoid repeating one binding query and one
    provider-registry query for every Kubernetes connection row.
    """
    normalized_providers = tuple(dict.fromkeys(str(value) for value in provider_types if value))
    normalized_scope_keys = tuple(dict.fromkeys(str(value) for value in scope_keys if value))
    if not normalized_providers or not normalized_scope_keys:
        return {}

    bindings = (
        IntegrationBinding.query.join(IntegrationInstance)
        .options(contains_eager(IntegrationBinding.instance))
        .filter(
            IntegrationInstance.provider_type.in_(normalized_providers),
            IntegrationBinding.asset_type == scope_type,
            IntegrationBinding.asset_key.in_(normalized_scope_keys),
            IntegrationBinding.enabled.is_(True),
        )
        .order_by(
            IntegrationBinding.asset_key.asc(),
            IntegrationInstance.provider_type.asc(),
            IntegrationBinding.priority.asc(),
            IntegrationBinding.id.asc(),
        )
        .all()
    )
    candidates: dict[tuple[str, str], list[IntegrationBinding]] = {}
    provider_by_instance: dict[int, str] = {}
    for binding in bindings:
        provider = binding.instance.provider_type
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
    provider_type: str, *, scope_type: str, scope_key: str
) -> tuple[Any | None, IntegrationBinding | None]:
    """Return the preferred persisted source binding without performing live resolution.

    This is used by inventory and navigation surfaces where a blocked or not-yet-
    validated binding must still remain visible and reviewable.
    """
    bindings = (
        IntegrationBinding.query.join(IntegrationInstance)
        .filter(
            IntegrationInstance.provider_type == provider_type,
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
            for instance in _instances(provider_type)
            if instance.integration_instance_id == binding.integration_instance_id
        ),
        None,
    )
    return source, binding


def _instances(provider_type: str) -> list[Any]:
    if provider_type == 'prometheus':
        return (
            PrometheusInstance.query.join(PrometheusInstance.integration_instance)
            .order_by(IntegrationInstance.name.asc())
            .all()
        )
    if provider_type == 'alertmanager':
        return (
            AlertmanagerInstance.query.join(AlertmanagerInstance.integration_instance)
            .order_by(IntegrationInstance.name.asc())
            .all()
        )
    raise ValueError(f'Unsupported integration provider: {provider_type}.')


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
