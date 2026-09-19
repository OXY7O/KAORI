from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MetricsSourceConfigurationInput:
    """Provider-neutral configuration submitted to the Metrics Source domain service."""

    name: str
    description: str | None
    provider_key: str
    endpoint: str
    compatibility_profile_override: str | None
    auth_type: str
    username: str | None
    password: str | None
    bearer_token: str | None
    timeout: int
    verify_ssl: bool
    enabled: bool
