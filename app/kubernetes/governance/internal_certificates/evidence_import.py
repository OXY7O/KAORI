"""Strict metadata-only import of operator-attested internal Kubernetes PKI evidence.

No HTTP upload, remote shell, provider calls, private key, PEM or kubeconfig.
An external host/tool must be inspected and approved independently.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from app.extensions.db import db
from app.models.audit import AuditEvent
from app.models.cluster import Cluster
from app.models.internal_certificates import InternalPKICertificateInventory, InternalPKIEvidenceBatch

SCHEMA_VERSION = 'kaori.internal-pki-evidence.v1'
MAX_MANIFEST_BYTES = 128 * 1024
MAX_RECORDS = 100
_LEAF_COMPONENTS = frozenset(
    {
        'admin.conf',
        'super-admin.conf',
        'apiserver',
        'apiserver-etcd-client',
        'apiserver-kubelet-client',
        'controller-manager.conf',
        'scheduler.conf',
        'etcd-healthcheck-client',
        'etcd-peer',
        'etcd-server',
        'front-proxy-client',
    }
)
_CA_COMPONENTS = frozenset({'ca', 'etcd-ca', 'front-proxy-ca'})
_MANIFEST_FIELDS = frozenset(
    {
        'schema_version',
        'cluster_id',
        'node_name',
        'source_kind',
        'source_version',
        'collected_at',
        'coverage_state',
        'reference',
        'certificates',
    }
)
_CERTIFICATE_FIELDS = frozenset(
    {'component', 'kind', 'issuer', 'not_before', 'not_after', 'externally_managed'}
)


class PKIEvidenceValidationError(ValueError):
    """Report only safe fixed-format validation failures; never echo source JSON."""


def _exact_keys(value: Any, fields: frozenset[str], *, where: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        raise PKIEvidenceValidationError(f'{where} has missing or unexpected fields.')
    return value


def _utc_timestamp(value: Any, *, name: str, required: bool = True) -> datetime | None:
    if value is None and not required:
        return None
    if not isinstance(value, str) or len(value) > 40:
        raise PKIEvidenceValidationError(f'{name} must be an ISO 8601 UTC timestamp.')
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as exc:
        raise PKIEvidenceValidationError(f'{name} must be an ISO 8601 UTC timestamp.') from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise PKIEvidenceValidationError(f'{name} must be timezone-aware UTC.')
    return parsed.astimezone(UTC)


def _identifier(value: Any, *, name: str, pattern: str, max_length: int) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= max_length or re.fullmatch(pattern, value) is None:
        raise PKIEvidenceValidationError(f'{name} has an invalid format.')
    if '-----BEGIN' in value or 'PRIVATE KEY' in value or 'kubeconfig' in value.lower():
        raise PKIEvidenceValidationError(f'{name} contains forbidden certificate or credential content.')
    return value


def validate_metadata_manifest(payload: Any) -> dict[str, Any]:
    """Normalize a strictly bounded, source-versioned non-secret evidence schema."""
    document = _exact_keys(payload, _MANIFEST_FIELDS, where='Manifest')
    if document['schema_version'] != SCHEMA_VERSION:
        raise PKIEvidenceValidationError('Unsupported Internal PKI evidence schema version.')
    try:
        cluster_id = str(UUID(str(document['cluster_id'])))
    except (ValueError, TypeError, AttributeError) as exc:
        raise PKIEvidenceValidationError('cluster_id must be a valid registered UUID.') from exc

    node_name = _identifier(
        document['node_name'], name='node_name', pattern=r'[A-Za-z0-9][A-Za-z0-9._-]*', max_length=255
    )
    source_kind = document['source_kind']
    if source_kind != 'kubeadm_check_expiration':
        raise PKIEvidenceValidationError('Only attested kubeadm check-expiration metadata is supported.')
    source_version = _identifier(
        document['source_version'], name='source_version', pattern=r'[A-Za-z0-9._+v-]+', max_length=64
    )
    reference = _identifier(
        document['reference'], name='reference', pattern=r'[A-Za-z0-9][A-Za-z0-9._:/-]*', max_length=120
    )
    if document['coverage_state'] not in ('complete', 'partial'):
        raise PKIEvidenceValidationError('coverage_state must be complete or partial.')
    collected_at = _utc_timestamp(document['collected_at'], name='collected_at')
    if collected_at is None or collected_at > datetime.now(UTC) + timedelta(minutes=5):
        raise PKIEvidenceValidationError('collected_at is missing or in the future.')

    raw_records = document['certificates']
    if not isinstance(raw_records, list) or not 1 <= len(raw_records) <= MAX_RECORDS:
        raise PKIEvidenceValidationError('certificates must contain 1–100 metadata records.')

    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in raw_records:
        record = _exact_keys(raw, _CERTIFICATE_FIELDS, where='Certificate')
        component = record['component']
        if component not in _LEAF_COMPONENTS | _CA_COMPONENTS:
            raise PKIEvidenceValidationError('Unsupported or non-kubeadm certificate component.')
        if component in seen:
            raise PKIEvidenceValidationError('Duplicate certificate component in source manifest.')
        seen.add(component)

        kind = 'ca' if component in _CA_COMPONENTS else 'leaf'
        if record['kind'] != kind:
            raise PKIEvidenceValidationError('Certificate component kind does not match the source contract.')
        issuer = record['issuer']
        if issuer is not None:
            issuer = _identifier(issuer, name='issuer', pattern=r'[A-Za-z0-9][A-Za-z0-9._:/ -]*', max_length=120)
        not_before = _utc_timestamp(record['not_before'], name='not_before', required=False)
        not_after = _utc_timestamp(record['not_after'], name='not_after')
        if not_after is None or (not_before is not None and not_before > not_after):
            raise PKIEvidenceValidationError('Certificate validity interval is invalid.')
        externally_managed = record['externally_managed']
        if externally_managed is not None and not isinstance(externally_managed, bool):
            raise PKIEvidenceValidationError('externally_managed must be true, false or null.')
        records.append(
            {
                'component': component,
                'kind': kind,
                'issuer': issuer,
                'not_before': not_before,
                'not_after': not_after,
                'externally_managed': externally_managed,
            }
        )

    return {
        'cluster_id': cluster_id,
        'node_name': node_name,
        'source_kind': source_kind,
        'source_version': source_version,
        'collected_at': collected_at,
        'coverage_state': document['coverage_state'],
        'reference': reference,
        'certificates': sorted(records, key=lambda entry: entry['component']),
    }


def import_attested_pki_metadata(payload: Any) -> tuple[InternalPKIEvidenceBatch, bool]:
    """Validate all fields, then atomically commit a source-qualified snapshot."""
    manifest = validate_metadata_manifest(payload)
    cluster = db.session.get(Cluster, manifest['cluster_id'])
    if cluster is None:
        raise PKIEvidenceValidationError('The target cluster is not registered in KAORI.')

    canonical = {
        **manifest,
        'collected_at': manifest['collected_at'].isoformat(),
        'certificates': [
            {
                **record,
                'not_before': record['not_before'].isoformat() if record['not_before'] else None,
                'not_after': record['not_after'].isoformat(),
            }
            for record in manifest['certificates']
        ],
    }
    digest = hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()
    source_scope = {
        'cluster_id': manifest['cluster_id'],
        'node_name': manifest['node_name'],
        'source_kind': manifest['source_kind'],
    }
    prior = (
        InternalPKIEvidenceBatch.query.filter_by(**source_scope)
        .order_by(InternalPKIEvidenceBatch.collected_at.desc(), InternalPKIEvidenceBatch.id.desc())
        .first()
    )
    if prior is not None and prior.manifest_sha256 == digest:
        return prior, False
    if prior is not None and manifest['collected_at'] <= prior.collected_at.replace(tzinfo=UTC):
        raise PKIEvidenceValidationError('Evidence is older than the latest committed source snapshot.')

    batch = InternalPKIEvidenceBatch(
        id=str(uuid4()),
        **source_scope,
        source_version=manifest['source_version'],
        operator_reference=manifest['reference'],
        manifest_sha256=digest,
        coverage_state=manifest['coverage_state'],
        collected_at=manifest['collected_at'],
        imported_at=datetime.now(UTC),
        record_count=len(manifest['certificates']),
    )
    try:
        db.session.add(batch)
        existing = {
            record.component: record
            for record in InternalPKICertificateInventory.query.filter_by(**source_scope).all()
        }
        received = set()
        for entry in manifest['certificates']:
            received.add(entry['component'])
            item = existing.get(entry['component'])
            if item is None:
                item = InternalPKICertificateInventory(**source_scope, component=entry['component'])
                db.session.add(item)
            for key in ('kind', 'issuer', 'not_before', 'not_after', 'externally_managed'):
                setattr(item, key, entry[key])
            item.evidence_batch_id = batch.id
            item.collected_at = manifest['collected_at']
        if manifest['coverage_state'] == 'complete':
            for component, item in existing.items():
                if component not in received:
                    db.session.delete(item)

        db.session.add(
            AuditEvent(
                target_type='internal_pki_evidence_batch',
                target_id=batch.id,
                action='internal_pki_operator_metadata_import',
                summary='Operator-attested internal PKI metadata committed for a registered cluster.',
                metadata_json={
                    'cluster_id': manifest['cluster_id'],
                    'node_name': manifest['node_name'],
                    'source_kind': manifest['source_kind'],
                    'source_version': manifest['source_version'],
                    'coverage_state': manifest['coverage_state'],
                    'record_count': len(received),
                    'operator_reference': manifest['reference'],
                    'manifest_sha256': digest,
                },
            )
        )
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return batch, True
