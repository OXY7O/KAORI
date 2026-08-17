from __future__ import annotations

from flask import abort, render_template
from flask_login import current_user

from app.integrations.capability_registry import build_capability_registry_view
from app.integrations.observability.alert_source.providers.alertmanager.application.presentation import (
    build_instance_context,
)
from app.integrations.observability.alert_source.providers.alertmanager.application.service import (
    get_alertmanager_instance,
)
from app.integrations.validation.state import build_validation_snapshot, get_active_validation_task_id
from app.platform_operations.notifications.service import get_navigation_notification_context


def instance_or_404(instance_id: int):
    instance = get_alertmanager_instance(instance_id)
    if instance is None:
        abort(404)
    return instance


def instance_context(instance, *, binding_page: int = 1, binding_per_page: int = 5) -> dict:
    context = build_instance_context(instance, binding_page=binding_page, binding_per_page=binding_per_page)
    context['capability_registry'] = build_capability_registry_view(
        context.get('capability_rows', []),
        search_fields=('label', 'category', 'description'),
        distinguish_optional_gap=True,
    )
    context['validation_job'] = _active_task(instance.integration_instance_id, 'full_validation')
    context['runtime_refresh_job'] = _active_task(instance.integration_instance_id, 'runtime_refresh')
    context['binding_validation_job'] = _active_binding_task(instance, context.get('bindings', []))
    return context


def render_instance_partial(
    template_name: str, instance, *, operation_feedback: dict | None = None, **extra_context
) -> str:
    context = instance_context(instance)
    context.update(extra_context)
    context['operation_feedback'] = operation_feedback
    context['notification_context'] = get_navigation_notification_context(user_id=int(current_user.id))
    return render_template(template_name, **context)


def _active_task(integration_instance_id: int, operation: str):
    task_id = get_active_validation_task_id(
        integration_type='alert_source',
        operation=operation,
        integration_instance_id=integration_instance_id,
    )
    return build_validation_snapshot(task_id) if task_id else None


def _active_binding_task(instance, bindings):
    for binding in bindings:
        task_id = get_active_validation_task_id(
            integration_type='alert_source',
            operation='binding_validation',
            integration_instance_id=instance.integration_instance_id,
            binding_id=binding.id,
        )
        if task_id:
            return build_validation_snapshot(task_id)
    return None
