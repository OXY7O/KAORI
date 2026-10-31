"""Typed, evidence-qualified Secret → materialization → consumer lineage.

Provider Secret paths and similarly named workloads are never identity proofs.
This is an in-memory normalization/impact contract; authoritative producing
domains must supply committed, authorized reference evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

EdgeKind = Literal['secret_to_materialization', 'materialization_to_consumer']
LineageStatus = Literal['candidate', 'confirmed', 'rejected', 'conflict']
MaterializationKind = Literal[
    'kubernetes_secret',
    'csi_volume',
    'vault_agent_template',
    'ci_variable',
    'injection_session',
]
ConsumerKind = Literal[
    'kubernetes_workload',
    'service_environment',
    'ci_pipeline',
    'automation_runner',
    'integration_instance',
]
EvidenceKind = Literal['controller_uid', 'resource_uid', 'runtime_readback', 'approved_mapping']
SourceFreshness = Literal['ready', 'stale', 'partial', 'not_collected']


def _uuid(value: str) -> str:
    try:
        return str(UUID(value))
    except (TypeError, AttributeError, ValueError) as exc:
        raise ValueError('Lineage references must use canonical opaque UUID identities.') from exc


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError('Lineage time must contain an explicit timezone.')
    return value.astimezone(UTC)


@dataclass(frozen=True, slots=True)
class LineageEdge:
    """One typed directed edge with independently qualified evidence."""

    edge_id: str
    kind: EdgeKind
    from_id: str
    to_id: str
    resource_kind: MaterializationKind | ConsumerKind
    status: LineageStatus
    evidence_kind: EvidenceKind
    evidence_id: str
    effective_from: datetime
    effective_until: datetime | None
    observed_at: datetime

    def __post_init__(self) -> None:
        for value in (self.edge_id, self.from_id, self.to_id, self.evidence_id):
            _uuid(value)
        started = _aware(self.effective_from)
        observed = _aware(self.observed_at)
        if observed < started:
            raise ValueError('Lineage observation cannot precede effective start.')
        if self.effective_until is not None and _aware(self.effective_until) <= started:
            raise ValueError('Effective end must follow effective start.')
        if self.kind not in {'secret_to_materialization', 'materialization_to_consumer'}:
            raise ValueError('Unknown typed lineage edge.')
        if self.status not in {'candidate', 'confirmed', 'rejected', 'conflict'}:
            raise ValueError('Unknown lineage verification state.')
        if self.evidence_kind not in {
            'controller_uid',
            'resource_uid',
            'runtime_readback',
            'approved_mapping',
        }:
            raise ValueError('Unsupported lineage evidence type.')
        if self.kind == 'secret_to_materialization' and self.resource_kind not in {
            'kubernetes_secret',
            'csi_volume',
            'vault_agent_template',
            'ci_variable',
            'injection_session',
        }:
            raise ValueError('Secret source must point to a typed materialization.')
        if self.kind == 'materialization_to_consumer' and self.resource_kind not in {
            'kubernetes_workload',
            'service_environment',
            'ci_pipeline',
            'automation_runner',
            'integration_instance',
        }:
            raise ValueError('Materialization must point to a typed consumer.')
        if self.status == 'confirmed' and self.evidence_kind == 'approved_mapping':
            raise ValueError('A declared name/path mapping alone cannot confirm actual lineage.')
        if self.from_id == self.to_id:
            raise ValueError('Lineage edges cannot point to themselves.')


@dataclass(frozen=True, slots=True)
class LineageImpact:
    source_secret_id: str
    matching_materializations: int
    confirmed_consumers: tuple[str, ...]
    state: Literal['qualified_current', 'historical_only', 'not_proven']
    omitted_unqualified_edges: int


def _active(edge: LineageEdge, at: datetime) -> bool:
    now = _aware(at)
    return (
        _aware(edge.effective_from) <= now
        and (edge.effective_until is None or now < _aware(edge.effective_until))
        and _aware(edge.observed_at) <= now
    )


def project_secret_impact(
    *,
    secret_identity_id: str,
    edges: tuple[LineageEdge, ...],
    authorized_consumer_ids: frozenset[str],
    source_freshness: SourceFreshness,
    correlation_freshness: SourceFreshness,
    at: datetime,
) -> LineageImpact:
    """Only connected confirmed, effective, authorized edges count as impact.

    Source outages retain historical facts but cannot prove *current* exposure.
    Authorization is supplied by the owning domain, not inferred from edge
    existence, provider namespace, Secret path or user interface membership.
    """
    source_id = _uuid(secret_identity_id)
    _aware(at)
    if source_freshness not in {'ready', 'stale', 'partial', 'not_collected'} or correlation_freshness not in {
        'ready',
        'stale',
        'partial',
        'not_collected',
    }:
        raise ValueError('Unknown committed source/correlation freshness.')
    if len(edges) > 500 or len(authorized_consumer_ids) > 500:
        raise ValueError('Impact projection exceeds bounded correlation scope.')
    allowed = {_uuid(value) for value in authorized_consumer_ids}
    # Conflict/rejected/candidate edges are excluded, including when a second
    # contradictory edge exists for an otherwise confirmed connection.
    conflicted = {
        (edge.kind, edge.from_id, edge.to_id)
        for edge in edges
        if _active(edge, at) and edge.status in {'conflict', 'rejected'}
    }
    usable = [
        edge
        for edge in edges
        if _active(edge, at) and edge.status == 'confirmed' and (edge.kind, edge.from_id, edge.to_id) not in conflicted
    ]
    mats = {edge.to_id for edge in usable if edge.kind == 'secret_to_materialization' and edge.from_id == source_id}
    consumers = sorted(
        {
            edge.to_id
            for edge in usable
            if edge.kind == 'materialization_to_consumer' and edge.from_id in mats and edge.to_id in allowed
        }
    )
    if not consumers:
        state = 'not_proven'
    elif source_freshness == 'ready' and correlation_freshness == 'ready':
        state = 'qualified_current'
    else:
        state = 'historical_only'
    return LineageImpact(
        source_secret_id=source_id,
        matching_materializations=len(mats),
        confirmed_consumers=tuple(consumers),
        state=state,
        omitted_unqualified_edges=len(edges) - len(usable),
    )
