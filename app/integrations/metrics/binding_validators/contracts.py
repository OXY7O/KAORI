from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from app.integrations.metrics.binding_profiles import BindingValidationProfile
from app.models.integration import IntegrationBinding


@dataclass(frozen=True, slots=True)
class BindingValidationAssessment:
    status: str
    message: str
    matched_series: int = 0
    matched_signal: str | None = None
    available_capabilities: tuple[str, ...] = ()
    evidence: dict[str, Any] = field(default_factory=dict)


class BindingValidator(Protocol):
    def __call__(
        self,
        *,
        client: Any,
        binding: IntegrationBinding,
        profile: BindingValidationProfile,
    ) -> BindingValidationAssessment: ...
