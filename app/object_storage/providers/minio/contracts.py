from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MinioRegistrationInput:
    name: str
    environment: str
    description: str | None
    endpoint: str
    access_key: str
    secret_key: str
    region: str
    addressing_style: str
    timeout: int
    verify_ssl: bool
    declared_release: str
    enabled: bool
