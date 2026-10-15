"""App-scoped composition boundary for Tenant Release/Handoff operations.

The originating Tenant modules remain authoritative for committed evidence,
authorization, provider mutation and fail-closed recovery. No import is used to
reach a downstream operation from a module that it itself depends on.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from flask import current_app


def require_handoff_operation(name: str) -> Callable[..., Any]:
    """Use one explicitly wired Tenant operation or fail closed."""
    operations = current_app.extensions.get('kaori_tenant_handoff_operations')
    if not isinstance(operations, dict):
        raise RuntimeError('Tenant Handoff operations are not registered.')
    operation = operations.get(name)
    if not callable(operation):
        raise RuntimeError(f'Tenant Handoff operation {name!r} is not registered.')
    return operation
