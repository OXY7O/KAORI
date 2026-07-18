from __future__ import annotations

from app.alertmanager.forms import AlertmanagerBindingForm
from app.alertmanager.repository import find_binding, get_binding, list_bindings_for_scope
from app.extensions import db
from app.integrations.lifecycle import ensure_canonical_instance
from app.models.alertmanager import AlertmanagerInstance
from app.models.integration import IntegrationBinding

DEFAULT_CAPABILITIES = ['alerts', 'silences', 'routing', 'receivers']


def create_or_update_binding(
    *,
    instance: AlertmanagerInstance,
    form: AlertmanagerBindingForm,
    commit: bool = True,
) -> IntegrationBinding:
    if not form.scope_key:
        raise ValueError('Binding scope is required.')
    if form.binding_role == 'primary':
        _ensure_primary_available(
            instance_id=instance.id,
            scope_type=form.scope_type,
            scope_key=form.scope_key,
        )

    canonical = ensure_canonical_instance(instance, provider_type='alertmanager')
    binding = find_binding(
        instance_id=instance.id,
        scope_type=form.scope_type,
        scope_key=form.scope_key,
    )
    if binding is None:
        binding = IntegrationBinding(
            integration_instance_id=canonical.id,
            asset_type=form.scope_type,
            asset_key=str(form.scope_key),
            binding_role=form.binding_role,
        )
        db.session.add(binding)

    binding.priority = form.priority
    binding.enabled = form.enabled
    binding.capability_scope = DEFAULT_CAPABILITIES
    if commit:
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise
    else:
        db.session.flush()
    return binding


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


def resolve_sources(*, scope_type: str, scope_key: str, required_capabilities: tuple[str, ...] = ()) -> list[AlertmanagerInstance]:
    from app.alertmanager.resolver import resolve_alertmanager_sources

    resolution = resolve_alertmanager_sources(
        scope_type=scope_type,
        scope_key=scope_key,
        required_capabilities=required_capabilities,
    )
    return [candidate.instance for candidate in resolution.eligible_candidates]


def _ensure_primary_available(*, instance_id: int, scope_type: str, scope_key: str) -> None:
    for binding in list_bindings_for_scope(scope_type=scope_type, scope_key=scope_key):
        if binding.binding_role != 'primary' or not binding.enabled:
            continue
        provider = AlertmanagerInstance.query.filter_by(
            integration_instance_id=binding.integration_instance_id,
        ).first()
        if provider is not None and provider.id != instance_id:
            raise ValueError(
                'This scope already has a primary Alertmanager binding. '
                'Use secondary/fallback or remove the existing primary binding first.'
            )
