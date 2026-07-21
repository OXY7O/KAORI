from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PrometheusConnectionSpec:
    endpoint: str
    auth_type: str = 'none'
    username: str | None = None
    password: str | None = None
    bearer_token: str | None = None
    timeout: int = 5
    verify_ssl: bool = True
