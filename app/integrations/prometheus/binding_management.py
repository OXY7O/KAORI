from __future__ import annotations

from app.extensions.db import db
from app.integrations.binding_selectors import build_selector
from app.integrations.lifecycle import bind_instance, ensure_canonical_instance
from app.integrations.prometheus.capabilities import BINDING_CAPABILITY_KEYS
from app.integrations.prometheus.scope import KUBERNETES_CLUSTER_SCOPE
from app.models.cluster import Cluster
from app.models.integration import IntegrationBinding, IntegrationInstance
from app.models.prometheus import PrometheusInstance


def create_binding(
    *,
    instance: PrometheusInstance,
    cluster: Cluster,
    role: str = 'primary',
    priority: int = 100,
    selector_label: str | None = None,
    selector_value: str | None = None,
    selector_operator: str = '=',
    commit: bool = True,
) -> IntegrationBinding:
    normalized_role = str(role or 'primary').strip().lower()
    if normalized_role not in {'primary', 'secondary', 'fallback'}:
        raise ValueError('Select a supported source role.')
    if priority < 1 or priority > 1000:
        raise ValueError('Priority must be between 1 and 1000.')

    selector_json = build_selector(
        label=selector_label,
        value=selector_value,
        operator=selector_operator,
    )
    if selector_json is None:
        raise ValueError('Define a metrics identity selector before binding this Prometheus source.')

    canonical = ensure_canonical_instance(instance, provider_type='prometheus')
    existing = IntegrationBinding.query.filter_by(
        integration_instance_id=canonical.id,
        asset_type=KUBERNETES_CLUSTER_SCOPE,
        asset_key=cluster.id,
    ).first()
    if existing is not None:
        raise ValueError('This Prometheus connection is already bound to the selected managed cluster.')

    if normalized_role == 'primary':
        conflicting_primary = (
            IntegrationBinding.query.join(
                IntegrationInstance,
                IntegrationBinding.integration_instance_id == IntegrationInstance.id,
            )
            .filter(
                IntegrationInstance.provider_type == 'prometheus',
                IntegrationInstance.enabled.is_(True),
                IntegrationBinding.asset_type == KUBERNETES_CLUSTER_SCOPE,
                IntegrationBinding.asset_key == cluster.id,
                IntegrationBinding.binding_role == 'primary',
                IntegrationBinding.enabled.is_(True),
            )
            .first()
        )
        if conflicting_primary is not None:
            raise ValueError('The selected managed cluster already has an enabled primary Prometheus source.')

    binding = bind_instance(
        canonical,
        asset_type=KUBERNETES_CLUSTER_SCOPE,
        asset_key=cluster.id,
        role=normalized_role,
        priority=priority,
        capability_scope=list(BINDING_CAPABILITY_KEYS),
        selector_json=selector_json,
        validation_status='validation_required',
        validation_message=(
            'Binding saved. Validate the metrics identity selector and source runtime before operational use.'
        ),
    )
    if commit:
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise
    else:
        db.session.flush()
    return binding


def update_binding_selector(
    *,
    instance: PrometheusInstance,
    binding: IntegrationBinding,
    selector_label: str | None,
    selector_value: str | None,
    selector_operator: str = '=',
    commit: bool = True,
) -> IntegrationBinding:
    if instance.integration_instance_id != binding.integration_instance_id:
        raise ValueError('The selected binding does not belong to this Prometheus source.')
    selector_json = build_selector(
        label=selector_label,
        value=selector_value,
        operator=selector_operator,
    )
    if selector_json is None:
        raise ValueError('Define a metrics identity selector before saving this binding.')
    binding.selector_json = selector_json
    binding.validation_status = 'validation_required'
    binding.validation_message = (
        'Metrics identity changed. Validate this binding before KAORI uses it for operational queries.'
    )
    binding.last_validated_at = None
    if commit:
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise
    else:
        db.session.flush()
    return binding
