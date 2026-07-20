from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from app.integrations.resolver import resolve_integration
from app.models.integration import IntegrationBinding
from app.models.prometheus import PrometheusInstance

_ROLE_ORDER: Final[dict[str, int]] = {
    'primary': 0,
    'secondary': 1,
    'fallback': 2,
}
_BLOCKED_READINESS: Final[set[str]] = {'blocked', 'unavailable', 'disabled', 'incompatible'}
_READY_READINESS: Final[set[str]] = {'ready'}
_DEGRADED_READINESS: Final[set[str]] = {'degraded'}
_FAILED_HEALTH: Final[set[str]] = {'disconnected', 'error', 'failed', 'incompatible', 'unhealthy'}


@dataclass(frozen=True, slots=True)
class ResolvedPrometheusSource:
    instance: PrometheusInstance
    binding: IntegrationBinding
    eligible: bool
    capability_state: str
    missing_binding_capabilities: tuple[str, ...]
    missing_technical_capabilities: tuple[str, ...]
    operational_state: str
    decision_reason: str
    score: tuple[int, int, int, int, int, int]


@dataclass(frozen=True, slots=True)
class PrometheusSourceResolution:
    scope_type: str
    scope_key: str
    required_binding_capabilities: tuple[str, ...]
    required_technical_capabilities: tuple[str, ...]
    candidates: tuple[ResolvedPrometheusSource, ...]

    @property
    def eligible_candidates(self) -> tuple[ResolvedPrometheusSource, ...]:
        return tuple(candidate for candidate in self.candidates if candidate.eligible)

    @property
    def selected(self) -> ResolvedPrometheusSource | None:
        return self.eligible_candidates[0] if self.eligible_candidates else None


def resolve_prometheus_sources(
    *,
    scope_type: str,
    scope_key: str,
    required_binding_capabilities: tuple[str, ...] = (),
    required_technical_capabilities: tuple[str, ...] = (),
) -> PrometheusSourceResolution:
    canonical = resolve_integration(
        provider_type='prometheus',
        asset_type=scope_type,
        asset_key=scope_key,
        required_capabilities=required_binding_capabilities,
    )
    candidates: list[ResolvedPrometheusSource] = []
    for item in canonical.candidates:
        provider_instance = PrometheusInstance.query.filter_by(
            integration_instance_id=item.instance.id,
        ).first()
        if provider_instance is None:
            continue
        candidates.append(
            _evaluate_binding(
                item.binding,
                provider_instance,
                missing_binding_capabilities=item.missing_capabilities,
                required_technical_capabilities=required_technical_capabilities,
            )
        )
    candidates.sort(key=lambda candidate: candidate.score)
    return PrometheusSourceResolution(
        scope_type=scope_type,
        scope_key=str(scope_key),
        required_binding_capabilities=required_binding_capabilities,
        required_technical_capabilities=required_technical_capabilities,
        candidates=tuple(candidates),
    )


def _evaluate_binding(
    binding: IntegrationBinding,
    instance: PrometheusInstance,
    *,
    missing_binding_capabilities: tuple[str, ...],
    required_technical_capabilities: tuple[str, ...],
) -> ResolvedPrometheusSource:
    readiness = (instance.readiness_status or '').strip().lower()
    health = (instance.last_status or '').strip().lower()
    observed = set((instance.capabilities or {}).get('available') or ())
    missing_technical = tuple(sorted(set(required_technical_capabilities) - observed))

    if not required_technical_capabilities:
        capability_state = 'not_required'
        capability_rank = 0
        technical_eligible = True
    elif not observed:
        # Preserve migrated sources during the compatibility window while ranking
        # positively validated sources first.
        capability_state = 'unknown'
        capability_rank = 1
        technical_eligible = True
    elif missing_technical:
        capability_state = 'missing_required'
        capability_rank = 2
        technical_eligible = False
    else:
        capability_state = 'verified'
        capability_rank = 0
        technical_eligible = True

    binding_eligible = not missing_binding_capabilities
    readiness_eligible = readiness not in _BLOCKED_READINESS
    eligible = bool(
        instance.enabled
        and binding.enabled
        and binding_eligible
        and readiness_eligible
        and technical_eligible
    )
    operational_rank, operational_state = _operational_rank(readiness=readiness, health=health)
    reason = _decision_reason(
        eligible=eligible,
        readiness=readiness,
        health=health,
        capability_state=capability_state,
        missing_binding=missing_binding_capabilities,
        missing_technical=missing_technical,
    )
    return ResolvedPrometheusSource(
        instance=instance,
        binding=binding,
        eligible=eligible,
        capability_state=capability_state,
        missing_binding_capabilities=missing_binding_capabilities,
        missing_technical_capabilities=missing_technical,
        operational_state=operational_state,
        decision_reason=reason,
        score=(
            0 if eligible else 1,
            operational_rank,
            capability_rank,
            _ROLE_ORDER.get(binding.binding_role, 9),
            binding.priority,
            binding.id,
        ),
    )


def _operational_rank(*, readiness: str, health: str) -> tuple[int, str]:
    if readiness in _READY_READINESS and health == 'connected':
        return 0, 'healthy'
    if readiness in _DEGRADED_READINESS and health == 'connected':
        return 1, 'degraded'
    if health == 'connected':
        return 2, 'connected_unvalidated'
    if health in _FAILED_HEALTH:
        return 6, 'unhealthy'
    if readiness in _READY_READINESS:
        return 3, 'ready_not_connected'
    if readiness in _DEGRADED_READINESS:
        return 4, 'degraded_not_connected'
    return 5, 'validation_required'


def _decision_reason(
    *,
    eligible: bool,
    readiness: str,
    health: str,
    capability_state: str,
    missing_binding: tuple[str, ...],
    missing_technical: tuple[str, ...],
) -> str:
    if missing_binding:
        return f'Missing binding coverage: {", ".join(missing_binding)}.'
    if capability_state == 'missing_required':
        return f'Missing validated technical capabilities: {", ".join(missing_technical)}.'
    if readiness in _BLOCKED_READINESS:
        return f'Readiness state {readiness or "unknown"} blocks source selection.'
    if not eligible:
        return 'Source is not eligible for selection.'
    if capability_state == 'unknown':
        return 'Capability validation has not been observed; source remains available for compatibility but ranks below verified sources.'
    if health in _FAILED_HEALTH:
        return 'Source is eligible but currently unhealthy; a healthier bound source is preferred.'
    if readiness in _DEGRADED_READINESS:
        return 'Source is usable with degraded readiness.'
    if readiness not in _READY_READINESS:
        return 'Source is usable but requires validation; a validated source is preferred.'
    return 'Source satisfies readiness, runtime health, binding coverage, and technical capability requirements.'
