from __future__ import annotations

from flask import abort, render_template, url_for
from flask_login import current_user

from app.integrations.capability_registry import build_capability_registry_view
from app.integrations.validation.state import build_validation_snapshot, get_active_validation_task_id
from app.metrics_sources.presentation import build_instance_context
from app.metrics_sources.repository import get_instance
from app.models import MetricsSource
from app.notifications.service import get_navigation_notification_context


def instance_or_404(instance_id: int) -> MetricsSource:
    instance = get_instance(instance_id)
    if instance is None:
        abort(404)
    return instance


def instance_detail_context(
    instance: MetricsSource,
    *,
    page: int = 1,
    per_page: int = 5,
    history_trigger: str = '',
    history_health: str = '',
    history_readiness: str = '',
    binding_page: int = 1,
    binding_per_page: int = 5,
) -> dict:
    """Build one canonical Metrics Source detail/partial context."""
    context = build_instance_context(
        instance,
        page=page,
        per_page=per_page,
        history_trigger=history_trigger,
        history_health=history_health,
        history_readiness=history_readiness,
        binding_page=binding_page,
        binding_per_page=binding_per_page,
    )
    context['capability_registry'] = build_capability_registry_view(
        context.get('capability_rows', []),
        search_fields=('label', 'category', 'source_owner'),
    )
    context['delete_instance_url'] = url_for('metrics.delete_instance', instance_id=instance.id)
    context['validation_job'] = _active_task(instance.integration_instance_id, 'full_validation')
    context['runtime_refresh_job'] = _active_task(instance.integration_instance_id, 'runtime_refresh')
    context['binding_validation_job'] = _active_binding_task(instance, context.get('bindings', []))
    return context


def render_instance_partial(
    template_name: str,
    instance: MetricsSource,
    *,
    operation_feedback: dict | None = None,
    **extra_context,
) -> str:
    context = instance_detail_context(instance)
    context.update(extra_context)
    context['operation_feedback'] = operation_feedback
    context['notification_context'] = get_navigation_notification_context(user_id=int(current_user.id))
    return render_template(template_name, **context)


def _active_task(integration_instance_id: int, operation: str):
    task_id = get_active_validation_task_id(
        integration_type='metrics_source',
        operation=operation,
        integration_instance_id=integration_instance_id,
    )
    return build_validation_snapshot(task_id) if task_id else None


def _active_binding_task(instance: MetricsSource, bindings):
    for binding in bindings:
        task_id = get_active_validation_task_id(
            integration_type='metrics_source',
            operation='binding_validation',
            integration_instance_id=instance.integration_instance_id,
            binding_id=binding.id,
        )
        if task_id:
            return build_validation_snapshot(task_id)
    return None
