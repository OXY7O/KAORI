from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from app.alertmanager.repository import list_bindings_for_scope
from app.models.alertmanager import AlertmanagerBinding, AlertmanagerInstance

_ROLE_ORDER: Final[dict[str, int]] = {
    'primary': 0,
    'secondary': 1,
    'fallback': 2,
}
_BLOCKED_READINESS: Final[set[str]] = {'blocked', 'unavailable', 'disabled', 'incompatible'}
_READY_READINESS: Final[set[str]] = {'ready'}
_DEGRADED_READINESS: Final[set[str]] = {'degraded'}
_FAILED_HEALTH: Final[set[str]] = {'disconnected', 'error', 'incompatible'}


@dataclass(frozen=True, slots=True)
class ResolvedAlertmanagerSource:
    instance: AlertmanagerInstance
    binding: AlertmanagerBinding
    eligible: bool
    capability_state: str
    missing_capabilities: tuple[str, ...]
    operational_state: str
    decision_reason: str
    score: tuple[int, int, int, int, int, int]

    def to_dict(self) -> dict[str, object]:
        return {
            'instance_id': self.instance.id,
            'instance_name': self.instance.name,
            'binding_id': self.binding.id,
            'binding_role': self.binding.binding_role,
            'priority': self.binding.priority,
            'eligible': self.eligible,
            'capability_state': self.capability_state,
            'missing_capabilities': list(self.missing_capabilities),
            'operational_state': self.operational_state,
            'decision_reason': self.decision_reason,
        }


@dataclass(frozen=True, slots=True)
class AlertmanagerSourceResolution:
    scope_type: str
    scope_key: str
    required_capabilities: tuple[str, ...]
    candidates: tuple[ResolvedAlertmanagerSource, ...]

    @property
    def eligible_candidates(self) -> tuple[ResolvedAlertmanagerSource, ...]:
        return tuple(candidate for candidate in self.candidates if candidate.eligible)

    @property
    def selected(self) -> ResolvedAlertmanagerSource | None:
        candidates = self.eligible_candidates
        return candidates[0] if candidates else None

    def to_dict(self) -> dict[str, object]:
        selected = self.selected
        return {
            'scope_type': self.scope_type,
            'scope_key': self.scope_key,
            'required_capabilities': list(self.required_capabilities),
            'selected_instance_id': selected.instance.id if selected else None,
            'selected_instance_name': selected.instance.name if selected else None,
            'selected_binding_role': selected.binding.binding_role if selected else None,
            'candidate_count': len(self.candidates),
            'eligible_candidate_count': len(self.eligible_candidates),
            'candidates': [candidate.to_dict() for candidate in self.candidates],
        }


def resolve_alertmanager_sources(
    *,
    scope_type: str,
    scope_key: str,
    required_capabilities: tuple[str, ...] = (),
) -> AlertmanagerSourceResolution:
    candidates = [
        _evaluate_binding(binding, required_capabilities=required_capabilities)
        for binding in list_bindings_for_scope(scope_type=scope_type, scope_key=scope_key)
    ]
    candidates.sort(key=lambda candidate: candidate.score)
    return AlertmanagerSourceResolution(
        scope_type=scope_type,
        scope_key=scope_key,
        required_capabilities=required_capabilities,
        candidates=tuple(candidates),
    )


def _evaluate_binding(
    binding: AlertmanagerBinding,
    *,
    required_capabilities: tuple[str, ...],
) -> ResolvedAlertmanagerSource:
    instance = binding.instance
    readiness = (instance.readiness_status or '').strip().lower()
    health = (instance.last_status or '').strip().lower()
    observed_capabilities = set(instance.capabilities or ())
    missing = tuple(sorted(set(required_capabilities) - observed_capabilities))

    if not required_capabilities:
        capability_state = 'not_required'
        capability_rank = 0
        capability_eligible = True
    elif not observed_capabilities:
        # Existing migrated instances may predate capability probing. Keep them usable
        # during the compatibility window, but rank a positively verified source first.
        capability_state = 'unknown'
        capability_rank = 1
        capability_eligible = True
    elif missing:
        capability_state = 'missing_required'
        capability_rank = 2
        capability_eligible = False
    else:
        capability_state = 'verified'
        capability_rank = 0
        capability_eligible = True

    readiness_eligible = readiness not in _BLOCKED_READINESS
    eligible = bool(instance.enabled and binding.enabled and readiness_eligible and capability_eligible)
    operational_rank, operational_state = _operational_rank(readiness=readiness, health=health)
    role_rank = _ROLE_ORDER.get(binding.binding_role, 9)
    eligibility_rank = 0 if eligible else 1

    reason = _decision_reason(
        eligible=eligible,
        readiness=readiness,
        health=health,
        capability_state=capability_state,
        missing=missing,
    )
    return ResolvedAlertmanagerSource(
        instance=instance,
        binding=binding,
        eligible=eligible,
        capability_state=capability_state,
        missing_capabilities=missing,
        operational_state=operational_state,
        decision_reason=reason,
        score=(
            eligibility_rank,
            operational_rank,
            capability_rank,
            role_rank,
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
    missing: tuple[str, ...],
) -> str:
    if capability_state == 'missing_required':
        return f'Missing required capabilities: {", ".join(missing)}.'
    if readiness in _BLOCKED_READINESS:
        return f'Readiness state {readiness or "unknown"} blocks source selection.'
    if not eligible:
        return 'Source is not eligible for selection.'
    if capability_state == 'unknown':
        return 'Capability validation has not been observed; source remains available for compatibility.'
    if health in _FAILED_HEALTH:
        return 'Source is eligible but currently unhealthy; a healthier bound source is preferred.'
    if readiness in _DEGRADED_READINESS:
        return 'Source is usable with degraded readiness.'
    if readiness not in _READY_READINESS:
        return 'Source is usable but requires validation; a validated source is preferred.'
    return 'Source satisfies readiness, health, and capability requirements.'
