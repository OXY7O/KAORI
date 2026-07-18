from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class AlertmanagerConnectionSpec:
    endpoint: str
    auth_type: str = 'none'
    username: str | None = None
    password: str | None = None
    bearer_token: str | None = None
    timeout: int = 5
    verify_ssl: bool = True


@dataclass(frozen=True, slots=True)
class AlertQuery:
    active: bool = True
    silenced: bool = True
    inhibited: bool = True
    unprocessed: bool = True
    receiver: str | None = None
    filters: tuple[str, ...] = ()


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
            'error': self.error,
            'reason': self.reason,
            'failure_code': self.failure_code,
            'endpoint_host': self.endpoint_host,
            'endpoint_port': self.endpoint_port,
            'request_path': self.request_path,
        }


@dataclass(frozen=True, slots=True)
class CanonicalAlert:
    source_instance_id: int | None
    source_instance_name: str
    alert_name: str
    severity: str
    state: str
    starts_at: datetime | None
    ends_at: datetime | None
    labels: dict[str, Any] = field(default_factory=dict)
    annotations: dict[str, Any] = field(default_factory=dict)
    receiver: str = '-'
    silenced: bool = False
    inhibited: bool = False
    silenced_by: tuple[str, ...] = ()
    inhibited_by: tuple[str, ...] = ()
    generator_url: str = ''
    runbook_url: str = ''
    fingerprint: str = ''
    summary: str = ''
    description: str = ''
    duration: str = '-'

    def to_dict(self) -> dict[str, Any]:
        return {
            'source': 'alertmanager',
            'source_instance_id': self.source_instance_id,
            'source_instance_name': self.source_instance_name,
            'alert_name': self.alert_name,
            'alertname': self.alert_name,
            'severity': self.severity,
            'state': self.state,
            'status': self.state,
            'starts_at': self.starts_at,
            'ends_at': self.ends_at,
            'startsAt': self.starts_at.isoformat() if self.starts_at else None,
            'endsAt': self.ends_at.isoformat() if self.ends_at else None,
            'labels': self.labels,
            'annotations': self.annotations,
            'receiver': self.receiver,
            'silenced': self.silenced,
            'inhibited': self.inhibited,
            'silenced_by': list(self.silenced_by),
            'inhibited_by': list(self.inhibited_by),
            'generator_url': self.generator_url,
            'generatorURL': self.generator_url,
            'runbook_url': self.runbook_url,
            'fingerprint': self.fingerprint,
            'summary': self.summary,
            'description': self.description,
            'duration': self.duration,
        }
