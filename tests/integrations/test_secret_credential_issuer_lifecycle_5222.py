"""Issuer transition shape only; no trust writer or operational authorization (#5222)."""

from datetime import UTC, datetime, timedelta
from hashlib import sha256

import pytest

from app.models.integration import IntegrationInstance
from app.models.secrets_pki import SecretCredentialIssuerRevision
from app.secrets_pki.credential_issuer_resolution import (
    issuer_proof_window_qualified,
    issuer_transition_shape_qualified,
)

_NOW = datetime(2026, 11, 26, 6, tzinfo=UTC)
_PUBLIC = bytes.fromhex('d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a')


def _source(**changes):
    values = {
        'id': 1,
        'integration_type': 'secrets_pki',
        'provider_key': 'openbao',
        'enabled': True,
        'lifecycle_status': 'active',
        'readiness_status': 'ready',
    }
    return IntegrationInstance(**(values | changes))


def _record(revision, state, **changes):
    values = {
        'integration_instance_id': 1,
        'provider_key': 'openbao',
        'provider_namespace': '',
        'mount': 'kv',
        'revision_number': revision,
        'lifecycle_status': state,
        'algorithm': 'ed25519',
        'public_key_hex': _PUBLIC.hex(),
        'key_sha256': sha256(_PUBLIC).hexdigest(),
        'deployment_ref': 'a' * 64,
        'evidence_ref': 'b' * 64,
        'requested_by_user_id': 1,
        'approved_by_user_id': None if state == 'draft' else 2,
        'approved_at': None if state == 'draft' else _NOW,
        'recorded_by_user_id': 1 if state == 'draft' else 2,
        'recorded_at': _NOW,
        'effective_from': _NOW - timedelta(minutes=1),
        'effective_until': _NOW + timedelta(hours=1),
    }
    return SecretCredentialIssuerRevision(**(values | changes))


def _qualify(candidate, latest=None, **changes):
    values = {
        'source': _source(),
        'latest': latest,
        'candidate': candidate,
        'expected_revision': 0 if latest is None else latest.revision_number,
        'current_deployment_ref': 'a' * 64,
        'key_history': () if latest is None else (latest,),
        'now': _NOW,
    }
    return issuer_transition_shape_qualified(**(values | changes))


def test_enrollment_and_independent_activation_shape():
    draft = _record(1, 'draft')
    assert _qualify(draft)
    assert _qualify(_record(2, 'active'), draft)
    assert not _qualify(_record(1, 'active'))


@pytest.mark.parametrize(
    'changes',
    [
        {'approved_by_user_id': 1, 'recorded_by_user_id': 1},
        {'approved_at': None},
        {'recorded_by_user_id': 3},
        {'requested_by_user_id': 3},
        {'key_sha256': 'c' * 64},
        {'evidence_ref': 'invalid'},
        {'deployment_ref': 'c' * 64},
        {'mount': 'other'},
        {'revision_number': 3},
        {'effective_until': _NOW + timedelta(hours=2)},
        {'approved_at': _NOW - timedelta(seconds=1)},
    ],
)
def test_activation_rejects_changed_or_unqualified_fields(changes):
    assert not _qualify(_record(2, 'active', **changes), _record(1, 'draft'))


def test_stale_or_incomplete_history_and_source_drift_denied():
    draft = _record(1, 'draft')
    active = _record(2, 'active')
    assert not _qualify(active, draft, expected_revision=0)
    assert not _qualify(active, draft, key_history=())
    assert not _qualify(active, draft, current_deployment_ref='c' * 64)
    assert not _qualify(active, draft, source=_source(enabled=False))
    assert not _qualify(active, draft, key_history=(draft, _record(1, 'draft', mount='other')))
    assert not _qualify(active, draft, key_history=(draft, _record(1, 'draft', deployment_ref='c' * 64)))


@pytest.mark.parametrize(
    'changes',
    [
        {'evidence_ref': 'c' * 64},
        {'requested_by_user_id': 3},
        {'lifecycle_status': 'active'},
        {'recorded_at': _NOW - timedelta(seconds=1)},
        {'effective_until': _NOW + timedelta(hours=2)},
    ],
)
def test_latest_snapshot_cannot_be_substituted_by_revision_number(changes):
    draft = _record(1, 'draft')
    history = _record(1, 'draft', **changes)
    assert not _qualify(_record(2, 'active'), draft, key_history=(history,))


def test_duplicate_history_and_malformed_draft_denied():
    draft = _record(1, 'draft')
    assert not _qualify(_record(2, 'active'), draft, key_history=(draft, draft))
    malformed = _record(1, 'draft', approved_by_user_id=2, approved_at=_NOW)
    assert not _qualify(_record(2, 'active'), malformed)


def test_revocation_terminal_and_reenrollment_requires_fresh_key():
    active = _record(2, 'active')
    revoked = _record(3, 'revoked')
    assert _qualify(revoked, active, source=_source(enabled=False))
    assert not _qualify(_record(3, 'draft'), active, key_history=())
    assert not _qualify(_record(4, 'active'), revoked)
    assert not _qualify(_record(4, 'draft'), revoked)
    assert not _qualify(_record(4, 'draft'), revoked, key_history=())
    fresh = bytes.fromhex('3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c')
    assert _qualify(
        _record(4, 'draft', public_key_hex=fresh.hex(), key_sha256=sha256(fresh).hexdigest()), revoked, key_history=()
    )


def test_expired_binding_can_be_revoked_but_not_activated():
    past = _NOW - timedelta(hours=2)
    window = {'effective_from': past - timedelta(hours=1), 'effective_until': past}
    active = _record(
        2, 'active', recorded_at=past - timedelta(minutes=1), approved_at=past - timedelta(minutes=1), **window
    )
    assert _qualify(_record(3, 'revoked', **window), active)
    assert not _qualify(_record(2, 'active', **window), _record(1, 'draft', **window))


def test_proof_must_be_contained_in_current_issuer_window():
    active = _record(2, 'active')
    expires = _NOW + timedelta(minutes=10)
    assert issuer_proof_window_qualified(active, issued_at=_NOW, expires_at=expires, now=_NOW)
    assert not issuer_proof_window_qualified(
        active, issued_at=_NOW - timedelta(seconds=1), expires_at=expires, now=_NOW
    )
    assert not issuer_proof_window_qualified(active, issued_at=_NOW, expires_at=_NOW + timedelta(hours=2), now=_NOW)
    assert not issuer_proof_window_qualified(_record(3, 'revoked'), issued_at=_NOW, expires_at=expires, now=_NOW)
