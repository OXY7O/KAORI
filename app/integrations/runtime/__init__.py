"""Shared integration runtime orchestration package."""

from __future__ import annotations

__all__ = ['dispatch_integration_runtime_refresh']


def dispatch_integration_runtime_refresh() -> dict[str, object]:
    """Queue runtime refresh jobs through the canonical monitoring service.

    The import remains local to keep package initialization lightweight and avoid
    circular imports while exposing a stable public API to CLI callers.
    """
    from app.integrations.runtime.monitoring import (
        dispatch_integration_runtime_refresh as _dispatch,
    )

    return _dispatch()
