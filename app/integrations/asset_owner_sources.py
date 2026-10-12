from __future__ import annotations

from typing import Any

from app.common.pagination import paginate_query
from app.integrations.kernel.registry import get_integration
from app.integrations.observability.metrics_source.providers import provider_definition
from app.integrations.readiness import resolve_binding_operational_status
from app.models.integration import IntegrationBinding, IntegrationInstance

_OBSERVABILITY_PROVIDER_TYPES = ('metrics_source', 'alert_source')


def _bound_observability_source_query(*, asset_type: str, asset_key: str):
    return (
        IntegrationBinding.query.join(IntegrationInstance)
        .filter(
            IntegrationBinding.asset_type == asset_type,
            IntegrationBinding.asset_key == str(asset_key),
            IntegrationBinding.enabled.is_(True),
            IntegrationInstance.integration_type.in_(_OBSERVABILITY_PROVIDER_TYPES),
        )
        .order_by(
            IntegrationInstance.integration_type.asc(),
            IntegrationBinding.priority.asc(),
            IntegrationBinding.id.asc(),
        )
    )


def build_bound_observability_source_rows(*, asset_type: str, asset_key: str) -> list[dict[str, Any]]:
    """Project source-owned bindings without changing existing caller behavior."""
    return _project_bound_source_rows(
        _bound_observability_source_query(asset_type=asset_type, asset_key=asset_key).all()
    )


def paginate_bound_observability_source_rows(
    *, asset_type: str, asset_key: str, page: int = 1, per_page: int = 5,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Bound SQL rows before resolving provider-specific source records."""
    bindings, pagination = paginate_query(
        _bound_observability_source_query(asset_type=asset_type, asset_key=asset_key),
        page=page,
        per_page=per_page,
    )
    return _project_bound_source_rows(bindings), pagination


def _project_bound_source_rows(bindings: list[IntegrationBinding]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for binding in bindings:
        canonical = binding.instance
        module = get_integration(canonical.integration_type)
        source = module.get_record_for_canonical(canonical.id)
        provider_label, provider_icon = _source_presentation(canonical, module.label, module.icon, source)
        source_readiness = getattr(source, 'readiness_status', None) or 'validation_required'
        binding_validation = binding.validation_status or 'validation_required'
        effective = resolve_binding_operational_status(
            source_readiness=source_readiness,
            binding_validation=binding_validation,
            source_enabled=bool(getattr(source, 'enabled', True)),
            binding_enabled=bool(binding.enabled),
        )
        rows.append(
            {
                'binding': binding,
                'provider': provider_label,
                'integration_type': canonical.integration_type,
                'icon': provider_icon,
                'name': getattr(source, 'name', None) or canonical.name,
                'role': binding.binding_role,
                'profile_label': binding.validation_profile or 'Validation Required',
                'source_readiness': source_readiness,
                'binding_validation': binding_validation,
                'effective_status': effective['status'],
                'effective_label': effective['label'],
            }
        )
    return rows


def _source_presentation(
    canonical: IntegrationInstance,
    provider_label: str,
    provider_icon: str,
    source: object | None,
) -> tuple[str, str]:
    if canonical.integration_type != 'metrics_source':
        return provider_label, provider_icon
    provider_key = str(getattr(source, 'provider_key', None) or canonical.provider_key or '').strip().lower()
    if not provider_key:
        return 'Metrics Source', provider_icon
    definition = provider_definition(provider_key)
    return definition.label, definition.icon
