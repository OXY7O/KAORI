from __future__ import annotations

from sqlalchemy.exc import SQLAlchemyError

from app.extensions.db import db
from app.integrations.alertmanager.binding_profiles import get_alert_consumer_profile
from app.integrations.alertmanager.capabilities import BINDING_CAPABILITY_KEYS
from app.integrations.binding_selectors import build_selector
from app.integrations.binding_service import SourceBindingSpec
from app.integrations.lifecycle import ensure_canonical_instance
from app.models.alertmanager import AlertmanagerInstance
from app.models.integration import IntegrationBinding, IntegrationInstance


def create_binding(
    *,
    instance: AlertmanagerInstance,
    spec: SourceBindingSpec,
    commit: bool = True,
) -> IntegrationBinding:
    normalized_scope_type = str(spec.asset_type or '').strip()
    normalized_scope_key = str(spec.asset_key or '').strip()
    normalized_role = str(spec.role or 'primary').strip().lower()

    if not normalized_scope_type:
        raise ValueError('Select an operational scope type before saving the binding.')
    if not normalized_scope_key:
        raise ValueError('Select or enter an operational scope before saving the binding.')
    if len(normalized_scope_key) > 255:
        raise ValueError('The operational scope key must be 255 characters or fewer.')
    if normalized_role not in {'primary', 'secondary', 'fallback'}:
        raise ValueError('Select a supported source role.')
    consumer_profile = get_alert_consumer_profile(normalized_scope_type)
    if consumer_profile is None:
        raise ValueError(f'No Alertmanager consumer profile is registered for scope type {normalized_scope_type!r}.')
    if spec.priority < 1 or spec.priority > 1000:
        raise ValueError('Priority must be between 1 and 1000.')

    canonical = ensure_canonical_instance(instance, provider_type='alertmanager')
    existing = IntegrationBinding.query.filter_by(
        integration_instance_id=canonical.id,
        asset_type=normalized_scope_type,
        asset_key=normalized_scope_key,
    ).first()
    if existing is not None:
        raise ValueError(
            'This Alertmanager instance is already bound to the selected scope. '
            'Remove the existing binding before creating a replacement.'
        )

    if normalized_role == 'primary':
        conflicting_primary = (
            IntegrationBinding.query.join(
                IntegrationInstance,
                IntegrationBinding.integration_instance_id == IntegrationInstance.id,
            )
            .join(
                AlertmanagerInstance,
                AlertmanagerInstance.integration_instance_id == IntegrationInstance.id,
            )
            .filter(
                IntegrationInstance.provider_type == 'alertmanager',
                IntegrationInstance.enabled.is_(True),
                IntegrationBinding.asset_type == normalized_scope_type,
                IntegrationBinding.asset_key == normalized_scope_key,
                IntegrationBinding.binding_role == 'primary',
                IntegrationBinding.enabled.is_(True),
                AlertmanagerInstance.id != instance.id,
            )
            .first()
        )
        if conflicting_primary is not None:
            provider = AlertmanagerInstance.query.filter_by(
                integration_instance_id=conflicting_primary.integration_instance_id,
            ).first()
            provider_name = provider.name if provider is not None else 'another source'
            raise ValueError(
                f'This scope already has a primary Alertmanager binding through {provider_name}. '
                'Choose secondary or fallback, or remove the existing primary binding first.'
            )

    selector_json = build_selector(
        label=spec.selector_label,
        value=spec.selector_value,
        operator=spec.selector_operator,
    )
    if normalized_scope_type != 'global' and selector_json is None:
        raise ValueError('Define an alert identity selector before binding this Alertmanager source.')

    binding = IntegrationBinding()
    binding.integration_instance_id = canonical.id
    binding.asset_type = normalized_scope_type
    binding.asset_key = normalized_scope_key
    binding.binding_role = normalized_role
    binding.priority = spec.priority
    binding.enabled = spec.enabled
    binding.capability_scope = list(spec.capability_scope or BINDING_CAPABILITY_KEYS)
    binding.selector_json = selector_json
    binding.validation_profile = consumer_profile.profile_key
    binding.validation_evidence = None
    binding.validation_status = 'validation_required'
    binding.validation_message = (
        'Binding saved. Validate source labels and runtime evidence before relying on this shared scope.'
    )
    db.session.add(binding)
    if commit:
        try:
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            raise
    else:
        db.session.flush()
    return binding


def update_binding_selector(
    *,
    instance: AlertmanagerInstance,
    binding: IntegrationBinding,
    selector_label: str | None,
    selector_value: str | None,
    selector_operator: str = '=',
    commit: bool = True,
) -> IntegrationBinding:
    if instance.integration_instance_id != binding.integration_instance_id:
        raise ValueError('The selected binding does not belong to this Alertmanager source.')
    if binding.asset_type == 'global':
        raise ValueError('Global Alertmanager bindings do not require an alert identity selector.')
    selector_json = build_selector(
        label=selector_label,
        value=selector_value,
        operator=selector_operator,
    )
    if selector_json is None:
        raise ValueError('Define an alert identity selector before saving this binding.')
    binding.selector_json = selector_json
    profile = get_alert_consumer_profile(binding.asset_type)
    binding.validation_profile = profile.profile_key if profile is not None else None
    binding.validation_evidence = None
    binding.validation_status = 'validation_required'
    binding.validation_message = (
        'Alert identity changed. Validate this binding before KAORI uses it for operational requests.'
    )
    binding.last_validated_at = None
    if commit:
        try:
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            raise
    else:
        db.session.flush()
    return binding
