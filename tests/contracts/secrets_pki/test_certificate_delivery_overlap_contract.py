"""Certificate identity overlap must never be represented as Vault delivery proof."""

import pytest

from app.secrets_pki import certificate_delivery_read_model as read_model
from app.secrets_pki.certificate_delivery import assess_certificate_overlap

FINGERPRINT_A = 'a' * 64
FINGERPRINT_B = 'b' * 64


def test_matching_public_fingerprints_are_only_candidate_overlap():
    evidence = assess_certificate_overlap(
        vault_fingerprints=(FINGERPRINT_A, FINGERPRINT_B),
        tls_fingerprints=(FINGERPRINT_A, FINGERPRINT_A),
        vault_state='ready', kubernetes_state='ready',
    )
    assert evidence.status == 'overlap_observed'
    assert evidence.overlapping_public_certificates == 1
    assert evidence.matching_kubernetes_tls_secrets == 2
    assert evidence.observed_source_certificates == 2
    assert evidence.delivery_proven is False
    assert evidence.endpoint_serving_verified is False
    assert 'secret_name' not in evidence.__dataclass_fields__
    assert 'vault_path' not in evidence.__dataclass_fields__


def test_absent_fingerprint_overlap_is_not_a_delivery_failure():
    result = assess_certificate_overlap(
        vault_fingerprints=(FINGERPRINT_A,),
        tls_fingerprints=(FINGERPRINT_B,),
        vault_state='ready', kubernetes_state='ready',
    )
    assert result.status == 'no_overlap_observed'
    assert result.matching_kubernetes_tls_secrets == 0
    assert result.delivery_proven is False


@pytest.mark.parametrize('bad_status', ['blocked', 'not_collected', 'not_configured'])
def test_missing_kubernetes_coverage_cannot_claim_zero_matches(bad_status):
    result = assess_certificate_overlap(
        vault_fingerprints=(FINGERPRINT_A,), tls_fingerprints=(),
        vault_state='ready', kubernetes_state=bad_status,
    )
    assert result.status == 'source_unknown'
    assert result.overlapping_public_certificates is None
    assert result.matching_kubernetes_tls_secrets is None


@pytest.mark.parametrize(
    ('vault_state', 'tls_state'),
    [('stale', 'ready'), ('ready', 'partial'), ('partial', 'stale')],
)
def test_stale_or_partial_sources_cannot_claim_current_assurance(vault_state, tls_state):
    result = assess_certificate_overlap(
        vault_fingerprints=(FINGERPRINT_A,), tls_fingerprints=(FINGERPRINT_A,),
        vault_state=vault_state, kubernetes_state=tls_state,
    )
    assert result.status == 'incomplete_evidence'
    assert result.overlapping_public_certificates == 1
    assert result.endpoint_serving_verified is False


def test_fingerprint_inputs_must_be_canonical_public_x509_sha256():
    for bad in ('private/path/name', 'AB' * 32, '0' * 63, 'z' * 64):
        with pytest.raises(ValueError, match='fingerprints'):
            assess_certificate_overlap(
                vault_fingerprints=(bad,), tls_fingerprints=(),
                vault_state='ready', kubernetes_state='ready',
            )


def test_unauthorized_tls_consumer_short_circuits_before_database_access(monkeypatch):
    monkeypatch.setattr(
        read_model, '_schema_ready',
        lambda: pytest.fail('TLS/PKI database must not be accessed before authorization'),
    )
    result = read_model.build_certificate_delivery_overlap(
        authorized_to_view_kubernetes_tls=False,
    )
    assert result['status'] == 'permission_required'
    assert result['source_certificates'] is None
    assert result['overlapping_certificates'] is None


def test_db_schema_unavailable_is_a_blocked_state_not_a_healthy_zero(monkeypatch):
    monkeypatch.setattr(read_model, '_schema_ready', lambda: False)
    result = read_model.build_certificate_delivery_overlap(
        authorized_to_view_kubernetes_tls=True,
    )
    assert result['status'] == 'blocked'
    assert result['matching_kubernetes_tls_secrets'] is None


def test_correlation_limits_do_not_silently_truncate_large_sources():
    with pytest.raises(ValueError, match='bounded'):
        assess_certificate_overlap(
            vault_fingerprints=(FINGERPRINT_A,) * 1501,
            tls_fingerprints=(),
            vault_state='ready', kubernetes_state='ready',
        )
    with pytest.raises(ValueError, match='bounded'):
        assess_certificate_overlap(
            vault_fingerprints=(FINGERPRINT_A,),
            tls_fingerprints=(FINGERPRINT_A,) * 1501,
            vault_state='ready', kubernetes_state='ready',
        )


def test_all_stale_sources_with_no_recent_sample_are_unknown_not_zero():
    for vault_state, tls_state in [('stale', 'ready'), ('ready', 'stale')]:
        result = assess_certificate_overlap(
            vault_fingerprints=() if vault_state == 'stale' else (FINGERPRINT_A,),
            tls_fingerprints=() if tls_state == 'stale' else (FINGERPRINT_A,),
            vault_state=vault_state, kubernetes_state=tls_state,
        )
        assert result.status == 'source_unknown'
        assert result.overlapping_public_certificates is None
        assert result.matching_kubernetes_tls_secrets is None
