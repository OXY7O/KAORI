"""Version-qualified adapter for an operator-reviewed kubeadm expiration report.

Converts public metadata only; never reads Kubernetes, PEM, keys, or a database.
The generated document must still be reviewed before the existing CLI import.
"""

from __future__ import annotations

from typing import Any

from app.kubernetes.governance.internal_certificates.evidence_import import (
    PKIEvidenceValidationError,
    SCHEMA_VERSION,
    validate_metadata_manifest,
)

_SUPPORTED_VERSION = 'v1.36.4'
_SOURCE_API_VERSION = 'output.kubeadm.k8s.io/v1alpha3'
_ROOT_FIELDS = frozenset({'kind', 'apiVersion', 'certificates', 'certificateAuthorities'})
_LEAF_FIELDS = frozenset(
    {'name', 'expirationDate', 'residualTime', 'externallyManaged', 'caName', 'missing'}
)
_CA_FIELDS = frozenset({'name', 'expirationDate', 'residualTime', 'externallyManaged', 'missing'})


def _source_fields(raw: Any, *, ca: bool) -> dict[str, Any]:
    expected = _CA_FIELDS if ca else _LEAF_FIELDS
    if not isinstance(raw, dict) or set(raw) != expected:
        raise PKIEvidenceValidationError('Unexpected kubeadm certificate metadata fields.')
    if raw['missing'] is not False:
        raise PKIEvidenceValidationError('Missing kubeadm certificate evidence cannot be attested.')
    if type(raw['externallyManaged']) is not bool:
        raise PKIEvidenceValidationError('Invalid kubeadm external management flag.')
    if type(raw['residualTime']) is not int:
        raise PKIEvidenceValidationError('Invalid kubeadm residual time metadata.')
    if not isinstance(raw['expirationDate'], str):
        raise PKIEvidenceValidationError('Invalid kubeadm expiry timestamp.')
    if not isinstance(raw['name'], str):
        raise PKIEvidenceValidationError('Invalid kubeadm certificate component.')
    if not ca and not isinstance(raw['caName'], str):
        raise PKIEvidenceValidationError('Invalid kubeadm CA association.')
    return raw


def prepare_kubeadm_metadata_manifest(
    report: Any,
    *,
    cluster_id: str,
    node_name: str,
    source_version: str,
    collected_at: str,
    reference: str,
    coverage_state: str = 'partial',
) -> dict[str, Any]:
    """Map the operator-observed kubeadm v1.36.4 JSON shape to KAORI v1.

    This is an allowlisted metadata conversion, not a provider verification.
    A separate operator invokes the existing import after reviewing the output.
    """
    if source_version != _SUPPORTED_VERSION:
        raise PKIEvidenceValidationError('Unsupported kubeadm source version.')
    if not isinstance(report, dict) or set(report) != _ROOT_FIELDS:
        raise PKIEvidenceValidationError('Unexpected kubeadm source report fields.')
    if report['kind'] != 'CertificateExpirationInfo' or report['apiVersion'] != _SOURCE_API_VERSION:
        raise PKIEvidenceValidationError('Unsupported kubeadm certificate report schema.')

    leaves = report['certificates']
    authorities = report['certificateAuthorities']
    if (
        not isinstance(leaves, list)
        or not isinstance(authorities, list)
        or not leaves
        or not authorities
        or len(leaves) + len(authorities) > 100
    ):
        raise PKIEvidenceValidationError('Kubeadm certificate metadata coverage is invalid.')

    ca_records = [_source_fields(raw, ca=True) for raw in authorities]
    ca_names = {raw['name'] for raw in ca_records}
    if len(ca_names) != len(ca_records):
        raise PKIEvidenceValidationError('Duplicate kubeadm certificate authority.')

    records: list[dict[str, Any]] = []
    for raw in leaves:
        leaf = _source_fields(raw, ca=False)
        if leaf['caName'] not in ca_names:
            raise PKIEvidenceValidationError('Kubeadm leaf CA is missing from the source report.')
        records.append(
            {
                'component': leaf['name'],
                'kind': 'leaf',
                'issuer': leaf['caName'],
                'not_before': None,
                'not_after': leaf['expirationDate'],
                'externally_managed': leaf['externallyManaged'],
            }
        )
    for authority in ca_records:
        records.append(
            {
                'component': authority['name'],
                'kind': 'ca',
                'issuer': None,
                'not_before': None,
                'not_after': authority['expirationDate'],
                'externally_managed': authority['externallyManaged'],
            }
        )

    manifest = {
        'schema_version': SCHEMA_VERSION,
        'cluster_id': cluster_id,
        'node_name': node_name,
        'source_kind': 'kubeadm_check_expiration',
        'source_version': source_version,
        'collected_at': collected_at,
        'coverage_state': coverage_state,
        'reference': reference,
        'certificates': records,
    }
    validate_metadata_manifest(manifest)
    return manifest
