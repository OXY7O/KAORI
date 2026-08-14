from __future__ import annotations

from typing import Any

from app.integrations.registry import registry
from app.integrations.taxonomy import ordered_domain_definitions


def _endpoint_matches(endpoint: str, prefix: str) -> bool:
    normalized = str(prefix or '').strip()
    if not normalized:
        return False
    return endpoint == normalized or endpoint.startswith(normalized)


def integration_endpoint_owner(endpoint: str | None) -> dict[str, str] | None:
    """Resolve an Integration provider endpoint to its taxonomy owner."""

    current_endpoint = str(endpoint or '').strip()
    if not current_endpoint:
        return None
    for module in registry.all():
        prefixes = module.navigation_endpoint_prefixes or (module.workspace_endpoint,)
        if any(_endpoint_matches(current_endpoint, prefix) for prefix in prefixes):
            return {
                'domain_key': module.domain_key,
                'domain_label': module.domain.label,
                'provider_type': module.provider_type,
                'provider_label': module.runtime_label or module.label,
            }
    return None


def build_integration_navigation_context(endpoint: str | None) -> dict[str, Any]:
    """Build registry-driven Integration sidebar state without provider-name branching."""

    current_endpoint = str(endpoint or '').strip()
    domains = ordered_domain_definitions()
    active_domain_key: str | None = None

    for domain in domains:
        if current_endpoint == domain.workspace_endpoint:
            active_domain_key = domain.key
            break

    if active_domain_key is None:
        for module in registry.all():
            prefixes = module.navigation_endpoint_prefixes or (module.workspace_endpoint,)
            if any(_endpoint_matches(current_endpoint, prefix) for prefix in prefixes):
                active_domain_key = module.domain_key
                break

    overview_active = current_endpoint == 'integrations.overview'
    notification_channels_active = current_endpoint.startswith('notification_channels.')
    integrations_active = bool(
        overview_active
        or notification_channels_active
        or active_domain_key
        or current_endpoint.startswith('integrations.')
    )

    return {
        'is_active': integrations_active,
        'overview_active': overview_active,
        'active_domain_key': active_domain_key,
        'notification_channels_active': notification_channels_active,
        'domains': [
            {
                'key': domain.key,
                'label': domain.label,
                'icon': domain.icon,
                'workspace_endpoint': domain.workspace_endpoint,
                'active': active_domain_key == domain.key,
            }
            for domain in domains
        ],
    }
