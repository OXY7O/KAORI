from __future__ import annotations

from app.alertmanager.forms import AlertmanagerBindingForm
from app.alertmanager.repository import find_binding, get_binding, resolve_instances_for_scope
from app.alertmanager.resolver import resolve_alertmanager_sources
from app.extensions import db
from app.models.alertmanager import AlertmanagerBinding, AlertmanagerInstance


def create_or_update_binding(
    *,
    instance: AlertmanagerInstance,
    form: AlertmanagerBindingForm,
    commit: bool = True,
) -> AlertmanagerBinding:
    if not form.scope_key:
        raise ValueError('Binding scope is required.')
    if form.binding_role == 'primary':
        _ensure_primary_available(
            instance_id=instance.id,
            scope_type=form.scope_type,
            scope_key=form.scope_key,
        )

    binding = find_binding(
        instance_id=instance.id,
        scope_type=form.scope_type,
        scope_key=form.scope_key,
    )
    if binding is None:
        binding = AlertmanagerBinding()
        binding.alertmanager_instance_id = instance.id
        binding.scope_type = form.scope_type
        binding.scope_key = form.scope_key
        db.session.add(binding)

    binding.binding_role = form.binding_role
    binding.priority = form.priority
    binding.enabled = form.enabled
    if commit:
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise
    else:
        db.session.flush()
    return binding


def delete_binding(binding_id: int) -> AlertmanagerBinding | None:
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
    """Return ordered eligible instances while preserving the legacy list contract."""
    resolution = resolve_alertmanager_sources(
        scope_type=scope_type,
        scope_key=scope_key,
        required_capabilities=required_capabilities,
    )
    return [candidate.instance for candidate in resolution.eligible_candidates]


def _ensure_primary_available(*, instance_id: int, scope_type: str, scope_key: str) -> None:
    for source in resolve_instances_for_scope(scope_type=scope_type, scope_key=scope_key):
        if source.id == instance_id:
            continue
        for binding in source.bindings:
            if (
                binding.enabled
                and binding.scope_type == scope_type
                and binding.scope_key == scope_key
                and binding.binding_role == 'primary'
            ):
                raise ValueError(
                    'This scope already has a primary Alertmanager binding. '
                    'Use secondary/fallback or remove the existing primary binding first.'
                )
