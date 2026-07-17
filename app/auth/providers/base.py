from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.auth.results import AuthResult


@runtime_checkable
class AuthProvider(Protocol):
    """Normalized contract implemented by every KAORI authentication provider."""

    source: str

    def authenticate(self, username: str, password: str) -> AuthResult:
        """Verify credentials and return a provider-neutral authentication result."""
        ...
