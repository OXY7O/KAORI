from __future__ import annotations

from typing import Any

def event_code(event_type: str) -> str:
    """Return the concise user-facing event code without domain-only prefixes."""
    normalized = event_type.strip()
    prefix = 'operational_activity_'
    if normalized.startswith(prefix):
        normalized = normalized[len(prefix):]
    return normalized or 'activity'


def event_label(event_type: str) -> str:
    return event_code(event_type).replace('_', ' ').strip().title() or 'Activity'


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
    endpoint = _string_metadata(metadata, 'endpoint', 'server')
    task_id = _string_metadata(metadata, 'task_id')

    context: dict[str, Any] = {
        'module_label': 'Operations',
        'target_type': 'Activity',
        'target_name': title,
        'event_icon': 'history',
        'event_tone': 'slate',
        'source_label': 'Administrative action',
        'source_detail': 'KAORI web application',
    }

    if event_type.startswith('cluster_'):
        context.update(
            module_label='Kubernetes Cluster',
            target_type='Cluster',
            target_name=cluster_name or 'Cluster registration',
            event_icon='server',
            event_tone='blue',
        )
    elif event_type.startswith('prometheus_'):
        context.update(
            module_label='Prometheus',
            target_type='Prometheus',
            target_name=cluster_name or endpoint or 'Prometheus integration',
            event_icon='activity',
            event_tone='cyan',
        )
    elif event_type.startswith('alertmanager_'):
        context.update(
            module_label='Alertmanager',
            target_type='Alertmanager',
            target_name=cluster_name or endpoint or 'Alertmanager integration',
            event_icon='siren',
            event_tone='rose',
        )
    elif event_type == 'kubernetes_inventory_sync':
        context.update(
            module_label='Kubernetes Inventory',
            target_type='Inventory',
            target_name=cluster_name or 'All connected clusters',
            event_icon='database',
            event_tone='indigo',
        )
    elif event_type.startswith('operational_activity_'):
        context.update(
            module_label='Activity Retention',
            target_type='Retention',
            target_name=_string_metadata(metadata, 'archive_id', 'domain') or 'Operational activity archive',
            event_icon='archive',
            event_tone='violet',
        )

    if task_id:
        context['source_label'] = 'Background task'
        context['source_detail'] = f'Task {task_id}'
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


