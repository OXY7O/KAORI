"""Offline custody evidence shape, not operational trust (#5224)."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from app.secrets_pki.credential_issuer_resolution import (
    IssuerCustodyEvidenceShape,
    IssuerResolutionTarget,
    issuer_custody_evidence_shape_qualified,
)

_NOW = datetime(2026, 11, 26, 8, tzinfo=UTC)
_CHALLENGE_TIME = _NOW - timedelta(minutes=10)
_TARGET = IssuerResolutionTarget(1, 'openbao', '', 'kv', 'a' * 64, 2)


def _evidence():
    return IssuerCustodyEvidenceShape(
        target=_TARGET,
        key_sha256='b' * 64,
        challenge_sha256='c' * 64,
        deployment_evidence_ref='d' * 64,
        possession_evidence_ref='e' * 64,
        custody_evidence_ref='f' * 64,
        access_decision_ref='1' * 64,
        source_owner_id=1,
        checker_id=2,
        issued_at=_NOW - timedelta(minutes=5),
        approved_at=_NOW,
        expires_at=_NOW + timedelta(minutes=10),
    )


def _qualify(evidence, **changes):
    values = {
        'target': _TARGET,
        'key_sha256': 'b' * 64,
        'expected_challenge_sha256': 'c' * 64,
        'challenge_issued_at': _CHALLENGE_TIME,
        'now': _NOW,
    }
    return issuer_custody_evidence_shape_qualified(evidence, **(values | changes))


def test_shape_only_for_both_providers():
    assert _qualify(_evidence())
    vault = replace(_TARGET, provider_key='vault')
    assert _qualify(replace(_evidence(), target=vault), target=vault)


@pytest.mark.parametrize(
    'changes',
    [
        {'provider_key': 'vault'},
        {'integration_instance_id': 2},
        {'provider_namespace': 'other'},
        {'mount': 'other'},
        {'deployment_ref': '2' * 64},
        {'revision_number': 3},
    ],
)
def test_different_target_denied(changes):
    assert not _qualify(replace(_evidence(), target=replace(_TARGET, **changes)))


@pytest.mark.parametrize(
    'changes',
    [
        {'key_sha256': '2' * 64},
        {'challenge_sha256': '2' * 64},
        {'deployment_evidence_ref': ''},
        {'possession_evidence_ref': ''},
        {'custody_evidence_ref': ''},
        {'access_decision_ref': ''},
        {'custody_evidence_ref': 'e' * 64},
        {'source_owner_id': 2},
        {'checker_id': 0},
        {'issued_at': _CHALLENGE_TIME - timedelta(seconds=1)},
        {'approved_at': _CHALLENGE_TIME},
        {'approved_at': _NOW + timedelta(seconds=1)},
        {'expires_at': _NOW},
        {'expires_at': _CHALLENGE_TIME + timedelta(hours=24, seconds=1)},
        {'expires_at': _NOW.replace(tzinfo=None)},
    ],
)
def test_invalid_evidence_shape_denied(changes):
    assert not _qualify(replace(_evidence(), **changes))


def test_changed_challenge_or_binding_denied():
    evidence = _evidence()
    assert not _qualify(evidence, expected_challenge_sha256='2' * 64)
    assert not _qualify(evidence, expected_challenge_sha256='')
    assert not _qualify(evidence, key_sha256='2' * 64)
    assert not _qualify(evidence, challenge_issued_at=_NOW)
    assert not _qualify(evidence, now=evidence.expires_at)


def test_invalid_scope_denied_even_when_matching():
    target = replace(_TARGET, mount='*')
    assert not _qualify(replace(_evidence(), target=target), target=target)
