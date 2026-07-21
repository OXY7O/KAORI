"""Compatibility import for the canonical integration contracts.

New code imports from :mod:`app.integrations.contracts`. This module remains so
existing extensions and bookmarks-era code can upgrade without duplicating the
runtime contract implementation.
"""

from app.integrations.contracts import (
    CapabilitySnapshot,
    DiagnosticResult,
    HealthFactor,
    HealthState,
    RuntimeAdapter,
    RuntimeState,
)

__all__ = [
    'CapabilitySnapshot',
    'DiagnosticResult',
    'HealthFactor',
    'HealthState',
    'RuntimeAdapter',
    'RuntimeState',
]
