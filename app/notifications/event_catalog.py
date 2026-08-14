from __future__ import annotations

from typing import Any

CATEGORY_LABELS = {
    'configmap_management': 'ConfigMap Management',
    'tls_certificate': 'TLS Certificate',
    'secret_management': 'Secret Management',
    'integrations': 'Integrations',
    'platform_operations': 'Platform Operations',
    'access': 'Access',
    'settings': 'Settings',
    'operations': 'Operations',
}

_EVENT_TOKEN_OVERRIDES = {
    'api': 'API',
    'configmap': 'ConfigMap',
    'csv': 'CSV',
    'id': 'ID',
    'jit': 'JIT',
    'kaori': 'KAORI',
    'k8s': 'Kubernetes',
    'ldap': 'LDAP',
    'oidc': 'OIDC',
    'rbac': 'RBAC',
    's3': 'S3',
    'saml': 'SAML',
    'sso': 'SSO',
    'tls': 'TLS',
    'url': 'URL',
}


def _display_event_label(value: str) -> str:
    words = []
    for token in value.replace('-', ' ').split():
        words.append(_EVENT_TOKEN_OVERRIDES.get(token.lower(), token[:1].upper() + token[1:].lower()))
    return ' '.join(words)


CATEGORY_ICONS = {
    'configmap_management': 'file-cog',
    'tls_certificate': 'shield-check',
    'secret_management': 'key-round',
    'integrations': 'plug-zap',
    'platform_operations': 'workflow',
    'access': 'users-round',
    'settings': 'settings-2',
    'operations': 'history',
}


def event_label(event_type: str) -> str:
    """Return a human-readable label while keeping the stored event key unchanged."""
    normalized = event_type.strip()
    prefix = 'operational_activity_'
    if normalized.startswith(prefix):
        normalized = normalized[len(prefix) :]
    return _display_event_label(normalized.replace('_', ' ').strip()) or 'Activity'


def event_category_key(event_type: str) -> str:
    """Map persisted event keys into the canonical Notification Center categories."""

    normalized = (event_type or '').strip().lower()

    if normalized.startswith('kubernetes_configmap_'):
        return 'configmap_management'
    if normalized.startswith('governance_tls_') or normalized.startswith('kubernetes_tls_secret_'):
        return 'tls_certificate'
    if normalized.startswith(
        (
            'kubernetes_secret_reveal_cluster_readiness_',
            'kubernetes_secret_reveal_namespace_policy_',
            'data_lifecycle_',
            'job_',
            'report_',
            'generated_report_',
            'generated_reports_',
        )
    ):
        return 'platform_operations'
    if normalized.startswith('kubernetes_secret_'):
        return 'secret_management'
    if (
        normalized.startswith(
            (
                'prometheus_',
                'alertmanager_',
                'cluster_',
                'kubernetes_capability_',
                'kubernetes_runtime_',
                'integration_',
            )
        )
        or normalized == 'kubernetes_inventory_sync'
    ):
        return 'integrations'
    if (
        normalized.startswith(('rbac_', 'identity_provider_', 'external_identity_', 'user_'))
        or normalized == 'authentication'
    ):
        if normalized == 'user_preference':
            return 'settings'
        return 'access'
    if normalized == 'account_security' or normalized.startswith('settings_'):
        return 'settings'
    return 'operations'


def event_category(event_type: str) -> dict[str, str]:
    key = event_category_key(event_type)
    return {
        'key': key,
        'label': CATEGORY_LABELS[key],
        'icon': CATEGORY_ICONS[key],
    }


def _string_metadata(
    metadata: dict[str, Any],
    *keys: str,
) -> str | None:
    for key in keys:
        value = metadata.get(key)
        if value is None:
            continue

        normalized = str(value).strip()
        if normalized:
            return normalized

    return None


def build_event_context(
    event_type: str,
    metadata: dict[str, Any],
    title: str,
) -> dict[str, Any]:
    cluster_name = _string_metadata(metadata, 'cluster_name', 'submitted_name')
    environment = _string_metadata(metadata, 'environment', 'submitted_environment')
    endpoint = _string_metadata(metadata, 'endpoint', 'endpoint_host', 'server')
    instance_name = _string_metadata(metadata, 'instance_name', 'submitted_name')
    task_id = _string_metadata(metadata, 'task_id')
    access_action = _string_metadata(metadata, 'access_action')
    auth_source = _string_metadata(metadata, 'authentication_provider', 'auth_source')
    auth_result = _string_metadata(metadata, 'result')
    username = _string_metadata(metadata, 'username')
    browser = _string_metadata(metadata, 'browser')
    operating_system = _string_metadata(metadata, 'operating_system')
    category = event_category(event_type)

    context: dict[str, Any] = {
        'module_label': category['label'],
        'category_key': category['key'],
        'category_label': category['label'],
        'category_icon': category['icon'],
        'target_type': 'Activity',
        'target_name': title,
        'event_icon': category['icon'],
        'event_tone': 'slate',
        'source_label': 'Administrative action',
        'source_detail': 'KAORI web runtime',
    }

    if event_type.startswith('kubernetes_configmap_'):
        context.update(
            target_type='ConfigMap',
            target_name=_string_metadata(metadata, 'configmap_name') or 'ConfigMap',
            event_icon='file-cog',
            event_tone='violet',
        )
    elif event_type.startswith('cluster_'):
        context.update(
            module_label='Integrations',
            target_type='Cluster',
            target_name=cluster_name or 'Cluster registration',
            event_icon='server',
            event_tone='blue',
        )
    elif event_type.startswith('prometheus_'):
        context.update(
            module_label='Integrations',
            target_type='Prometheus',
            target_name=cluster_name or endpoint or 'Prometheus integration',
            event_icon='activity',
            event_tone='cyan',
        )
    elif event_type.startswith('alertmanager_'):
        context.update(
            module_label='Integrations',
            target_type='Alertmanager',
            target_name=instance_name or cluster_name or endpoint or 'Alertmanager integration',
            event_icon='siren',
            event_tone='rose',
        )
    elif event_type == 'kubernetes_inventory_sync':
        context.update(
            module_label='Integrations',
            target_type='Inventory',
            target_name=cluster_name or 'All connected clusters',
            event_icon='database',
            event_tone='indigo',
        )
    elif event_type.startswith('governance_tls_secret_') or event_type.startswith('kubernetes_tls_secret_'):
        context.update(
            module_label='TLS Certificate',
            target_type='TLS Secret',
            target_name=cluster_name or _string_metadata(metadata, 'secret_name') or 'Kubernetes TLS Secret',
            event_icon='shield-check',
            event_tone='cyan',
        )
    elif event_type.startswith('kubernetes_secret_'):
        context.update(
            target_type='Kubernetes Secret',
            target_name=_string_metadata(metadata, 'secret_name', 'namespace') or 'Protected Secret',
            event_icon='key-round',
            event_tone='violet',
        )
    elif event_type.startswith(('report_', 'generated_report_', 'generated_reports_')):
        report_name = _string_metadata(metadata, 'report_name')
        report_id = _string_metadata(metadata, 'report_id')
        context.update(
            module_label='Platform Operations',
            target_type='Report',
            target_name=report_name or (f'Report #{report_id}' if report_id else 'Report operation'),
            event_icon='file-text',
            event_tone='violet',
            source_label='Reports operation',
            source_detail='KAORI Reports runtime',
        )
    elif event_type == 'authentication':
        action_is_logout = access_action == 'logout'
        result_failed = auth_result == 'failed'
        context.update(
            module_label='Access',
            target_type='User Session',
            target_name=username or 'Unauthenticated request',
            event_icon='log-out' if action_is_logout else 'log-in',
            event_tone='rose' if result_failed else 'indigo',
            source_label='Authentication provider',
            source_detail=auth_source or 'Provider not recorded',
        )
    elif event_type == 'user_preference':
        preference_name = _string_metadata(metadata, 'preference')
        context.update(
            module_label='Settings',
            target_type='User Preference',
            target_name=(preference_name or 'General Settings').replace('_', ' ').title(),
            event_icon='settings-2',
            event_tone='violet',
            source_label='Preference scope',
            source_detail='Authenticated user account',
        )
    elif event_type == 'account_security':
        security_action = _string_metadata(metadata, 'security_action')
        context.update(
            module_label='Settings',
            target_type='Account Security',
            target_name=(security_action or 'Security action').replace('_', ' ').title(),
            event_icon='key-round',
            event_tone='violet',
            source_label='Credential owner',
            source_detail=_string_metadata(metadata, 'credential_owner') or 'KAORI account',
        )
    elif event_type.startswith('operational_activity_'):
        context.update(
            module_label='Platform Operations',
            target_type='Retention',
            target_name=_string_metadata(metadata, 'archive_id', 'domain') or 'Operational activity archive',
            event_icon='archive',
            event_tone='violet',
        )

    if task_id:
        context['source_label'] = 'Background task'
        context['source_detail'] = f'Task {task_id}'
    elif event_type == 'authentication':
        context['source_label'] = 'Authentication provider'
        context['source_detail'] = auth_source or 'Provider not recorded'
    elif event_type.endswith('_connection_test'):
        context['source_label'] = 'Interactive test'
        context['source_detail'] = 'KAORI web action'
    elif event_type == 'kubernetes_inventory_sync':
        context['source_label'] = 'Inventory worker'
        context['source_detail'] = 'Synchronous inventory action'

    context_items = [
        {
            'label': 'Module',
            'value': context['module_label'],
            'tone': 'blue',
        }
    ]

    if event_type == 'authentication':
        context_items.append(
            {
                'label': 'Action',
                'value': 'Sign out' if access_action == 'logout' else 'Sign in',
                'tone': 'indigo',
            }
        )
        if auth_source:
            context_items.append(
                {
                    'label': 'Provider',
                    'value': auth_source,
                    'tone': 'blue',
                }
            )
        client_label = ' on '.join(value for value in (browser, operating_system) if value)
        if client_label:
            context_items.append(
                {
                    'label': 'Client',
                    'value': client_label,
                    'tone': 'amber',
                }
            )

    if environment:
        context_items.append(
            {
                'label': 'Environment',
                'value': environment,
                'tone': 'emerald' if environment.lower() == 'production' else 'amber',
            }
        )

    if cluster_name and context['target_type'] != 'Cluster':
        context_items.append(
            {
                'label': 'Cluster',
                'value': cluster_name,
                'tone': 'indigo',
            }
        )

    context['context_items'] = context_items
    return context
