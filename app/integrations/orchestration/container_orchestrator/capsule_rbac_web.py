"""Resolve Tenant-owned Capsule RBAC actions at the Flask application boundary."""

from collections.abc import Callable
from typing import Any

from flask import current_app


def capsule_rbac_operation(name: str) -> Callable[..., Any]:
    """Resolve the Tenant-owned operation via the application composition root."""
    operations = current_app.extensions.get('kaori_tenant_capsule_rbac_bootstrap')
    if not isinstance(operations, dict):
        raise RuntimeError('Tenant Capsule RBAC operations are not registered.')
    operation = operations.get(name)
    if not callable(operation):
        raise RuntimeError(f'Tenant Capsule RBAC operation {name!r} is unavailable.')
    return operation
