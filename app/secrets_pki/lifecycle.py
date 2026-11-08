"""Secrets & PKI lifecycle facts, independent of Vault material and write APIs.

This module evaluates source-qualified facts; it NEVER infers completed Secret
rotation from a KV v2 version increment, or revocation from missing Lease data.
Policies and consumer readbacks must be persisted by a separately admitted,
authorized source workflow before becoming operating facts.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

VersionState = Literal['available', 'scheduled_deletion', 'soft_deleted', 'destroyed', 'unknown']
RotationState = Literal['not_configured', 'not_evaluated', 'awaiting_readback', 'verified']
LeaseState = Literal['unknown', 'observed', 'expiry_window_elapsed_unverified']


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError('Lifecycle evidence timestamp must contain an explicit timezone.')
    return value.astimezone(UTC)


def _uuid(value: str) -> str:
    try:
        return str(UUID(value))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError('Lifecycle identity must be an opaque UUID.') from exc


@dataclass(frozen=True, slots=True)
class RotationPolicyEvidence:
    """Versioned governance policy. This is not a Vault-native rotation rule."""

    policy_id: str
    policy_revision: int
    effective_at: datetime
    maximum_verified_rotation_age_days: int | None = None
    required_consumer_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _uuid(self.policy_id)
        _aware(self.effective_at)
        if self.policy_revision < 1:
            raise ValueError('Rotation policy revision must be positive.')
        if self.maximum_verified_rotation_age_days is not None and not (
            1 <= self.maximum_verified_rotation_age_days <= 3650
        ):
            raise ValueError('Rotation policy threshold must be explicitly bounded.')
        if len(self.required_consumer_ids) > 128:
            raise ValueError('Rotation consumer scope exceeds limit.')
        for key in self.required_consumer_ids:
            _uuid(key)
        if len(set(self.required_consumer_ids)) != len(self.required_consumer_ids):
            raise ValueError('Rotation consumer scope cannot contain duplicates.')


@dataclass(frozen=True, slots=True)
class ConsumerVersionReadback:
    consumer_id: str
    adopted_version: int
    verified_at: datetime
    source_kind: Literal['controller_readback', 'workload_readback']

    def __post_init__(self) -> None:
        _uuid(self.consumer_id)
        _aware(self.verified_at)
        if self.source_kind not in {'controller_readback', 'workload_readback'}:
            raise ValueError('Rotation readback source is not qualified.')
        if self.adopted_version < 1:
            raise ValueError('Consumer adoption version must be positive.')


@dataclass(frozen=True, slots=True)
class RotationTransitionEvidence:
    """A provider-side change is not equivalent to verified consumer cutover."""

    secret_identity_id: str
    target_version: int
    started_at: datetime
    policy: RotationPolicyEvidence | None
    readbacks: tuple[ConsumerVersionReadback, ...] = ()
    verified_rotation_at: datetime | None = None

    def __post_init__(self) -> None:
        _uuid(self.secret_identity_id)
        _aware(self.started_at)
        if self.target_version < 1:
            raise ValueError('Rotation target version must be positive.')
        if len(self.readbacks) > 256:
            raise ValueError('Rotation evidence exceeds consumer bound.')
        if self.verified_rotation_at is not None and _aware(self.verified_rotation_at) < _aware(self.started_at):
            raise ValueError('Verified rotation must follow transition start.')


@dataclass(frozen=True, slots=True)
class RotationAssessment:
    status: RotationState
    verified_at: datetime | None
    required_consumers: int
    verified_consumers: int
    overdue: bool | None


def assess_rotation(
    evidence: RotationTransitionEvidence,
    *,
    at: datetime,
) -> RotationAssessment:
    """No automatic success for a version increase or unqualified attestation."""
    now = _aware(at)
    policy = evidence.policy
    if policy is None or _aware(policy.effective_at) > now:
        return RotationAssessment('not_configured', None, 0, 0, None)
    required = set(policy.required_consumer_ids)
    matched = {
        entry.consumer_id
        for entry in evidence.readbacks
        if entry.consumer_id in required
        and entry.adopted_version == evidence.target_version
        and _aware(evidence.started_at) <= _aware(entry.verified_at) <= now
    }
    complete = bool(required) and matched == required
    attested_at = evidence.verified_rotation_at
    can_verify = (
        complete
        and attested_at is not None
        and _aware(evidence.started_at) <= _aware(attested_at) <= now
        and all(
            any(
                entry.consumer_id == consumer
                and entry.adopted_version == evidence.target_version
                and _aware(entry.verified_at) <= _aware(attested_at)
                and _aware(entry.verified_at) >= _aware(evidence.started_at)
                for entry in evidence.readbacks
            )
            for consumer in required
        )
    )
    if not can_verify or attested_at is None:
        return RotationAssessment(
            'awaiting_readback' if required else 'not_evaluated',
            None,
            len(required),
            len(matched),
            None,
        )
    verified_at = _aware(attested_at)
    threshold = policy.maximum_verified_rotation_age_days
    return RotationAssessment(
        'verified',
        verified_at,
        len(required),
        len(matched),
        now > verified_at + timedelta(days=threshold) if threshold is not None else None,
    )


def classify_kv2_version(
    *,
    destroyed: bool,
    deletion_time: str | None,
    observed_at: datetime,
) -> VersionState:
    """KV v2 deletion_time may be scheduled for a future instant."""
    observation_time = _aware(observed_at)
    if destroyed:
        return 'destroyed'
    if not deletion_time:
        return 'available'
    if len(deletion_time) > 80:
        return 'unknown'
    try:
        deletion_at = _aware(datetime.fromisoformat(deletion_time.replace('Z', '+00:00')))
    except ValueError:
        return 'unknown'
    return 'soft_deleted' if deletion_at <= observation_time else 'scheduled_deletion'


@dataclass(frozen=True, slots=True)
class KnownLeaseEvidence:
    """Lease metadata for a known source-owned identity, never the provider lease_id."""

    lease_identity_id: str
    observed_at: datetime
    expires_at: datetime | None
    renewable: bool | None
    source_kind: Literal['qualified_issuance_receipt', 'authorized_known_lease_lookup']
    ttl_seconds: int | None

    def __post_init__(self) -> None:
        _uuid(self.lease_identity_id)
        _aware(self.observed_at)
        if self.expires_at is not None:
            _aware(self.expires_at)
        if self.source_kind not in {'qualified_issuance_receipt', 'authorized_known_lease_lookup'}:
            raise ValueError('Lease observation source is not qualified.')
        if self.renewable is not None and not isinstance(self.renewable, bool):
            raise ValueError('Lease renewability must be qualified or unknown.')
        if self.ttl_seconds is not None and not (0 <= self.ttl_seconds <= 315_360_000):
            raise ValueError('Lease TTL exceeds normalized bound.')


@dataclass(frozen=True, slots=True)
class LeaseAssessment:
    status: LeaseState
    observed_at: datetime | None
    expiry_window: datetime | None
    renewable: bool | None
    coverage: Literal['single_known_lease', 'none']


def assess_known_lease(
    evidence: KnownLeaseEvidence | None,
    *,
    at: datetime,
) -> LeaseAssessment:
    """Elapsed expiry is not proof of revocation, renewal, or dynamic credential deletion."""
    now = _aware(at)
    if evidence is None or _aware(evidence.observed_at) > now:
        return LeaseAssessment('unknown', None, None, None, 'none')
    deadline = _aware(evidence.expires_at) if evidence.expires_at else None
    if deadline is None:
        return LeaseAssessment('unknown', _aware(evidence.observed_at), None, evidence.renewable, 'single_known_lease')
    return LeaseAssessment(
        'expiry_window_elapsed_unverified' if deadline <= now else 'observed',
        _aware(evidence.observed_at),
        deadline,
        evidence.renewable,
        'single_known_lease',
    )
