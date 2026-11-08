"""Secrets & PKI lifecycle evidence is not a Vault mutation or inference engine."""

from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.secrets_pki.lifecycle import (
    ConsumerVersionReadback,
    KnownLeaseEvidence,
    RotationPolicyEvidence,
    RotationTransitionEvidence,
    assess_known_lease,
    assess_rotation,
    classify_kv2_version,
)


def _id() -> str:
    return str(uuid4())


def test_kv2_future_deletion_time_is_scheduled_not_soft_deleted():
    at = datetime(2026, 10, 22, tzinfo=UTC)
    assert (
        classify_kv2_version(
            destroyed=False,
            deletion_time='2026-10-23T00:00:00Z',
            observed_at=at,
        )
        == 'scheduled_deletion'
    )
    assert (
        classify_kv2_version(
            destroyed=False,
            deletion_time='2026-10-21T00:00:00Z',
            observed_at=at,
        )
        == 'soft_deleted'
    )
    assert (
        classify_kv2_version(
            destroyed=True,
            deletion_time=None,
            observed_at=at,
        )
        == 'destroyed'
    )
    assert (
        classify_kv2_version(
            destroyed=False,
            deletion_time=None,
            observed_at=at,
        )
        == 'available'
    )
    assert (
        classify_kv2_version(
            destroyed=False,
            deletion_time='invalid',
            observed_at=at,
        )
        == 'unknown'
    )


def test_kv2_version_increment_without_readback_cannot_claim_rotated():
    now = datetime(2026, 10, 22, tzinfo=UTC)
    consumer = _id()
    policy = RotationPolicyEvidence(
        policy_id=_id(),
        policy_revision=1,
        effective_at=now - timedelta(days=90),
        maximum_verified_rotation_age_days=30,
        required_consumer_ids=(consumer,),
    )
    candidate = RotationTransitionEvidence(
        secret_identity_id=_id(),
        target_version=9,
        started_at=now - timedelta(days=50),
        policy=policy,
    )
    assessment = assess_rotation(candidate, at=now)
    assert assessment.status == 'awaiting_readback'
    assert assessment.overdue is None
    unverified = replace(
        candidate,
        readbacks=(
            ConsumerVersionReadback(
                consumer_id=consumer,
                adopted_version=9,
                verified_at=now - timedelta(days=45),
                source_kind='controller_readback',
            ),
        ),
    )
    assert assess_rotation(unverified, at=now).status == 'awaiting_readback'
    verified = replace(unverified, verified_rotation_at=now - timedelta(days=45))
    assessment = assess_rotation(verified, at=now)
    assert assessment.status == 'verified'
    assert assessment.verified_consumers == 1
    assert assessment.overdue is True


def test_rotation_requires_all_policy_consumers_after_transition_and_correct_version():
    at = datetime(2026, 10, 22, tzinfo=UTC)
    a, b = _id(), _id()
    policy = RotationPolicyEvidence(
        policy_id=_id(),
        policy_revision=2,
        effective_at=at - timedelta(days=5),
        required_consumer_ids=(a, b),
    )
    transition = RotationTransitionEvidence(
        secret_identity_id=_id(),
        target_version=3,
        started_at=at - timedelta(days=3),
        policy=policy,
        readbacks=(
            ConsumerVersionReadback(
                consumer_id=a,
                adopted_version=3,
                verified_at=at - timedelta(days=1),
                source_kind='workload_readback',
            ),
        ),
        verified_rotation_at=at,
    )
    assert assess_rotation(transition, at=at).status == 'awaiting_readback'
    wrong = replace(
        transition,
        readbacks=(
            *transition.readbacks,
            ConsumerVersionReadback(
                consumer_id=b,
                adopted_version=2,
                verified_at=at - timedelta(days=1),
                source_kind='controller_readback',
            ),
        ),
    )
    assert assess_rotation(wrong, at=at).verified_consumers == 1
    right = replace(
        wrong,
        readbacks=(
            transition.readbacks[0],
            ConsumerVersionReadback(
                consumer_id=b,
                adopted_version=3,
                verified_at=at - timedelta(days=1),
                source_kind='controller_readback',
            ),
        ),
    )
    assert assess_rotation(right, at=at).status == 'verified'


def test_no_policy_never_assumes_rotation_cadence():
    at = datetime(2026, 10, 22, tzinfo=UTC)
    evidence = RotationTransitionEvidence(
        secret_identity_id=_id(),
        target_version=8,
        started_at=at,
        policy=None,
    )
    assert assess_rotation(evidence, at=at).status == 'not_configured'


def test_known_lease_expiry_is_unverified_not_revocation():
    at = datetime(2026, 10, 22, tzinfo=UTC)
    lease = KnownLeaseEvidence(
        lease_identity_id=_id(),
        observed_at=at - timedelta(hours=2),
        expires_at=at - timedelta(minutes=30),
        renewable=True,
        source_kind='qualified_issuance_receipt',
        ttl_seconds=3600,
    )
    state = assess_known_lease(lease, at=at)
    assert state.status == 'expiry_window_elapsed_unverified'
    assert state.coverage == 'single_known_lease'
    assert asdict(state).get('revoked') is None
    assert 'lease_id' not in asdict(lease)
    assert assess_known_lease(None, at=at).status == 'unknown'


def test_bad_lease_identity_and_unbounded_ttl_are_rejected():
    now = datetime(2026, 10, 22, tzinfo=UTC)
    with pytest.raises(ValueError, match='opaque UUID'):
        KnownLeaseEvidence(
            lease_identity_id='aws/creds/role/private-provider-lease-id',
            observed_at=now,
            expires_at=None,
            renewable=True,
            source_kind='authorized_known_lease_lookup',
            ttl_seconds=3600,
        )
    with pytest.raises(ValueError, match='TTL'):
        KnownLeaseEvidence(
            lease_identity_id=_id(),
            observed_at=now,
            expires_at=None,
            renewable=True,
            source_kind='authorized_known_lease_lookup',
            ttl_seconds=999_999_999,
        )


def test_naive_timestamp_cannot_enter_lease_or_rotation_evidence():
    now = datetime(2026, 10, 22, tzinfo=UTC)
    with pytest.raises(ValueError, match='timezone'):
        KnownLeaseEvidence(
            lease_identity_id=_id(),
            observed_at=now.replace(tzinfo=None),
            expires_at=None,
            renewable=None,
            source_kind='qualified_issuance_receipt',
            ttl_seconds=None,
        )
