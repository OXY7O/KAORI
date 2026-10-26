"""Bounded read-only bridge between committed Vault and Kubernetes TLS evidence.

This is NOT endpoint polling, Certificate issuance attestation, or a new TLS
inventory. Kubernetes TLS Governance remains the source owner of TLS Secrets
and Ingress relationships. This bridge returns counts, never Secret names,
certificate serials, Vault mount paths, SAN/CN, raw PEM or resource IDs.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import inspect
from sqlalchemy.exc import SQLAlchemyError

from app.extensions.db import db
from app.integrations.secrets_management.secrets_pki.providers.vault.pki_public_evidence import (
    parse_approved_pki_mounts,
)
from app.kubernetes.governance.tls_certificates.constants import TLS_COLLECTION_COLLECTED
from app.kubernetes.governance.tls_certificates.controller_evidence import validate_committed_controller_owners
from app.kubernetes.governance.tls_certificates.readiness import (
    check_tls_governance_schema_readiness,
)
from app.models.governance import TLSCertificateCollectionState, TLSCertificateInventory
from app.models.integration import IntegrationInstance
from app.models.secrets_pki_stored_certificates import (
    PKIStoredCertificateCollectionState,
    PKIStoredCertificateObservation,
)
from app.models.vault import VaultInstance
from app.secrets_pki.certificate_delivery import SourceState, assess_certificate_overlap
from app.secrets_pki.certificate_ingress_assurance import (
    IngressTLSReference,
    assess_ingress_reference,
)

_MAX_VAULT_SOURCES = 25
_MAX_PKI_SCOPES = 100
_MAX_TLS_CLUSTERS = 100
_MAX_CERT_RECORDS = 1500
_FRESHNESS = timedelta(hours=24)


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _blocked(label: str, *, state: str = 'blocked') -> dict[str, Any]:
    return {
        'status': state,
        'label': label,
        'source_certificates': None,
        'overlapping_certificates': None,
        'matching_kubernetes_tls_secrets': None,
        'matching_tls_secrets_with_object_uid': None,
        'controller_owner_reference_status': 'not_qualified',
        'matching_tls_secrets_with_controller_owner': None,
        'object_identity_status': 'not_qualified',
        'ingress_reference_status': 'unknown',
        'ingress_mapping_state': 'not_collected',
        'matching_tls_secrets_referenced_by_ingress': None,
        'matching_tls_secrets_covering_declared_hosts': None,
        'vault_to_controller_proven': False,
        'delivery_proven': False,
        'endpoint_serving_verified': False,
        'coverage': 'Vault stored certificates vs Kubernetes TLS Secrets (observed sources only)',
    }


def _qualified_ingress_reference(value: Any) -> bool:
    """Only well-formed source-owned references support a negative or positive count.

    Invalid JSON is source uncertainty, not evidence of no Ingress use.
    Resource names are validated transiently and never returned by this bridge.
    """
    if not isinstance(value, list) or len(value) > 128:
        raise ValueError('Ingress reference evidence is missing or malformed.')
    for item in value:
        if (
            not isinstance(item, dict)
            or not isinstance(item.get('name'), str)
            or not 0 < len(item['name'].strip()) <= 255
            or not isinstance(item.get('namespace'), str)
            or not 0 < len(item['namespace'].strip()) <= 255
        ):
            raise ValueError('Ingress reference identity is incomplete.')
    return bool(value)


def _has_canonical_object_uid(value: object) -> bool:
    """Legacy NULL or malformed database values are not trusted identities."""
    if not isinstance(value, str) or len(value) > 64:
        return False
    try:
        return str(UUID(value)) == value
    except (ValueError, TypeError, AttributeError):
        return False


def _schema_ready() -> bool:
    """Avoid UndefinedTable 500 on DevContainer branches not yet migrated."""
    try:
        inspector = inspect(db.engine)
        required = {
            'secrets_pki_stored_cert_observations',
            'secrets_pki_stored_cert_collection_states',
        }
        if not required.issubset(set(inspector.get_table_names())):
            return False
        vault_columns = {str(column['name']) for column in inspector.get_columns('vault_instances')}
        tls_columns = {str(col['name']) for col in inspector.get_columns('tls_certificate_inventory')}
        return ('pki_stored_certs_enabled' in vault_columns
                and {'secret_uid', 'controller_owner_refs'}.issubset(tls_columns))
    except SQLAlchemyError:
        return False


def build_certificate_delivery_overlap(
    *, authorized_to_view_kubernetes_tls: bool, now: datetime | None = None,
) -> dict[str, Any]:
    """Never query cross-domain TLS evidence without both domain permissions.

    The caller already requires secrets_pki.view. The explicit second gate
    protects Kubernetes governance, including direct HTTP route access.
    """
    if not authorized_to_view_kubernetes_tls:
        return _blocked('Kubernetes TLS View Permission Required', state='permission_required')
    if not _schema_ready() or not check_tls_governance_schema_readiness().ready:
        return _blocked('Certificate Evidence Schema Not Ready')
    instant = _utc(now or datetime.now(UTC))
    if instant is None:
        raise ValueError('An evaluation time is required.')
    cutoff = instant - _FRESHNESS
    try:
        sources = (
            VaultInstance.query.join(VaultInstance.integration_instance)
            .filter(
                IntegrationInstance.integration_type == 'secrets_pki',
                IntegrationInstance.provider_key == 'vault',
                IntegrationInstance.enabled.is_(True),
                IntegrationInstance.lifecycle_status == 'active',
                VaultInstance.pki_stored_certs_enabled.is_(True),
            )
            .order_by(VaultInstance.id.asc())
            .limit(_MAX_VAULT_SOURCES + 1).all()
        )
        if len(sources) > _MAX_VAULT_SOURCES:
            return _blocked('Certificate Source Scope Exceeds Limit')
        scopes = {
            (int(provider.integration_instance_id), provider.namespace or '', mount)
            for provider in sources
            for mount in parse_approved_pki_mounts(','.join(provider.pki_mounts or ()))
        }
        if not scopes:
            return _blocked('Stored Certificate Source Not Enabled', state='not_configured')
        if len(scopes) > _MAX_PKI_SCOPES:
            return _blocked('Certificate Mount Scope Exceeds Limit')
        ids = [int(provider.integration_instance_id) for provider in sources]
        state_rows = PKIStoredCertificateCollectionState.query.filter(
            PKIStoredCertificateCollectionState.integration_instance_id.in_(ids)
        ).limit(_MAX_PKI_SCOPES + 1).all()
        if len(state_rows) > _MAX_PKI_SCOPES:
            return _blocked('Stored Certificate State Exceeds Limit')
        allowed = {
            (row.integration_instance_id, row.provider_namespace, row.mount): row
            for row in state_rows
            if (row.integration_instance_id, row.provider_namespace, row.mount) in scopes
        }
        qualified_sources = {
            int(row.integration_instance_id)
            for row in sources if row.integration_instance.readiness_status == 'ready'
        }
        ready_scopes = {
            key for key, row in allowed.items()
            if key[0] in qualified_sources
            and row.status == 'ready'
            and (_utc(row.last_committed_at) or datetime.min.replace(tzinfo=UTC)) >= cutoff
        }
        source_state: SourceState
        if not ready_scopes:
            source_state = 'stale' if any(row.last_committed_at is not None for row in allowed.values()) else 'not_collected'
        elif len(ready_scopes) != len(scopes):
            source_state = 'partial'
        else:
            source_state = 'ready'
        # A successful empty source is a real observed zero. Historic/nonapproved
        # rows cannot qualify that zero or participate in a candidate overlap.
        public_fps: tuple[str, ...] = ()
        if ready_scopes:
            source_rows = PKIStoredCertificateObservation.query.filter(
                PKIStoredCertificateObservation.integration_instance_id.in_(ids),
                PKIStoredCertificateObservation.observation_status == 'observed',
                PKIStoredCertificateObservation.last_observed_at >= cutoff,
            ).limit(_MAX_CERT_RECORDS + 1).all()
            if len(source_rows) > _MAX_CERT_RECORDS:
                return _blocked('Vault Certificate Evidence Exceeds Limit')
            public_fps = tuple(
                row.fingerprint_sha256 for row in source_rows
                if (row.integration_instance_id, row.provider_namespace, row.mount) in ready_scopes
            )
        tls_states = TLSCertificateCollectionState.query.limit(_MAX_TLS_CLUSTERS + 1).all()
        if len(tls_states) > _MAX_TLS_CLUSTERS:
            return _blocked('Kubernetes TLS Source Scope Exceeds Limit')
        ready_clusters = {
            row.cluster_id for row in tls_states
            if row.secret_collection_status == TLS_COLLECTION_COLLECTED
            and (_utc(row.collected_at) or datetime.min.replace(tzinfo=UTC)) >= cutoff
        }
        kubernetes_state: SourceState
        if not tls_states:
            kubernetes_state = 'not_collected'
        elif not ready_clusters:
            kubernetes_state = 'stale'
        elif len(ready_clusters) < len(tls_states):
            kubernetes_state = 'partial'
        else:
            kubernetes_state = 'ready'
        # Ingress mapping is an independent source within Kubernetes TLS
        # Governance. A current Secret inventory does not prove a complete
        # Ingress reference inventory.
        ingress_ready = {
            row.cluster_id for row in tls_states
            if row.cluster_id in ready_clusters
            and row.ingress_mapping_status == TLS_COLLECTION_COLLECTED
            and (_utc(row.collected_at) or datetime.min.replace(tzinfo=UTC)) >= cutoff
        }
        if not tls_states:
            mapping_state = 'not_collected'
        elif not ingress_ready:
            mapping_state = 'stale'
        elif len(ingress_ready) < len(tls_states):
            mapping_state = 'partial'
        else:
            mapping_state = 'ready'
        tls_fps: tuple[str, ...] = ()
        uid_count = 0
        controller_owner_count = 0
        controller_owner_unknown = False
        ingress_matches: tuple[IngressTLSReference, ...] = ()
        if public_fps and ready_clusters:
            # SQL predicate restricts to approved fingerprint and collected
            # clusters before hydrating records (never load TLS Secret names).
            tls_rows = TLSCertificateInventory.query.with_entities(
                TLSCertificateInventory.fingerprint_sha256,
                TLSCertificateInventory.secret_uid,
                TLSCertificateInventory.controller_owner_refs,
                TLSCertificateInventory.cluster_id,
                TLSCertificateInventory.used_by,
                TLSCertificateInventory.coverage_state,
                TLSCertificateInventory.declared_host_count,
                TLSCertificateInventory.covered_host_count,
            ).filter(
                TLSCertificateInventory.cluster_id.in_(ready_clusters),
                TLSCertificateInventory.fingerprint_sha256.in_(set(public_fps)),
                TLSCertificateInventory.collected_at >= cutoff,
                TLSCertificateInventory.status.notin_(['invalid', 'unknown']),
            ).limit(_MAX_CERT_RECORDS + 1).all()
            if len(tls_rows) > _MAX_CERT_RECORDS:
                return _blocked('Kubernetes TLS Fingerprint Overlap Exceeds Limit')
            tls_fps = tuple(row[0] for row in tls_rows)
            uid_count = sum(1 for row in tls_rows if _has_canonical_object_uid(row[1]))
            for row in tls_rows:
                if not _has_canonical_object_uid(row[1]):
                    controller_owner_unknown = True
                    continue
                owner_refs = validate_committed_controller_owners(row[2])
                if owner_refs is None:
                    controller_owner_unknown = True
                elif owner_refs:
                    controller_owner_count += 1
            # Authoritative Kubernetes Ingress mapping supplies the reference;
            # no association is inferred from DNS, serial or matching cert.
            if mapping_state == 'ready':
                ingress_matches = tuple(
                    IngressTLSReference(
                        has_ingress_reference=_qualified_ingress_reference(row[4]),
                        coverage_state=row[5],
                        declared_host_count=row[6],
                        covered_host_count=row[7],
                    )
                    for row in tls_rows if row[3] in ingress_ready
                )
        assessment = assess_certificate_overlap(
            vault_fingerprints=public_fps,
            tls_fingerprints=tls_fps,
            vault_state=source_state,
            kubernetes_state=kubernetes_state,
        )
        ingress = assess_ingress_reference(
            matches=ingress_matches,
            mapping_state=(
                mapping_state if assessment.status in {'overlap_observed', 'no_overlap_observed'}
                and kubernetes_state == 'ready' and source_state == 'ready'
                else 'blocked'
            ),
        )
        label = {
            'overlap_observed': 'Same Public Certificate Observed',
            'no_overlap_observed': 'No Overlap in Qualified Observed Sources',
            'incomplete_evidence': 'Partial or Stale Certificate Correlation',
            'source_unknown': 'Certificate Source Evidence Not Available',
        }[assessment.status]
        return {
            'status': assessment.status,
            'label': label,
            'source_certificates': assessment.observed_source_certificates,
            'overlapping_certificates': assessment.overlapping_public_certificates,
            'matching_kubernetes_tls_secrets': assessment.matching_kubernetes_tls_secrets,
            'matching_tls_secrets_with_object_uid': (
                uid_count if assessment.status in {'overlap_observed', 'no_overlap_observed'}
                and source_state == 'ready' and kubernetes_state == 'ready'
                and (uid_count > 0 or assessment.matching_kubernetes_tls_secrets == 0)
                else None
            ),
            'controller_owner_reference_status': (
                'not_qualified' if assessment.status not in {'overlap_observed', 'no_overlap_observed'}
                or source_state != 'ready' or kubernetes_state != 'ready'
                else 'not_applicable' if not assessment.matching_kubernetes_tls_secrets
                else 'partial' if controller_owner_unknown
                else 'candidate_observed' if controller_owner_count
                else 'not_observed'
            ),
            'matching_tls_secrets_with_controller_owner': (
                controller_owner_count if not controller_owner_unknown
                and assessment.status in {'overlap_observed', 'no_overlap_observed'}
                and source_state == 'ready' and kubernetes_state == 'ready'
                else None
            ),
            'object_identity_status': (
                'not_qualified' if source_state != 'ready' or kubernetes_state != 'ready'
                else 'not_applicable' if not assessment.matching_kubernetes_tls_secrets
                else 'not_observed' if uid_count == 0
                else 'partial' if uid_count < assessment.matching_kubernetes_tls_secrets
                else 'qualified'
            ),
            'ingress_reference_status': ingress.status,
            'ingress_mapping_state': ingress.mapping_state,
            'matching_tls_secrets_referenced_by_ingress': ingress.matching_tls_secrets_referenced_by_ingress,
            'matching_tls_secrets_covering_declared_hosts': ingress.matching_tls_secrets_covering_declared_hosts,
            'vault_to_controller_proven': False,
            'delivery_proven': False,
            'endpoint_serving_verified': False,
            'coverage': 'Vault stored certificates vs Kubernetes TLS Secrets (observed sources only)',
        }
    except (SQLAlchemyError, ValueError):
        # Do not expose source IDs, mount names or database exception details.
        return _blocked('Certificate Correlation Source Unavailable')
