"""Qualified Kubernetes Ingress references to an observed public X.509 certificate.

The source is committed TLS Governance, not Vault or a network endpoint.
An Ingress referring to a Kubernetes TLS Secret and a matching SAN is NOT
proof the ingress controller accepted, loaded, or currently serves the cert.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

IngressEvidenceState = Literal['ready', 'partial', 'stale', 'not_collected', 'blocked']
IngressReferenceStatus = Literal['observed', 'not_observed', 'unknown']
_VALID_COVERAGE = frozenset(
    {
        'fully_covered',
        'partial',
        'uncovered',
        'no_declared_hosts',
        'not_reported',
    }
)
_MAX_MATCHING_TLS_SECRETS = 1500


@dataclass(frozen=True, slots=True)
class IngressTLSReference:
    """No Ingress/Secret name, hostname, SAN or other sensitive source identity."""

    has_ingress_reference: bool
    coverage_state: str
    declared_host_count: int
    covered_host_count: int

    def __post_init__(self) -> None:
        if not isinstance(self.has_ingress_reference, bool):
            raise ValueError('Ingress reference must come from qualified mapping evidence.')
        if self.coverage_state not in _VALID_COVERAGE:
            raise ValueError('Unknown Kubernetes TLS Governance host coverage.')
        if (
            type(self.declared_host_count) is not int
            or type(self.covered_host_count) is not int
            or not 0 <= self.covered_host_count <= self.declared_host_count <= 10000
        ):
            raise ValueError('Ingress declared/covered host counts are malformed.')


@dataclass(frozen=True, slots=True)
class IngressTLSAssurance:
    status: IngressReferenceStatus
    mapping_state: IngressEvidenceState
    matching_tls_secrets_referenced_by_ingress: int | None
    matching_tls_secrets_covering_declared_hosts: int | None
    # Distinct proof axes. Neither can be manufactured by this source.
    vault_to_controller_proven: bool = False
    endpoint_serving_verified: bool = False


def assess_ingress_reference(
    *,
    matches: tuple[IngressTLSReference, ...],
    mapping_state: IngressEvidenceState,
) -> IngressTLSAssurance:
    """Only count actual references and declared-host coverage when mapping is Ready."""
    if mapping_state not in {'ready', 'partial', 'stale', 'not_collected', 'blocked'}:
        raise ValueError('Unsupported Ingress mapping qualification.')
    if len(matches) > _MAX_MATCHING_TLS_SECRETS:
        raise ValueError('Ingress evidence exceeds bounded TLS source budget.')
    if mapping_state != 'ready':
        return IngressTLSAssurance('unknown', mapping_state, None, None)

    referenced = sum(1 for item in matches if item.has_ingress_reference)
    covered = sum(
        1
        for item in matches
        if item.has_ingress_reference
        and item.coverage_state == 'fully_covered'
        and item.declared_host_count > 0
        and item.covered_host_count == item.declared_host_count
    )
    return IngressTLSAssurance(
        'observed' if referenced else 'not_observed',
        'ready',
        referenced,
        covered,
    )
