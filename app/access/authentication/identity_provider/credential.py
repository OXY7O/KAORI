from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.access.authentication.results import AuthResult


@runtime_checkable
class CredentialAuthAdapter(Protocol):
    adapter_key: str

    def authenticate(self, username: str, password: str) -> AuthResult: ...
