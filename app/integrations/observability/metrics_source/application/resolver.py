from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from app.integrations.binding_selectors import selector_is_configured
from app.integrations.observability.metrics_source.routing import normalize_routing_policy, routing_rank
from app.integrations.resolver import resolve_integration
from app.models.integration import IntegrationBinding
from app.models.metrics_source import MetricsSource

_ROLE_ORDER: Final[dict[str, int]] = {
    'primary': 0,
    'secondary': 1,
    'fallback': 2,
}
_READY_READINESS: Final[set[str]] = {'ready'}
_DEGRADED_READINESS: Final[set[str]] = {'degraded'}
_FAILED_HEALTH: Final[set[str]] = {'disconnected', 'error', 'failed', 'incompatible', 'unhealthy'}
_ELIGIBLE_BINDING_VALIDATION: Final[set[str]] = {'ready'}


@dataclass(frozen=True, slots=True)
class ResolvedMetricsSource:
    instance: MetricsSource
    binding: IntegrationBinding
    eligible: bool
    capability_state: str
    missing_binding_capabilities: tuple[str, ...]
    missing_technical_capabilities: tuple[str, ...]
    operational_state: str
    decision_reason: str
    query_horizon: str
    routing_weight: int
    provider_key: str
    score: tuple[int, int, int, int, int, int, int, int]


@dataclass(frozen=True, slots=True)
class MetricsSourceResolution:
    scope_type: str
    scope_key: str
    required_binding_capabilities: tuple[str, ...]
    required_technical_capabilities: tuple[str, ...]
    candidates: tuple[ResolvedMetricsSource, ...]

    @property
    def eligible_candidates(self) -> tuple[ResolvedMetricsSource, ...]:
        return tuple(candidate for candidate in self.candidates if candidate.eligible)

    @property
    def selected(self) -> ResolvedMetricsSource | None:
        return self.eligible_candidates[0] if self.eligible_candidates else None


def resolve_metrics_sources(
    *,
    scope_type: str,
    scope_key: str,
    required_binding_capabilities: tuple[str, ...] = (),
    required_technical_capabilities: tuple[str, ...] = (),
    query_horizon: str = 'balanced',
) -> MetricsSourceResolution:
    canonical = resolve_integration(
        integration_type='metrics_source',
        asset_type=scope_type,
        asset_key=scope_key,
        required_capabilities=required_binding_capabilities,
    )
    candidates: list[ResolvedMetricsSource] = []
    for item in canonical.candidates:
        provider_instance = MetricsSource.query.filter_by(
            integration_instance_id=item.instance.id,
        ).first()
        if provider_instance is None:
            continue
        effective_binding_scope = set(item.binding.capability_scope or ())
        missing_binding_capabilities = tuple(sorted(set(required_binding_capabilities) - effective_binding_scope))
        candidates.append(
            _evaluate_binding(
                item.binding,
                provider_instance,
                missing_binding_capabilities=missing_binding_capabilities,
                required_technical_capabilities=required_technical_capabilities,
                query_horizon=query_horizon,
            )
        )
    candidates.sort(key=lambda candidate: candidate.score)
    return MetricsSourceResolution(
        scope_type=scope_type,
        scope_key=str(scope_key),
        required_binding_capabilities=required_binding_capabilities,
        required_technical_capabilities=required_technical_capabilities,
        candidates=tuple(candidates),
    )


def _evaluate_binding(
    binding: IntegrationBinding,
    instance: MetricsSource,
    *,
    missing_binding_capabilities: tuple[str, ...],
    required_technical_capabilities: tuple[str, ...],
    query_horizon: str,
) -> ResolvedMetricsSource:
    readiness = (instance.readiness_status or '').strip().lower()
    health = (instance.last_status or '').strip().lower()
    observed = _available_technical_capabilities(binding, instance)
    missing_technical = tuple(sorted(set(required_technical_capabilities) - observed))

    if not required_technical_capabilities:
        capability_state = 'not_required'
        capability_rank = 0
        technical_eligible = True
    elif not observed:
        capability_state = 'validation_required'
        capability_rank = 2
        technical_eligible = False
    elif missing_technical:
        capability_state = 'missing_required'
        capability_rank = 2
        technical_eligible = False
    else:
        capability_state = 'verified'
        capability_rank = 0
        technical_eligible = True

    selector_required = _selector_required(binding)
    selector_eligible = not selector_required or selector_is_configured(binding.selector_json)
    binding_validation = (binding.validation_status or 'validation_required').strip().lower()
    binding_validation_eligible = binding_validation in _ELIGIBLE_BINDING_VALIDATION
    binding_eligible = not missing_binding_capabilities and selector_eligible and binding_validation_eligible
    readiness_eligible = readiness in (_READY_READINESS | _DEGRADED_READINESS)
    eligible = bool(
        instance.enabled and binding.enabled and binding_eligible and readiness_eligible and technical_eligible
    )
    operational_rank, operational_state = _operational_rank(readiness=readiness, health=health)
    routing_policy = normalize_routing_policy(binding.routing_policy)
    horizon_rank, weight_rank = routing_rank(routing_policy, requested_horizon=query_horizon)
    reason = _decision_reason(
        eligible=eligible,
        readiness=readiness,
        health=health,
        capability_state=capability_state,
        missing_binding=missing_binding_capabilities,
        selector_required=selector_required,
        selector_eligible=selector_eligible,
        binding_validation=binding_validation,
        binding_validation_eligible=binding_validation_eligible,
        missing_technical=missing_technical,
    )
    return ResolvedMetricsSource(
        instance=instance,
        binding=binding,
        eligible=eligible,
        capability_state=capability_state,
        missing_binding_capabilities=missing_binding_capabilities,
        missing_technical_capabilities=missing_technical,
        operational_state=operational_state,
        decision_reason=reason,
        query_horizon=str(routing_policy['query_horizon']),
        routing_weight=int(routing_policy['weight']),
        provider_key=str(instance.provider_key),
        score=(
            0 if eligible else 1,
            operational_rank,
            horizon_rank,
            _ROLE_ORDER.get(binding.binding_role, 9),
            weight_rank,
            capability_rank,
            binding.priority,
            binding.id,
        ),
    )


def _available_technical_capabilities(
    binding: IntegrationBinding,
    instance: MetricsSource,
) -> set[str]:
    """Merge provider-core transport evidence with binding-owned consumer evidence."""
    provider_payload = instance.capabilities or {}
    binding_payload = binding.validation_evidence or {}
    observed: set[str] = {str(item) for item in (provider_payload.get('available') or ()) if item}
    observed.update(
        str(item.get('key'))
        for item in (provider_payload.get('assessments') or ())
        if isinstance(item, dict)
        and item.get('key')
        and str(item.get('status') or '').strip().lower() in {'available', 'ready'}
    )
    observed.update(str(item) for item in (binding_payload.get('available_capabilities') or ()) if item)
    observed.update(
        str(item.get('key'))
        for item in (binding_payload.get('capability_assessments') or ())
        if isinstance(item, dict)
        and item.get('key')
        and str(item.get('status') or '').strip().lower() in {'available', 'ready'}
    )
    return observed


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
    selector_required: bool,
    selector_eligible: bool,
    binding_validation: str,
    binding_validation_eligible: bool,
) -> str:
    if selector_required and not selector_eligible:
        return 'Shared metrics sources require a binding selector to isolate metrics for this scope.'
    if not binding_validation_eligible:
        return (
            f'Binding validation state {binding_validation or "validation_required"} blocks source selection. '
            'Validate the scope selector before operational use.'
        )
    if missing_binding:
        return f'Missing binding coverage: {", ".join(missing_binding)}.'
    if capability_state == 'validation_required':
        return 'Required consumer capability evidence has not been recorded on this binding. Validate the consumer binding before operational use.'
    if capability_state == 'missing_required':
        return f'Missing validated consumer capabilities: {", ".join(missing_technical)}.'
    if readiness not in (_READY_READINESS | _DEGRADED_READINESS):
        return f'Readiness state {readiness or "validation_required"} blocks source selection. Run Full Validation.'
    if not eligible:
        return 'Source is not eligible for selection.'
    if health in _FAILED_HEALTH:
        return 'Source is eligible but currently unhealthy; a healthier bound source is preferred.'
    if readiness in _DEGRADED_READINESS:
        return 'Source is usable with degraded readiness.'
    return 'Source satisfies readiness, runtime health, binding coverage, and technical capability requirements.'


def _selector_required(binding: IntegrationBinding) -> bool:
    return (
        IntegrationBinding.query.filter_by(
            integration_instance_id=binding.integration_instance_id,
            enabled=True,
        ).count()
        > 1
    )
