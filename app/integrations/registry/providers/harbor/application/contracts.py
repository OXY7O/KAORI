from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class HarborRegistrationInput:
    name: str
    environment: str
    description: str | None
    endpoint: str
    auth_type: str
    username: str | None
    password: str | None
    timeout: int
    verify_ssl: bool
    enabled: bool
