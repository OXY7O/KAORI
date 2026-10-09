from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.kubernetes.tenant.release_handoff_approval import (
    _can_confirm_plan,
    _complete_provider_snapshot,
    _valid_reference,
    approve_release_handoff_plan_committed,
)


def _snapshot(*, status: str = 'blocked', blockers: list[str] | None = None) -> dict:
    return {
        'tenant_id': 'tenant-a',
        'cluster_id': 'cluster-a',
        'generation': 2,
        'provider': 'native_kubernetes',
        'status': status,
        'checked_at': datetime.now(UTC).isoformat(),
        'handoff_fingerprint': 'a' * 64,
        'live_provider_identity': [
            {
                'kind': 'Namespace',
                'name': 'sandbox',
                'uid': 'namespace-uid',
                'resource_version': '5',
            }
        ],
        'handoff_components': [
            {
                'kind': 'Namespace', 'name': 'sandbox', 'uid': 'namespace-uid',
                'resource_version': '5', 'handoff': 'external_acceptance_required',
                'ownership': 'kaori_marker_correlated',
            }
        ],
        'handoff_required_count': 1,
        'dependency_counts': {
            'Access Grants': 0, 'credentials': 0, 'Memberships': 0,
            'enabled Groups': 0, 'advanced capabilities': 0,
        },
        'blockers': blockers if blockers is not None else [
            'Adoption performed KAORI-owned provider mutations. '
            'Complete independently verified allocation/policy handoff before Release.',
            'sandbox KAORI-linked allocation ownership requires independently approved '
            'external handoff and provider read-back.',
        ],
    }


def test_handoff_plan_acceptance_requires_only_expected_handoff_blockers():
    _can_confirm_plan(_snapshot())


@pytest.mark.parametrize('blocker', [
    'Namespace/sandbox provider UID mismatch.',
    'External Capsule access observation is stale.',
    'Native provider is unavailable.',
    'sandbox allocation hash changed since committed KAORI evidence.',
    'sandbox has inconsistent provider ownership markers.',
])
def test_handoff_approval_blocks_other_governance_or_provider_failures(blocker):
    with pytest.raises(ValueError, match='Unresolved'):
        _can_confirm_plan(_snapshot(blockers=[blocker]))


def test_handoff_approval_rejects_active_dependencies():
    snapshot = _snapshot()
    snapshot['dependency_counts']['Access Grants'] = 1
    with pytest.raises(ValueError, match='Clear all active'):
        _can_confirm_plan(snapshot)


def test_handoff_approval_rejects_foreign_or_unverified_ownership():
    snapshot = _snapshot()
    snapshot['handoff_components'][0]['handoff'] = 'owner_review_required'
    with pytest.raises(ValueError, match='Conflicting provider ownership'):
        _can_confirm_plan(snapshot)

    snapshot['handoff_components'][0]['handoff'] = 'observe_only'
    with pytest.raises(ValueError, match='No verified KAORI-linked resource'):
        _can_confirm_plan(snapshot)


def test_handoff_evidence_requires_all_correlated_namespace_identities():
    snapshot = _snapshot()
    snapshot['live_provider_identity'].append({
        'kind': 'Namespace', 'name': 'second', 'uid': 'other',
        'resource_version': '1',
    })
    with pytest.raises(ValueError, match='coverage'):
        _complete_provider_snapshot(snapshot)


def test_handoff_evidence_rejects_stale_and_incomplete_provider_metadata():
    snapshot = _snapshot()
    snapshot['checked_at'] = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    with pytest.raises(ValueError, match='Refresh'):
        _complete_provider_snapshot(snapshot)

    snapshot = _snapshot()
    snapshot['handoff_components'][0]['uid'] = ''
    with pytest.raises(ValueError, match='incomplete'):
        _complete_provider_snapshot(snapshot)


def test_handoff_owner_and_change_references_are_bounded_and_nonsecret():
    assert _valid_reference('platform-team', name='Successor') == 'platform-team'
    assert _valid_reference('CHG-2026-109', name='Change') == 'CHG-2026-109'
    for value in ('', 'ab', 'space separated', '<script>', 'x' * 121):
        with pytest.raises(ValueError):
            _valid_reference(value, name='Successor')


def test_second_approver_cannot_be_handoff_requester(monkeypatch):
    from app.kubernetes.tenant import release_handoff_approval as module

    monkeypatch.setattr(
        module, 'latest_release_handoff_plan',
        lambda _: {
            'status': 'pending_independent_approval',
            'plan_sha256': 'a' * 64,
            'requested_by': 42,
            'requested_at': datetime.now(UTC).isoformat(),
        },
    )
    with pytest.raises(ValueError, match='independent approver'):
        approve_release_handoff_plan_committed(
            tenant_id='tenant-a', actor_user_id=42,
            plan_sha256='a' * 64, approved=True,
        )


def test_second_approver_requires_same_latest_plan_and_fresh_window(monkeypatch):
    from app.kubernetes.tenant import release_handoff_approval as module

    plan = {
        'status': 'pending_independent_approval',
        'plan_sha256': 'a' * 64,
        'requested_by': 42,
        'requested_at': datetime.now(UTC).isoformat(),
    }
    monkeypatch.setattr(module, 'latest_release_handoff_plan', lambda _: plan)
    with pytest.raises(ValueError, match='plan changed'):
        approve_release_handoff_plan_committed(
            tenant_id='tenant-a', actor_user_id=43,
            plan_sha256='b' * 64, approved=True,
        )
    plan['requested_at'] = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
    with pytest.raises(ValueError, match='expired'):
        approve_release_handoff_plan_committed(
            tenant_id='tenant-a', actor_user_id=43,
            plan_sha256='a' * 64, approved=True,
        )


def test_second_approver_requires_explicit_acknowledgement():
    with pytest.raises(ValueError, match='acknowledgement'):
        approve_release_handoff_plan_committed(
            tenant_id='tenant-a', actor_user_id=43,
            plan_sha256='a' * 64, approved=False,
        )
