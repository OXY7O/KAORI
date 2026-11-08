"""Kubernetes TLS Governance captures immutable object IDs, not names as proof."""

from types import SimpleNamespace

from app.kubernetes.governance.tls_certificates.collector import (
    _qualified_secret_uid,
    parse_tls_secret,
)

UID_OLD = '12345678-1234-4234-8234-123456789abc'
UID_NEW = '12345678-1234-4234-8234-123456789abd'


def _secret(uid):
    return SimpleNamespace(
        metadata=SimpleNamespace(
            namespace='internal-ns',
            name='api-certificate',
            uid=uid,
        ),
        type='kubernetes.io/tls',
        data={},  # no tls.crt means invalid cert but the UID is still a source fact
    )


def test_immutable_uid_is_distinct_on_secret_delete_and_recreate():
    old = parse_tls_secret(_secret(UID_OLD), {})
    new = parse_tls_secret(_secret(UID_NEW), {})
    assert old['namespace'] == new['namespace']
    assert old['secret_name'] == new['secret_name']
    assert old['secret_uid'] == UID_OLD
    assert new['secret_uid'] == UID_NEW
    assert old['secret_uid'] != new['secret_uid']
    assert 'tls.key' not in repr(old)


def test_legacy_empty_or_malformed_uid_is_unknown_not_name_identity():
    for uid in (None, '', 'internal-ns/api-certificate', '../kube-system', 'x' * 200, 42):
        result = parse_tls_secret(_secret(uid), {})
        assert result['secret_uid'] is None
        assert result['secret_name'] == 'api-certificate'


def test_canonical_uid_validation_never_normalizes_untrusted_user_identifiers():
    assert _qualified_secret_uid(_secret(UID_OLD)) == UID_OLD
    assert _qualified_secret_uid(_secret(UID_OLD.upper())) == UID_OLD
    assert _qualified_secret_uid(_secret(UID_OLD.replace('-', ''))) is None
