from __future__ import annotations

from sqlalchemy.exc import SQLAlchemyError

from app.extensions.db import db
from app.integrations.binding_selectors import build_selector
from app.integrations.binding_service import SourceBindingSpec
from app.integrations.lifecycle import BindingPersistenceSpec, bind_instance, ensure_canonical_instance
from app.integrations.observability.metrics_source.binding_profiles import get_binding_validation_profile
from app.integrations.observability.metrics_source.capabilities import BINDING_CAPABILITY_KEYS
from app.integrations.observability.metrics_source.routing import normalize_routing_policy
from app.integrations.observability.metrics_source.scope import KUBERNETES_CLUSTER_SCOPE
from app.models.cluster import Cluster
from app.models.integration import IntegrationBinding, IntegrationInstance
from app.models.metrics_source import MetricsSource


def create_binding(
    *,
    instance: MetricsSource,
    spec: SourceBindingSpec,
    cluster: Cluster | None = None,
    commit: bool = True,
) -> IntegrationBinding:
    normalized_role = str(spec.role or 'primary').strip().lower()
    if normalized_role not in {'primary', 'secondary', 'fallback'}:
        raise ValueError('Select a supported source role.')
    if spec.priority < 1 or spec.priority > 1000:
        raise ValueError('Priority must be between 1 and 1000.')

    normalized_scope_type = str(spec.asset_type or '').strip()
    normalized_scope_key = str(spec.asset_key or '').strip()
    if cluster is not None:
        normalized_scope_type = normalized_scope_type or KUBERNETES_CLUSTER_SCOPE
        normalized_scope_key = normalized_scope_key or str(cluster.id)
    if not normalized_scope_type:
        raise ValueError('Select an operational scope type before saving the metrics-source binding.')
    if not normalized_scope_key:
        raise ValueError('Select or enter an operational scope before saving the metrics-source binding.')
    if len(normalized_scope_key) > 255:
        raise ValueError('The operational scope key must be 255 characters or fewer.')

    selector_json = build_selector(
        label=spec.selector_label,
        value=spec.selector_value,
        operator=spec.selector_operator,
    )
    if selector_json is None:
        raise ValueError('Define a metrics identity selector before binding this metrics source.')

    canonical = ensure_canonical_instance(instance, integration_type='metrics_source')
    routing_policy = normalize_routing_policy(spec.routing_policy)
    existing = IntegrationBinding.query.filter_by(
        integration_instance_id=canonical.id,
        asset_type=normalized_scope_type,
        asset_key=normalized_scope_key,
    ).first()
    if existing is not None:
        raise ValueError('This metrics source is already bound to the selected operational scope.')

    _assert_primary_horizon_available(
        asset_type=normalized_scope_type,
        asset_key=normalized_scope_key,
        role=normalized_role,
        routing_policy=routing_policy,
    )

    validation_profile = get_binding_validation_profile(instance.adapter_key, normalized_scope_type)
    if validation_profile is None:
        raise ValueError(
            f'No metrics-source consumer validation profile is registered for asset type {normalized_scope_type!r}.'
        )

    binding = bind_instance(
        canonical,
        spec=BindingPersistenceSpec(
            asset_type=normalized_scope_type,
            asset_key=normalized_scope_key,
            role=normalized_role,
            priority=spec.priority,
            capability_scope=list(spec.capability_scope or BINDING_CAPABILITY_KEYS),
            selector_json=selector_json,
            routing_policy=routing_policy,
            validation_status='validation_required',
            validation_profile=validation_profile.profile_key,
            validation_message=(
                'Binding saved. Validate the metrics identity selector and source runtime before operational use.'
            ),
        ),
    )
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
    instance: MetricsSource,
    binding: IntegrationBinding,
    selector_label: str | None,
    selector_value: str | None,
    selector_operator: str = '=',
    routing_policy: dict | None = None,
    commit: bool = True,
) -> IntegrationBinding:
    if instance.integration_instance_id != binding.integration_instance_id:
        raise ValueError('The selected binding does not belong to this metrics source.')
    selector_json = build_selector(
        label=selector_label,
        value=selector_value,
        operator=selector_operator,
    )
    if selector_json is None:
        raise ValueError('Define a metrics identity selector before saving this binding.')
    binding.selector_json = selector_json
    if routing_policy is not None:
        normalized_routing = normalize_routing_policy(routing_policy)
        _assert_primary_horizon_available(
            asset_type=binding.asset_type,
            asset_key=str(binding.asset_key),
            role=binding.binding_role,
            routing_policy=normalized_routing,
            exclude_binding_id=binding.id,
        )
        binding.routing_policy = normalized_routing
    binding.validation_status = 'validation_required'
    profile = get_binding_validation_profile(instance.adapter_key, binding.asset_type)
    binding.validation_profile = profile.profile_key if profile is not None else None
    binding.validation_evidence = None
    binding.validation_message = (
        'Metrics identity changed. Validate this binding before KAORI uses it for operational queries.'
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


def _assert_primary_horizon_available(
    *,
    asset_type: str,
    asset_key: str,
    role: str,
    routing_policy: dict,
    exclude_binding_id: int | None = None,
) -> None:
    if role != 'primary':
        return
    query = IntegrationBinding.query.join(
        IntegrationInstance,
        IntegrationBinding.integration_instance_id == IntegrationInstance.id,
    ).filter(
        IntegrationInstance.integration_type == 'metrics_source',
        IntegrationInstance.enabled.is_(True),
        IntegrationBinding.asset_type == asset_type,
        IntegrationBinding.asset_key == asset_key,
        IntegrationBinding.binding_role == 'primary',
        IntegrationBinding.enabled.is_(True),
    )
    if exclude_binding_id is not None:
        query = query.filter(IntegrationBinding.id != exclude_binding_id)
    requested_horizon = str(routing_policy['query_horizon'])
    conflicting_primary = next(
        (
            item
            for item in query.all()
            if normalize_routing_policy(item.routing_policy)['query_horizon'] == requested_horizon
        ),
        None,
    )
    if conflicting_primary is not None:
        raise ValueError(
            f'The selected operational scope already has an enabled primary metrics source for {requested_horizon} queries.'
        )
