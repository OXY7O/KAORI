"""Owner references are optional typed Kubernetes evidence, never Vault delivery."""

from types import SimpleNamespace

import pytest

from app.kubernetes.governance.tls_certificates.collector import parse_tls_secret
from app.kubernetes.governance.tls_certificates.controller_evidence import (
    normalize_tls_controller_owner,
    validate_committed_controller_owners,
)

UID_SECRET = '12345678-1234-4234-8234-123456789abc'
UID_OWNER = '12345678-1234-4234-8234-123456789abd'


def owner(kind='ExternalSecret', *, version='external-secrets.io/v1beta1',
          uid=UID_OWNER, controller=True, name='secret-name-can-be-sensitive'):
    return SimpleNamespace(
        kind=kind, api_version=version, uid=uid, controller=controller,
        name=name,
    )


def tls_secret(*, references=None, uid=UID_SECRET):
    return SimpleNamespace(
        type='kubernetes.io/tls',
        metadata=SimpleNamespace(
            namespace='team-private', name='credential-material',
            uid=uid, owner_references=references,
        ),
        data={},
    )


def test_supported_owner_uid_is_safe_candidate_not_source_proof():
    secret = tls_secret(references=[owner()])
    snapshot = parse_tls_secret(secret, {})
    assert snapshot['secret_uid'] == UID_SECRET
    assert snapshot['controller_owner_refs'] == [
        {'kind': 'ExternalSecret', 'api_group': 'external-secrets.io', 'uid': UID_OWNER},
    ]
    assert 'secret-name-can-be-sensitive' not in repr(snapshot['controller_owner_refs'])
    assert 'credential-material' not in repr(snapshot['controller_owner_refs'])
    assert 'vault' not in repr(snapshot['controller_owner_refs'])


def test_cert_manager_certificate_is_candidate_without_claiming_vault_source():
    item = normalize_tls_controller_owner(
        tls_secret(references=[
            owner('Certificate', version='cert-manager.io/v1'),
        ]).metadata,
    )
    assert item == [{'kind': 'Certificate', 'api_group': 'cert-manager.io', 'uid': UID_OWNER}]


def test_other_owner_kind_and_noncontroller_reference_never_establish_candidate():
    for references in (
        [owner('ReplicaSet', version='apps/v1')],
        [owner(controller=False)],
        [],
    ):
        assert normalize_tls_controller_owner(tls_secret(references=references).metadata) == []


@pytest.mark.parametrize('references', [
    [owner(uid='../../secrets')],
    [owner(version='unapproved/v1')],
    [owner(kind='Certificate', version='external-secrets.io/v1')],
    [owner(), owner()],
    [owner(uid=UID_OWNER.upper().replace('-', ''))],
    [owner()] * 9,
])
def test_ambiguous_untrusted_or_overbound_owner_cannot_be_treated_as_absent(references):
    assert normalize_tls_controller_owner(tls_secret(references=references).metadata) is None


def test_legacy_missing_owner_metadata_is_a_qualified_no_candidate_not_origin_proof():
    result = normalize_tls_controller_owner(tls_secret(references=None).metadata)
    assert result == []
    assert validate_committed_controller_owners(result) == []
    assert validate_committed_controller_owners(None) is None


@pytest.mark.parametrize('stored', [
    {'kind': 'ExternalSecret'},
    [{'kind': 'ExternalSecret', 'api_group': 'external-secrets.io', 'uid': 'private/path'}],
    [{'kind': 'Certificate', 'api_group': 'external-secrets.io', 'uid': UID_OWNER}],
    [{'kind': 'ExternalSecret', 'api_group': 'external-secrets.io', 'uid': UID_OWNER,
      'name': 'sensitive'}],
    [{'kind': 'ExternalSecret', 'api_group': 'external-secrets.io', 'uid': UID_OWNER}] * 2,
])
def test_malformed_committed_reference_never_counts_as_controller(stored):
    assert validate_committed_controller_owners(stored) is None
