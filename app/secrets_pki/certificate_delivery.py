"""Source-qualified public certificate overlap, never inferred Vault delivery.

The equality of two SHA-256 *public X.509* fingerprints proves only that two
source owners observed the same public certificate. It does not establish
who issued/distributed it, which key holder adopted it, or what TLS endpoint
currently serves it. No Vault or Kubernetes API calls belong in this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

SourceState = Literal['ready', 'partial', 'stale', 'not_collected', 'not_configured', 'blocked']
CorrelationState = Literal[
    'overlap_observed',
    'no_overlap_observed',
    'incomplete_evidence',
    'source_unknown',
]
_VALID_STATES = frozenset({'ready', 'partial', 'stale', 'not_collected', 'not_configured', 'blocked'})
_MAX_SOURCE_FINGERPRINTS = 1500
_MAX_TLS_OBSERVATIONS = 1500


def _fingerprint(value: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in '0123456789abcdef' for character in value)
    ):
        raise ValueError('Only canonical SHA-256 public certificate fingerprints are admissible.')
    return value


@dataclass(frozen=True, slots=True)
class CertificateDeliveryOverlap:
    status: CorrelationState
    source_state: SourceState
    kubernetes_state: SourceState
    observed_source_certificates: int | None
    overlapping_public_certificates: int | None
    matching_kubernetes_tls_secrets: int | None
    coverage: Literal['stored_vault_certs_vs_committed_kubernetes_tls']
    delivery_proven: bool = False
    endpoint_serving_verified: bool = False


def assess_certificate_overlap(
    *,
    vault_fingerprints: tuple[str, ...],
    tls_fingerprints: tuple[str, ...],
    vault_state: SourceState,
    kubernetes_state: SourceState,
) -> CertificateDeliveryOverlap:
    """Aggregate two separately authorized committed evidence sets.

    Callers must enforce resource authorization *before* loading source rows.
    Neither overlap nor lack of overlap may be used as a delivery verdict.
    """
    if vault_state not in _VALID_STATES or kubernetes_state not in _VALID_STATES:
        raise ValueError('Unknown certificate source readiness.')
    if len(vault_fingerprints) > _MAX_SOURCE_FINGERPRINTS or len(tls_fingerprints) > _MAX_TLS_OBSERVATIONS:
        raise ValueError('Certificate correlation source size exceeds bounded read profile.')
    sources = {_fingerprint(fp) for fp in vault_fingerprints}
    targets = tuple(_fingerprint(fp) for fp in tls_fingerprints)
    if (
        vault_state in {'blocked', 'not_configured', 'not_collected'}
        or kubernetes_state in {'blocked', 'not_configured', 'not_collected'}
        or (vault_state == 'stale' and not vault_fingerprints)
        or (kubernetes_state == 'stale' and not tls_fingerprints)
    ):
        return CertificateDeliveryOverlap(
            'source_unknown',
            vault_state,
            kubernetes_state,
            None,
            None,
            None,
            'stored_vault_certs_vs_committed_kubernetes_tls',
        )
    overlaps = sources.intersection(targets)
    matches = sum(1 for fp in targets if fp in sources)
    if vault_state != 'ready' or kubernetes_state != 'ready':
        state: CorrelationState = 'incomplete_evidence'
    elif overlaps:
        state = 'overlap_observed'
    else:
        state = 'no_overlap_observed'
    return CertificateDeliveryOverlap(
        state,
        vault_state,
        kubernetes_state,
        len(sources),
        len(overlaps),
        matches,
        'stored_vault_certs_vs_committed_kubernetes_tls',
    )
