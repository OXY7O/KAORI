from __future__ import annotations

from app.integrations.prometheus.binding_validators.kubernetes import validate_kubernetes_binding
from app.integrations.prometheus.binding_validators.object_storage import validate_object_storage_binding
from app.integrations.prometheus.binding_validators.registry import (
    get_binding_validator,
    register_binding_validator,
)
from app.integrations.prometheus.scope import KUBERNETES_CLUSTER_SCOPE

register_binding_validator(KUBERNETES_CLUSTER_SCOPE, validate_kubernetes_binding)
register_binding_validator('object_storage_system', validate_object_storage_binding)

__all__ = ['get_binding_validator', 'register_binding_validator']
