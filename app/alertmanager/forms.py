from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

SUPPORTED_AUTH_TYPES = {'none', 'basic', 'bearer'}
SUPPORTED_DEPLOYMENT_TYPES = {
    'external_managed',
    'standalone',
    'shared',
    'cluster_managed',
}
SUPPORTED_BINDING_ROLES = {'primary', 'secondary', 'fallback'}
SUPPORTED_SCOPE_TYPES = {
    'kubernetes_cluster',
    'server',
    'server_group',
    'hci_environment',
    'storage_service',
    'object_storage_system',
    'global',
}


@dataclass(frozen=True, slots=True)
class AlertmanagerInstanceForm:
    name: str
    description: str | None
    deployment_type: str
    endpoint: str
    auth_type: str
    username: str | None
    password: str | None
    bearer_token: str | None
    timeout: int
    verify_ssl: bool
    enabled: bool


@dataclass(frozen=True, slots=True)
class AlertmanagerBindingForm:
    scope_type: str
    scope_key: str
    binding_role: str
    priority: int
    enabled: bool
    selector_label: str | None = None
    selector_value: str | None = None
    selector_operator: str = '='


def parse_alertmanager_instance_form(form_data: Mapping[str, Any]) -> AlertmanagerInstanceForm:
    auth_type = str(form_data.get('auth_type', 'none')).strip().lower()
    if auth_type not in SUPPORTED_AUTH_TYPES:
        auth_type = 'none'

    deployment_type = str(form_data.get('deployment_type', 'external_managed')).strip().lower()
    if deployment_type not in SUPPORTED_DEPLOYMENT_TYPES:
        deployment_type = 'external_managed'

    return AlertmanagerInstanceForm(
        name=str(form_data.get('name', '')).strip(),
        description=clean_optional_value(form_data.get('description')),
        deployment_type=deployment_type,
        endpoint=normalize_endpoint(str(form_data.get('endpoint', '')).strip()),
        auth_type=auth_type,
        username=clean_optional_value(form_data.get('username')),
        password=clean_optional_value(form_data.get('password')),
        bearer_token=clean_optional_value(form_data.get('bearer_token')),
        timeout=parse_timeout(form_data.get('timeout', 5)),
        verify_ssl=parse_checkbox(form_data.get('verify_ssl')),
        enabled=parse_checkbox(form_data.get('enabled', '1')),
    )


def parse_alertmanager_binding_form(form_data: Mapping[str, Any]) -> AlertmanagerBindingForm:
    scope_type = str(form_data.get('scope_type', '')).strip().lower()
    if scope_type not in SUPPORTED_SCOPE_TYPES:
        scope_type = 'kubernetes_cluster'

    binding_role = str(form_data.get('binding_role', 'primary')).strip().lower()
    if binding_role not in SUPPORTED_BINDING_ROLES:
        binding_role = 'primary'

    if scope_type == 'kubernetes_cluster':
        scope_key = str(form_data.get('cluster_scope_key') or form_data.get('scope_key') or '').strip()
    elif scope_type == 'object_storage_system':
        scope_key = str(form_data.get('object_storage_scope_key') or form_data.get('scope_key') or '').strip()
    else:
        scope_key = str(form_data.get('generic_scope_key') or form_data.get('scope_key') or '').strip()

    return AlertmanagerBindingForm(
        scope_type=scope_type,
        scope_key=scope_key,
        binding_role=binding_role,
        priority=parse_priority(form_data.get('priority', 100)),
        enabled=parse_checkbox(form_data.get('enabled', '1')),
        selector_label=clean_optional_value(form_data.get('selector_label')),
        selector_value=clean_optional_value(form_data.get('selector_value')),
        selector_operator=str(form_data.get('selector_operator', '=')).strip() or '=',
    )


def normalize_endpoint(value: str) -> str:
    endpoint = value.rstrip('/')
    if not endpoint:
        return ''
    if not endpoint.startswith(('http://', 'https://')):
        return f'http://{endpoint}'
    return endpoint


def validate_endpoint(endpoint: str) -> None:
    if not endpoint:
        raise ValueError('Alertmanager endpoint is required.')
    parsed = urlsplit(endpoint)
    if parsed.scheme not in {'http', 'https'} or not parsed.hostname:
        raise ValueError('Alertmanager endpoint must be a valid HTTP or HTTPS URL.')
    if parsed.username or parsed.password:
        raise ValueError('Do not embed credentials in the Alertmanager endpoint URL.')
    if parsed.query or parsed.fragment:
        raise ValueError('Alertmanager endpoint must not include query parameters or a fragment.')
    if parsed.path.rstrip('/').endswith('/api/v2'):
        raise ValueError('Use the Alertmanager base URL, not an /api/v2 endpoint path.')


def clean_optional_value(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def parse_timeout(value: Any) -> int:
    try:
        timeout = int(value)
    except (TypeError, ValueError):
        return 5
    return min(max(timeout, 1), 30)


def parse_priority(value: Any) -> int:
    try:
        priority = int(value)
    except (TypeError, ValueError):
        return 100
    return min(max(priority, 1), 1000)


def parse_checkbox(value: Any) -> bool:
    return str(value).lower() in {'1', 'true', 'on', 'yes'}
