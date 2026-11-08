"""Ingress TLS Secret reference evidence is not a served endpoint TLS proof."""

import pytest

from app.secrets_pki.certificate_ingress_assurance import (
    IngressTLSReference,
    assess_ingress_reference,
)


def test_ingress_reference_and_host_identity_coverage_are_separate_axes():
    evidence = assess_ingress_reference(
        matches=(
            IngressTLSReference(True, 'fully_covered', 2, 2),
            IngressTLSReference(True, 'partial', 2, 1),
            IngressTLSReference(False, 'no_declared_hosts', 0, 0),
        ),
        mapping_state='ready',
    )
    assert evidence.status == 'observed'
    assert evidence.matching_tls_secrets_referenced_by_ingress == 2
    assert evidence.matching_tls_secrets_covering_declared_hosts == 1
    assert evidence.vault_to_controller_proven is False
    assert evidence.endpoint_serving_verified is False
    assert 'secret_name' not in evidence.__dataclass_fields__
    assert 'ingress_hosts' not in evidence.__dataclass_fields__


def test_successfully_collected_scope_can_have_no_ingress_reference():
    result = assess_ingress_reference(
        matches=(IngressTLSReference(False, 'no_declared_hosts', 0, 0),),
        mapping_state='ready',
    )
    assert result.status == 'not_observed'
    assert result.matching_tls_secrets_referenced_by_ingress == 0
    assert result.matching_tls_secrets_covering_declared_hosts == 0


@pytest.mark.parametrize('state', ['partial', 'stale', 'not_collected', 'blocked'])
def test_nonready_ingress_mapping_cannot_claim_negative_evidence(state):
    result = assess_ingress_reference(
        matches=(IngressTLSReference(True, 'fully_covered', 2, 2),),
        mapping_state=state,
    )
    assert result.status == 'unknown'
    assert result.matching_tls_secrets_referenced_by_ingress is None
    assert result.matching_tls_secrets_covering_declared_hosts is None


def test_full_coverage_without_reference_is_not_a_delivery_reference():
    result = assess_ingress_reference(
        matches=(IngressTLSReference(False, 'fully_covered', 2, 2),),
        mapping_state='ready',
    )
    assert result.matching_tls_secrets_referenced_by_ingress == 0
    assert result.matching_tls_secrets_covering_declared_hosts == 0
    assert result.endpoint_serving_verified is False


@pytest.mark.parametrize(
    'kwargs',
    [
        {'coverage_state': 'served_by_endpoint'},
        {'declared_host_count': -1},
        {'declared_host_count': 1, 'covered_host_count': 2},
        {'declared_host_count': True},
        {'has_ingress_reference': 'probably'},
    ],
)
def test_invalid_or_synthetic_ingress_evidence_is_rejected(kwargs):
    original = {
        'has_ingress_reference': True,
        'coverage_state': 'fully_covered',
        'declared_host_count': 2,
        'covered_host_count': 2,
    }
    original.update(kwargs)
    with pytest.raises(ValueError):
        IngressTLSReference(**original)


def test_ingress_source_limit_never_truncates_silently():
    with pytest.raises(ValueError, match='bounded'):
        assess_ingress_reference(
            matches=(IngressTLSReference(False, 'no_declared_hosts', 0, 0),) * 1501,
            mapping_state='ready',
        )
