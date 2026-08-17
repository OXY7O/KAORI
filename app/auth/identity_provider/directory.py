from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.models import IdentityProvider


class DirectoryProviderError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ExternalIdentity:
    subject: str
    username: str
    email: str | None
    display_name: str | None
    distinguished_name: str


class DirectoryProviderAdapter(Protocol):
    adapter_key: str

    def validate_configuration(self, provider: IdentityProvider) -> str: ...

    def search(self, provider: IdentityProvider, query: str) -> list[ExternalIdentity]: ...
