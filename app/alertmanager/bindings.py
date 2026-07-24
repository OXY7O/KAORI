from __future__ import annotations

from app.alertmanager.forms import AlertmanagerBindingForm
from app.alertmanager.repository import get_binding
from app.alertmanager.resolver import resolve_alertmanager_sources
from app.extensions.db import db
from app.integrations.registry import get_integration
from app.models.alertmanager import AlertmanagerInstance
from app.models.integration import IntegrationBinding


def create_or_update_binding(
    *,
    instance: AlertmanagerInstance,
    form: AlertmanagerBindingForm,
    commit: bool = True,
) -> IntegrationBinding:
    return get_integration('alertmanager').execute(
        'binding.create',
        instance,
        scope_type=form.scope_type,
        scope_key=form.scope_key,
        role=form.binding_role,
        priority=form.priority,
        enabled=form.enabled,
        selector_label=form.selector_label,
        selector_value=form.selector_value,
        selector_operator=form.selector_operator,
        commit=commit,
    )


def delete_binding(binding_id: int) -> IntegrationBinding | None:
    binding = get_binding(binding_id)
    if binding is None:
        return None
    db.session.delete(binding)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return binding


def resolve_sources(
    *,
    scope_type: str,
    scope_key: str,
    required_capabilities: tuple[str, ...] = (),
) -> list[AlertmanagerInstance]:
    resolution = resolve_alertmanager_sources(
        scope_type=scope_type,
        scope_key=scope_key,
        required_capabilities=required_capabilities,
    )
    return [candidate.instance for candidate in resolution.eligible_candidates]
