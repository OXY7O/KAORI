"""Synthetic provider metadata and independently pinned receipt qualification (#5245)."""

from __future__ import annotations

import base64
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.access.scope_policy import CredentialIssuerScope
from app.integrations.secrets_management.secrets_pki.providers.credential_version_proof import (
    CredentialVersionSelector,
    ProviderCredentialVersionSelector,
    canonical_statement,
    provider_credential_version_statement,
)
from app.integrations.secrets_management.secrets_pki.providers.issuer_transit import (
    TransitIssuerBinding,
    TransitIssuerObservation,
    decode_transit_signature,
    qualify_transit_public_key,
)
from app.secrets_pki import issuer_authority
from app.secrets_pki.credential_issuer_resolution import IssuerPossessionChallenge, IssuerResolutionTarget

_NOW = datetime(2026, 11, 27, 6, tzinfo=UTC)
_ROOT = Ed25519PrivateKey.from_private_bytes(b'\x01' * 32)
_ISSUER = Ed25519PrivateKey.from_private_bytes(b'\x02' * 32)
_PUBLIC = _ISSUER.public_key().public_bytes_raw()
_KEY_DIGEST = sha256(_PUBLIC).hexdigest()
_CHALLENGE = 'c' * 64


def _binding(provider='openbao'):
    return TransitIssuerBinding(
        provider, 'https://fixture.invalid', 'cluster-fixture', '', 'transit', 'issuer', 1, _KEY_DIGEST
    )


def _metadata():
    return {
        'name': 'issuer',
        'type': 'ed25519',
        'supports_signing': True,
        'derived': False,
        'exportable': False,
        'allow_plaintext_backup': False,
        'deletion_allowed': False,
        'imported_key': False,
        'auto_rotate_period': 0,
        'latest_version': 1,
        'min_decryption_version': 1,
        'min_encryption_version': 0,
        'keys': {'1': {'public_key': base64.b64encode(_PUBLIC).decode('ascii')}},
    }


@pytest.mark.parametrize('provider', ['openbao', 'vault'])
def test_native_key_metadata_is_provider_version_bound(provider):
    assert qualify_transit_public_key(_metadata(), _binding(provider)) == _PUBLIC


@pytest.mark.parametrize(
    'changes',
    [
        {'type': 'rsa-2048'},
        {'derived': True},
        {'exportable': True},
        {'allow_plaintext_backup': True},
        {'deletion_allowed': True},
        {'imported_key': True},
        {'auto_rotate_period': 3600},
        {'auto_rotate_period': False},
        {'latest_version': 2},
        {'latest_version': True},
        {'min_decryption_version': 2},
        {'min_encryption_version': 2},
        {'supports_signing': False},
        {'name': 'other'},
        {'keys': {}},
        {'keys': {'1': {'public_key': 'not-base64'}}},
        {'keys': {'1': {'public_key': base64.b64encode(b'x' * 32).decode('ascii')}}},
    ],
)
def test_unsafe_missing_or_rotated_native_key_is_denied(changes):
    assert qualify_transit_public_key(_metadata() | changes, _binding()) is None


def test_missing_policy_flag_is_not_safe_default():
    metadata = _metadata()
    del metadata['exportable']
    assert qualify_transit_public_key(metadata, _binding()) is None


def test_signature_decoding_requires_exact_native_version():
    signature = _ISSUER.sign(b'fixture-only')
    encoded = base64.b64encode(signature).decode('ascii')
    assert decode_transit_signature(f'vault:v1:{encoded}', key_version=1) == signature
    for value in (f'vault:v2:{encoded}', f'vault:v01:{encoded}', encoded, f'vault:v1:{encoded} '):
        assert decode_transit_signature(value, key_version=1) is None


def _envelope(payload, key=_ROOT):
    return canonical_statement({'payload': payload, 'signature': key.sign(canonical_statement(payload)).hex()})


def _times():
    return {
        'issued_at': (_NOW - timedelta(minutes=1)).isoformat(),
        'expires_at': (_NOW + timedelta(minutes=4)).isoformat(),
    }


@pytest.fixture
def authority_files(monkeypatch):
    # Synthetic trust root, no real filesystem deployment or provider.
    transit = _binding()
    scope = CredentialIssuerScope(1, 'openbao', '', 'kv', 'a' * 64)
    scope = replace(scope, deployment_ref=issuer_authority.deployment_identity_ref(scope, transit))
    deployment = {
        'schema': 'kaori.secrets.issuer_deployment.v1',
        'state': 'active',
        'scope': asdict(scope),
        'transit': asdict(transit),
        'key_sha256': _KEY_DIGEST,
        'source_owner_id': 1,
        'checker_id': 2,
        **_times(),
    }
    deployment_file = f'deployment-{scope.deployment_ref}.json'
    files = {
        'root.pub': _ROOT.public_key().public_bytes_raw().hex().encode('ascii'),
        deployment_file: _envelope(deployment),
    }
    custody = {
        'schema': 'kaori.secrets.issuer_custody.v1',
        'state': 'active',
        'deployment_evidence_ref': sha256(files[deployment_file]).hexdigest(),
        'key_sha256': _KEY_DIGEST,
        'revision_number': 2,
        'challenge_sha256': _CHALLENGE,
        'source_owner_id': 1,
        'checker_id': 2,
        **_times(),
    }
    custody_file = f'custody-{_CHALLENGE}.json'
    files[custody_file] = _envelope(custody)
    monkeypatch.setattr(issuer_authority, '_read_authority_file', files.get)
    expected = IssuerPossessionChallenge(
        IssuerResolutionTarget(1, 'openbao', '', 'kv', scope.deployment_ref, 2),
        _KEY_DIGEST,
        _CHALLENGE,
        1,
        _NOW - timedelta(minutes=2),
        _NOW + timedelta(minutes=8),
    )
    observation = TransitIssuerObservation(transit, _PUBLIC.hex(), _NOW)
    return files, scope, deployment_file, deployment, custody_file, custody, expected, observation


def _resolve(fixture, *, checker=2, observation=None, now=_NOW):
    return issuer_authority.resolve_custody_authority(
        fixture[6], checker_id=checker, observation=observation or fixture[7], now=now
    )


def test_current_independent_deployment_and_custody_receipts(authority_files):
    files, scope, deployment_file, _, custody_file, _, _, _ = authority_files
    deployment = issuer_authority.resolve_deployment_authority(scope, now=_NOW)
    assert deployment is not None
    assert deployment.evidence_ref == sha256(files[deployment_file]).hexdigest()
    custody = _resolve(authority_files)
    assert custody is not None
    assert custody.evidence_ref == sha256(files[custody_file]).hexdigest()
    # Revocation/removal is re-read, not cached.
    del files[custody_file]
    assert _resolve(authority_files) is None


@pytest.mark.parametrize(
    'changes',
    [
        {'state': 'revoked'},
        {'revision_number': 3},
        {'challenge_sha256': 'd' * 64},
        {'checker_id': 1},
        {'source_owner_id': 9},
        {'key_sha256': 'e' * 64},
        {'deployment_evidence_ref': 'f' * 64},
        {'expires_at': _NOW.isoformat()},
        {'issued_at': (_NOW + timedelta(seconds=1)).isoformat()},
        {'extra': 'not-in-schema'},
    ],
)
def test_signed_but_wrong_custody_receipt_denied(authority_files, changes):
    files, _, _, _, custody_file, custody, _, _ = authority_files
    files[custody_file] = _envelope(custody | changes)
    assert _resolve(authority_files) is None


def test_wrong_signing_authority_or_missing_pin_denied(authority_files):
    files, _, _, _, custody_file, custody, _, _ = authority_files
    files[custody_file] = _envelope(custody, _ISSUER)
    assert _resolve(authority_files) is None
    files[custody_file] = _envelope(custody)
    del files['root.pub']
    assert _resolve(authority_files) is None


def test_provider_drift_stale_observation_and_checker_denied(authority_files):
    observation = authority_files[7]
    assert _resolve(authority_files, checker=1) is None
    assert _resolve(authority_files, observation=replace(observation, observed_at=_NOW - timedelta(seconds=61))) is None
    drifted = replace(observation.binding, cluster_id='other-cluster')
    assert _resolve(authority_files, observation=replace(observation, binding=drifted)) is None


def test_current_deployment_revocation_invalidates_custody(authority_files):
    files, _, deployment_file, deployment, _, _, _, _ = authority_files
    files[deployment_file] = _envelope(deployment | {'state': 'revoked'})
    assert _resolve(authority_files) is None


def test_noncanonical_envelope_denied(authority_files):
    files, _, _, _, custody_file, _, _, _ = authority_files
    files[custody_file] = files[custody_file].replace(b'"payload":', b'"payload": ')
    assert _resolve(authority_files) is None


def test_missing_real_authority_directory_denies(monkeypatch, tmp_path):
    monkeypatch.setattr(issuer_authority, '_AUTHORITY_DIR', tmp_path / 'missing')
    assert issuer_authority._read_authority_file('root.pub') is None
    assert issuer_authority._read_authority_file('../root.pub') is None


def test_boolean_source_identity_cannot_match_integer_scope(authority_files):
    files, scope, deployment_file, deployment, _, _, _, _ = authority_files
    altered_scope = dict(deployment['scope'], instance_id=True)
    files[deployment_file] = _envelope(deployment | {'scope': altered_scope})
    assert issuer_authority.resolve_deployment_authority(scope, now=_NOW) is None


@pytest.fixture
def typed_evidence(authority_files):
    files, scope = authority_files[:2]
    deployment = issuer_authority.resolve_deployment_authority(scope, now=_NOW)
    assert deployment is not None
    selector = ProviderCredentialVersionSelector(
        'openbao',
        scope.deployment_ref,
        2,
        '11111111-2222-4333-8444-555555555555',
        7,
        CredentialVersionSelector(1, '', 'kv', 'a' * 64, 2, (_NOW - timedelta(days=1)).isoformat()),
    )
    issued, expires = _NOW, _NOW + timedelta(minutes=3)
    statement = provider_credential_version_statement(selector, issued_at=issued, expires_at=expires)
    assert statement is not None
    payload = {
        'schema': 'kaori.secrets.typed_credential_evidence.v1',
        'state': 'active',
        'deployment_evidence_ref': deployment.evidence_ref,
        'issuer_evidence_ref': 'e' * 64,
        'key_sha256': _KEY_DIGEST,
        'statement_sha256': sha256(statement).hexdigest(),
        'issuer_signature': _ISSUER.sign(statement).hex(),
        'source_owner_id': 1,
        'checker_id': 2,
        'issued_at': issued.isoformat(),
        'expires_at': expires.isoformat(),
    }
    name = issuer_authority.credential_evidence_name(selector)
    files[name] = _envelope(payload)
    return files, selector, deployment, name, payload


def _resolve_typed(fixture, *, selector=None, now=_NOW, issuer_ref='e' * 64):
    _, original, deployment, _, _ = fixture
    return issuer_authority.resolve_typed_credential_evidence(
        selector or original,
        deployment=deployment,
        issuer_evidence_ref=issuer_ref,
        verification_key=_ISSUER.public_key(),
        now=now,
    )


def test_exact_typed_evidence_requires_both_signatures_and_current_files(typed_evidence):
    files, _, _, name, payload = typed_evidence
    result = _resolve_typed(typed_evidence)
    assert result is not None
    assert result.evidence_ref == sha256(files[name]).hexdigest()
    files[name] = _envelope(payload, _ISSUER)
    assert _resolve_typed(typed_evidence) is None
    files[name] = _envelope(payload | {'issuer_signature': '0' * 128})
    assert _resolve_typed(typed_evidence) is None
    del files[name]
    assert _resolve_typed(typed_evidence) is None


@pytest.mark.parametrize(
    'changes',
    [
        {'state': 'revoked'},
        {'deployment_evidence_ref': '0' * 64},
        {'issuer_evidence_ref': '0' * 64},
        {'key_sha256': '0' * 64},
        {'statement_sha256': '0' * 64},
        {'source_owner_id': True},
        {'checker_id': 1},
        {'expires_at': _NOW.isoformat()},
        {'extra': 'not-in-schema'},
    ],
)
def test_wrong_independent_typed_receipt_denies_even_with_valid_root_signature(typed_evidence, changes):
    files, _, _, name, payload = typed_evidence
    files[name] = _envelope(payload | changes)
    assert _resolve_typed(typed_evidence) is None


def test_version_issuer_and_deployment_rotation_invalidate_typed_evidence(typed_evidence):
    files, selector, deployment, name, _ = typed_evidence
    for changed in (
        replace(selector, issuer_revision=3),
        replace(selector, representation_id=8),
        replace(selector, credential=replace(selector.credential, version=3)),
    ):
        # Even copying a valid receipt under the new selector's name cannot
        # transfer the provider signature to another version or issuer.
        files[issuer_authority.credential_evidence_name(changed)] = files[name]
        assert _resolve_typed(typed_evidence, selector=changed) is None
    assert _resolve_typed(typed_evidence, issuer_ref='f' * 64) is None
    assert _resolve_typed(typed_evidence, now=_NOW + timedelta(minutes=3)) is None
    del files[f'deployment-{deployment.scope.deployment_ref}.json']
    assert _resolve_typed(typed_evidence) is None
