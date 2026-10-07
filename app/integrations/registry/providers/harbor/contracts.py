from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TypedDict


class HarborConnectionResult(TypedDict):
    connected: bool
    response_time_ms: int
    version: str
    registry_url: object | None
    external_url: object | None


@dataclass(frozen=True, slots=True)
class HarborConnectionSpec:
    endpoint: str
    auth_type: str = 'basic'
    username: str | None = None
    password: str | None = None
    timeout: int = 5
    verify_ssl: bool = True


@dataclass(frozen=True, slots=True)
class HarborRetryPolicy:
    transport_retries: int = 0
    backoff_seconds: float = 0.25


@dataclass(frozen=True, slots=True)
class ValidationStep:
    key: str
    label: str
    status: str
    detail: str
    response_time_ms: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            'key': self.key,
            'label': self.label,
            'status': self.status,
            'detail': self.detail,
            'response_time_ms': self.response_time_ms,
        }


@dataclass(frozen=True, slots=True)
class ValidationResult:
    connected: bool
    label: str
    response_time_ms: int | None = None
    version: str | None = None
    compatibility_status: str | None = None
    readiness_status: str | None = None
    compatibility_profile: str | None = None
    capabilities: tuple[str, ...] = ()
    capability_profile: str | None = None
    validation_steps: tuple[ValidationStep, ...] = ()
    error: str | None = None
    reason: str | None = None
    failure_code: str | None = None
    endpoint_host: str | None = None
    endpoint_port: int | None = None
    request_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            'connected': self.connected,
            'label': self.label,
            'response_time_ms': self.response_time_ms,
            'version': self.version,
            'compatibility_status': self.compatibility_status,
            'readiness_status': self.readiness_status,
            'compatibility_profile': self.compatibility_profile,
            'capabilities': list(self.capabilities),
            'capability_profile': self.capability_profile,
            'validation_steps': [step.to_dict() for step in self.validation_steps],
            'error': self.error,
            'reason': self.reason,
            'failure_code': self.failure_code,
            'endpoint_host': self.endpoint_host,
            'endpoint_port': self.endpoint_port,
            'request_path': self.request_path,
        }
