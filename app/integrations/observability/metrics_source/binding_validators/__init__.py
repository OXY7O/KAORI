from __future__ import annotations

from app.integrations.observability.metrics_source.binding_validators.kubernetes import validate_kubernetes_binding
from app.integrations.observability.metrics_source.binding_validators.object_storage import (
    validate_object_storage_binding,
)
from app.integrations.observability.metrics_source.binding_validators.registry import (
    get_binding_validator,
    register_binding_validator,
)
from app.integrations.observability.metrics_source.scope import KUBERNETES_CLUSTER_SCOPE

PROMETHEUS_HTTP_ADAPTER = 'prometheus_http'

register_binding_validator(PROMETHEUS_HTTP_ADAPTER, KUBERNETES_CLUSTER_SCOPE, validate_kubernetes_binding)
register_binding_validator(PROMETHEUS_HTTP_ADAPTER, 'object_storage_system', validate_object_storage_binding)

__all__ = ['get_binding_validator', 'register_binding_validator']
