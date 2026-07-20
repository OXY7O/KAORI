from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from app.integrations.binding_selectors import selector_is_configured
from app.integrations.resolver import resolve_integration
from app.models.alertmanager import AlertmanagerInstance
from app.models.integration import IntegrationBinding

_ROLE_ORDER: Final[dict[str, int]] = {
    'primary': 0,
    'secondary': 1,
    'fallback': 2,
}
_BLOCKED_READINESS: Final[set[str]] = {'blocked', 'unavailable', 'disabled', 'incompatible'}
_READY_READINESS: Final[set[str]] = {'ready'}
_DEGRADED_READINESS: Final[set[str]] = {'degraded'}
_FAILED_HEALTH: Final[set[str]] = {'disconnected', 'error', 'incompatible'}
_ELIGIBLE_BINDING_VALIDATION: Final[set[str]] = {'ready', 'legacy_unscoped'}


@dataclass(frozen=True, slots=True)
class ResolvedAlertmanagerSource:
    instance: AlertmanagerInstance
    binding: IntegrationBinding
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
    canonical = resolve_integration(
        provider_type='alertmanager',
        asset_type=scope_type,
        asset_key=scope_key,
        required_capabilities=required_capabilities,
    )
    candidates: list[ResolvedAlertmanagerSource] = []
    for item in canonical.candidates:
        provider_instance = AlertmanagerInstance.query.filter_by(
            integration_instance_id=item.instance.id,
        ).first()
        if provider_instance is None:
            continue
        candidates.append(
            _evaluate_binding(
                item.binding,
                provider_instance,
                required_capabilities=required_capabilities,
            )
        )
    candidates.sort(key=lambda candidate: candidate.score)
    return AlertmanagerSourceResolution(
        scope_type=scope_type,
        scope_key=scope_key,
        required_capabilities=required_capabilities,
        candidates=tuple(candidates),
    )


def _evaluate_binding(
    binding: IntegrationBinding,
    instance: AlertmanagerInstance,
    *,
    required_capabilities: tuple[str, ...],
) -> ResolvedAlertmanagerSource:
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

    selector_required = _selector_required(binding)
    selector_eligible = not selector_required or selector_is_configured(binding.selector_json)
    binding_validation = (binding.validation_status or 'validation_required').strip().lower()
    binding_validation_eligible = binding_validation in _ELIGIBLE_BINDING_VALIDATION
    readiness_eligible = readiness not in _BLOCKED_READINESS
    eligible = bool(
        instance.enabled
        and binding.enabled
        and readiness_eligible
        and capability_eligible
        and selector_eligible
        and binding_validation_eligible
    )
    operational_rank, operational_state = _operational_rank(readiness=readiness, health=health)
    role_rank = _ROLE_ORDER.get(binding.binding_role, 9)
    eligibility_rank = 0 if eligible else 1

    reason = _decision_reason(
        eligible=eligible,
        readiness=readiness,
        health=health,
        capability_state=capability_state,
        missing=missing,
        selector_required=selector_required,
        selector_eligible=selector_eligible,
        binding_validation=binding_validation,
        binding_validation_eligible=binding_validation_eligible,
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
    selector_required: bool,
    selector_eligible: bool,
    binding_validation: str,
    binding_validation_eligible: bool,
) -> str:
    if selector_required and not selector_eligible:
        return 'Shared Alertmanager sources require a binding selector to isolate alerts for this scope.'
    if not binding_validation_eligible:
        return (
            f'Binding validation state {binding_validation or "validation_required"} blocks source selection. '
            'Validate the scope selector before operational use.'
        )
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


def _selector_required(binding: IntegrationBinding) -> bool:
    return (
        IntegrationBinding.query.filter_by(
            integration_instance_id=binding.integration_instance_id,
            enabled=True,
        ).count() > 1
    )
