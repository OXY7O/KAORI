"""Integration domain package.

Keep this package initializer free from eager route imports. Provider resolvers and
runtime services import lightweight helpers from ``app.integrations`` while the
application itself is still assembling blueprints. Importing the routes here would
therefore pull validation tasks and provider services back into partially initialized
modules.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.integrations.routes import integrations_bp as integrations_bp

__all__ = ['integrations_bp']


def __getattr__(name: str) -> Any:
    """Lazily expose the integrations blueprint for compatibility."""
    if name == 'integrations_bp':
        from app.integrations.routes import integrations_bp

        globals()[name] = integrations_bp
        return integrations_bp
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
