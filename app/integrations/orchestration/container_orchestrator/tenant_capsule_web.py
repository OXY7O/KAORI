"""Read-only resolver for Tenant-owned Capsule RBAC web operations.

Composition occurs per Flask application in bootstrap; Integration routes retain
request authorization/CSRF and do not import Tenant domain implementations.
"""

from collections.abc import Callable
from typing import Any

from flask import current_app


def capsule_rbac_operation(name: str) -> Callable[..., Any]:
    """Fail closed when canonical Tenant operations are not registered."""
    operations = current_app.extensions.get('kaori_tenant_capsule_rbac_bootstrap')
    if not isinstance(operations, dict):
        raise RuntimeError('Tenant Capsule RBAC operations are not registered.')
    operation = operations.get(name)
    if not callable(operation):
        raise RuntimeError(f'Tenant Capsule RBAC operation {name!r} is unavailable.')
    return operation
