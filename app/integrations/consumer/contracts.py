from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ConsumerDiagnostic:
    code: str
    message: str
    category: str = 'runtime'
    remediation: str | None = None
    source_owner: str | None = None
    detail: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            'code': self.code,
            'message': self.message,
            'category': self.category,
            'remediation': self.remediation,
            'source_owner': self.source_owner,
            'detail': self.detail,
        }


@dataclass(frozen=True)
class ConsumerSource:
    provider: str
    instance_id: str | int | None
    instance_name: str
    endpoint_product: str | None = None
    compatibility_profile: str | None = None
    capability_profile: str | None = None
    readiness: str | None = None
    health: str | None = None
    fallback_used: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            'provider': self.provider,
            'instance_id': self.instance_id,
            'instance_name': self.instance_name,
            'endpoint_product': self.endpoint_product,
            'compatibility_profile': self.compatibility_profile,
            'capability_profile': self.capability_profile,
            'readiness': self.readiness,
            'health': self.health,
            'fallback_used': self.fallback_used,
        }


@dataclass(frozen=True)
class ConsumerResult[PayloadT]:
    ok: bool
    payload: PayloadT
    source: ConsumerSource | None = None
    diagnostics: tuple[ConsumerDiagnostic, ...] = field(default_factory=tuple)
    required_capabilities: tuple[str, ...] = field(default_factory=tuple)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def error(self) -> str | None:
        if self.ok or not self.diagnostics:
            return None
        return self.diagnostics[0].message

    def to_dict(self) -> dict[str, Any]:
        return {
            'ok': self.ok,
            'payload': self.payload,
            'source': self.source.to_dict() if self.source else None,
            'diagnostics': [item.to_dict() for item in self.diagnostics],
            'required_capabilities': list(self.required_capabilities),
            'metadata': self.metadata,
            'error': self.error,
        }
