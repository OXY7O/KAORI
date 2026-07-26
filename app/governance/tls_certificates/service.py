from __future__ import annotations

import base64
import uuid
from collections.abc import Iterable
from datetime import UTC, datetime
from math import ceil
from typing import Any, cast

from flask import current_app
from flask_login import current_user
from sqlalchemy import or_

from app.common.integration_errors import describe_integration_failure
from app.extensions.db import db
from app.governance.tls_certificates.certificate import find_uncovered_hosts, validate_certificate_pair
from app.governance.tls_certificates.collector import build_kubernetes_client, collect_tls_certificates
from app.governance.tls_certificates.constants import (
    TLS_CRT_KEY,
    TLS_DEFAULT_PER_PAGE,
    TLS_KEY_KEY,
    TLS_PER_PAGE_OPTIONS,
    TLS_SECRET_TYPE,
    TLS_STATUS_OPTIONS,
)
from app.integrations.kubernetes.resolver import server_for_cluster
from app.models import Cluster, TLSCertificateInventory, TLSCertificateUpdateEvent, User


def _new_tls_inventory_record(
    *,
    cluster_id: str,
    namespace: str,
    secret_name: str,
) -> TLSCertificateInventory:
    record = TLSCertificateInventory()
    record.cluster_id = cluster_id
    record.namespace = namespace
    record.secret_name = secret_name
    return record


def _new_tls_update_event(
    *,
    cluster_id: str,
    namespace: str,
    secret_name: str,
    old_fingerprint_sha256: str | None,
    new_fingerprint_sha256: str | None,
    old_not_after: datetime | None,
    new_not_after: datetime | None,
    status: str,
    message: str | None,
    actor_user_id: int | None,
    bulk_job_id: str | None = None,
) -> TLSCertificateUpdateEvent:
    event = TLSCertificateUpdateEvent()
    event.cluster_id = cluster_id
    event.namespace = namespace
    event.secret_name = secret_name
    event.old_fingerprint_sha256 = old_fingerprint_sha256
    event.new_fingerprint_sha256 = new_fingerprint_sha256
    event.old_not_after = old_not_after
    event.new_not_after = new_not_after
    event.status = status
    event.message = message
    event.actor_user_id = actor_user_id
    event.bulk_job_id = bulk_job_id
    return event


def _normalize_per_page(value: str | None) -> int:
    try:
        per_page = int(value or TLS_DEFAULT_PER_PAGE)
    except ValueError:
        return TLS_DEFAULT_PER_PAGE

    if per_page not in TLS_PER_PAGE_OPTIONS:
        return TLS_DEFAULT_PER_PAGE

    return per_page


def _normalize_page(value: str | None) -> int:
    try:
        return max(int(value or 1), 1)
    except ValueError:
        return 1


def _build_pagination(*, page: int, per_page: int, total_items: int) -> dict[str, Any]:
    total_pages = max(ceil(total_items / per_page), 1)
    current_page = min(max(page, 1), total_pages)

    if total_items:
        start_item = ((current_page - 1) * per_page) + 1
        end_item = min(current_page * per_page, total_items)
    else:
        start_item = 0
        end_item = 0

    return {
        'page': current_page,
        'per_page': per_page,
        'total_items': total_items,
        'total_pages': total_pages,
        'start_item': start_item,
        'end_item': end_item,
        'has_prev': current_page > 1,
        'has_next': current_page < total_pages,
        'prev_page': max(current_page - 1, 1),
        'next_page': min(current_page + 1, total_pages),
        'allowed_per_page': TLS_PER_PAGE_OPTIONS,
    }


def _normalize_status(value: str | None) -> str:
    selected = (value or 'all').strip().lower()
    return selected if selected in TLS_STATUS_OPTIONS else 'all'


def _filters(args: Any) -> dict[str, Any]:
    return {
        'cluster_id': (args.get('cluster_id') or '').strip(),
        'namespace': (args.get('namespace') or '').strip(),
        'status': _normalize_status(args.get('status')),
        'search': (args.get('search') or '').strip(),
        'page': _normalize_page(args.get('page')),
        'per_page': _normalize_per_page(args.get('per_page')),
    }


def _base_query(filters: dict[str, Any]):
    query = TLSCertificateInventory.query

    if filters['cluster_id']:
        query = query.filter(TLSCertificateInventory.cluster_id == filters['cluster_id'])

    if filters['namespace']:
        query = query.filter(TLSCertificateInventory.namespace == filters['namespace'])

    if filters['status'] != 'all':
        query = query.filter(TLSCertificateInventory.status == filters['status'])

    if filters['search']:
        search = f'%{filters["search"]}%'
        query = query.filter(
            or_(
                TLSCertificateInventory.secret_name.ilike(search),
                TLSCertificateInventory.namespace.ilike(search),
                TLSCertificateInventory.common_name.ilike(search),
                TLSCertificateInventory.issuer.ilike(search),
            )
        )

    return query


def _summary(query) -> dict[str, int]:
    records = query.all()
    return {
        'total': len(records),
        'healthy': sum(1 for record in records if record.status == 'healthy'),
        'warning': sum(1 for record in records if record.status == 'warning'),
        'critical': sum(1 for record in records if record.status == 'critical'),
        'expired': sum(1 for record in records if record.status == 'expired'),
        'invalid': sum(1 for record in records if record.status == 'invalid'),
    }


def get_tls_certificate_page(args: Any) -> dict[str, Any]:
    filters = _filters(args)
    clusters = Cluster.query.order_by(Cluster.name.asc()).all()

    namespace_query = db.session.query(TLSCertificateInventory.namespace).distinct()
    if filters['cluster_id']:
        namespace_query = namespace_query.filter(TLSCertificateInventory.cluster_id == filters['cluster_id'])

    namespaces = [row[0] for row in namespace_query.order_by(TLSCertificateInventory.namespace.asc()).all()]

    # Cluster is the parent filter for namespace. When users switch cluster,
    # an old namespace value from the previous cluster must not keep filtering
    # the result set or remain selected in the UI.
    if filters['namespace'] and filters['namespace'] not in namespaces:
        filters['namespace'] = ''
        filters['page'] = 1

    query = _base_query(filters).order_by(
        TLSCertificateInventory.status.asc(),
        TLSCertificateInventory.days_remaining.asc().nullslast(),
        TLSCertificateInventory.namespace.asc(),
        TLSCertificateInventory.secret_name.asc(),
    )
    total_items = query.count()
    pagination = _build_pagination(
        page=filters['page'],
        per_page=filters['per_page'],
        total_items=total_items,
    )
    records = query.offset((pagination['page'] - 1) * pagination['per_page']).limit(pagination['per_page']).all()

    from app.governance.tls_certificates.sync_state import build_tls_sync_state

    return {
        'records': records,
        'clusters': clusters,
        'namespaces': namespaces,
        'filters': filters,
        'pagination': pagination,
        'summary': _summary(_base_query({**filters, 'page': 1})),
        'status_options': TLS_STATUS_OPTIONS,
        'sync_state': build_tls_sync_state(cluster_id=filters['cluster_id'] or None),
    }


def get_tls_certificate_detail(certificate_id: int) -> TLSCertificateInventory | None:
    return TLSCertificateInventory.query.get(certificate_id)


def sync_tls_certificates_for_cluster(cluster: Cluster) -> tuple[int, str | None]:
    try:
        records = collect_tls_certificates(cluster)
    except Exception as exc:
        current_app.logger.exception('TLS certificate sync failed for cluster %s', cluster.name)
        failure = describe_integration_failure(
            exc,
            service_name='Kubernetes API',
            endpoint=server_for_cluster(cluster),
            request_path='/api/v1/secrets',
        )
        if 'ee key too small' in str(exc).lower():
            failure['code'] = 'legacy_tls_key_rejected'
            failure['reason'] = 'Legacy TLS key was rejected'
            failure['detail'] = (
                'The Kubernetes API client certificate uses a legacy key that is rejected by the current OpenSSL security policy. '
                'Enable Allow legacy TLS certificate for this trusted cluster, then retry the TLS Secret sync.'
            )
        return 0, failure['detail']

    existing = {
        (record.namespace, record.secret_name): record
        for record in TLSCertificateInventory.query.filter(TLSCertificateInventory.cluster_id == cluster.id).all()
    }
    seen: set[tuple[str, str]] = set()

    for payload in records:
        key = (payload['namespace'], payload['secret_name'])
        seen.add(key)
        record = existing.get(key)
        if record is None:
            record = _new_tls_inventory_record(
                cluster_id=cluster.id,
                namespace=payload['namespace'],
                secret_name=payload['secret_name'],
            )
            db.session.add(record)

        for field, value in payload.items():
            setattr(record, field, value)

    stale_records = [record for key, record in existing.items() if key not in seen]
    for record in stale_records:
        db.session.delete(record)

    db.session.commit()
    return len(records), None


def _read_uploaded_pair(files: Any) -> tuple[bytes, bytes]:
    cert_file = files.get('tls_crt_file') or files.get('tls_crt')
    key_file = files.get('tls_key_file') or files.get('tls_key')
    cert_bytes = cert_file.read() if cert_file else b''
    key_bytes = key_file.read() if key_file else b''
    return cert_bytes, key_bytes


def preview_uploaded_pair(files: Any, target_ids: Iterable[int] | None = None) -> dict[str, Any]:
    cert_bytes, key_bytes = _read_uploaded_pair(files)
    validation = validate_certificate_pair(cert_bytes, key_bytes)
    targets: list[TLSCertificateInventory] = []
    target_previews: list[dict[str, Any]] = []

    if target_ids:
        ids = [int(item) for item in target_ids if str(item).isdigit()]
        targets = TLSCertificateInventory.query.filter(TLSCertificateInventory.id.in_(ids)).all() if ids else []

    if validation.parsed_certificate and targets:
        for target in targets:
            uncovered_hosts = find_uncovered_hosts(target.ingress_hosts or [], validation.parsed_certificate)
            status = 'ready'
            message = 'Ready to update.'
            if uncovered_hosts:
                status = 'warning'
                message = 'Certificate SAN does not cover all currently mapped Ingress hosts.'

            target_previews.append(
                {
                    'target': target,
                    'status': status,
                    'message': message,
                    'uncovered_hosts': uncovered_hosts,
                    'new_not_after': validation.parsed_certificate.not_after,
                    'new_days_remaining': validation.parsed_certificate.days_remaining,
                    'new_fingerprint_sha256': validation.parsed_certificate.fingerprint_sha256,
                }
            )

    return {
        'validation': validation,
        'targets': target_previews,
        'cert_bytes': cert_bytes,
        'key_bytes': key_bytes,
    }


def _patch_tls_secret(record: TLSCertificateInventory, cert_bytes: bytes, key_bytes: bytes) -> None:
    cluster = Cluster.query.get(record.cluster_id)
    if cluster is None:
        raise ValueError('Cluster record no longer exists.')

    client = build_kubernetes_client(cluster)
    body = {
        'type': TLS_SECRET_TYPE,
        'data': {
            TLS_CRT_KEY: base64.b64encode(cert_bytes).decode('utf-8'),
            TLS_KEY_KEY: base64.b64encode(key_bytes).decode('utf-8'),
        },
    }
    client.core_api().patch_namespaced_secret(
        name=record.secret_name,
        namespace=record.namespace,
        body=body,
    )


def apply_certificate_update(certificate_id: int, files: Any) -> dict[str, Any]:
    record = TLSCertificateInventory.query.get(certificate_id)
    if record is None:
        return {'status': 'failed', 'message': 'TLS certificate inventory record was not found.'}

    cert_bytes, key_bytes = _read_uploaded_pair(files)
    validation = validate_certificate_pair(cert_bytes, key_bytes)
    if not validation.is_valid or validation.parsed_certificate is None:
        return {'status': 'failed', 'message': ' '.join(validation.errors), 'errors': validation.errors}

    actor = cast(User, current_user)
    old_fingerprint = record.fingerprint_sha256
    old_not_after = record.not_after

    try:
        _patch_tls_secret(record, cert_bytes, key_bytes)
        parsed = validation.parsed_certificate
        record.common_name = parsed.common_name
        record.issuer = parsed.issuer
        record.serial_number = parsed.serial_number
        record.fingerprint_sha256 = parsed.fingerprint_sha256
        record.dns_names = parsed.dns_names
        record.not_before = parsed.not_before
        record.not_after = parsed.not_after
        record.days_remaining = parsed.days_remaining
        record.status = parsed.status
        record.risk_level = parsed.risk_level
        record.parse_error = None
        record.updated_at = datetime.now(UTC)

        db.session.add(
            _new_tls_update_event(
                cluster_id=record.cluster_id,
                namespace=record.namespace,
                secret_name=record.secret_name,
                old_fingerprint_sha256=old_fingerprint,
                new_fingerprint_sha256=parsed.fingerprint_sha256,
                old_not_after=old_not_after,
                new_not_after=parsed.not_after,
                status='success',
                message='TLS Secret updated from uploaded certificate and key.',
                actor_user_id=getattr(actor, 'id', None),
            )
        )
        db.session.commit()
        return {'status': 'success', 'message': 'TLS Secret updated successfully.'}
    except Exception:
        db.session.rollback()
        current_app.logger.exception('TLS certificate update failed')
        db.session.add(
            _new_tls_update_event(
                cluster_id=record.cluster_id,
                namespace=record.namespace,
                secret_name=record.secret_name,
                old_fingerprint_sha256=old_fingerprint,
                new_fingerprint_sha256=validation.parsed_certificate.fingerprint_sha256,
                old_not_after=old_not_after,
                new_not_after=validation.parsed_certificate.not_after,
                status='failed',
                message='The Kubernetes TLS Secret could not be updated.',
                actor_user_id=getattr(actor, 'id', None),
            )
        )
        db.session.commit()
        return {
            'status': 'failed',
            'message': (
                'The Kubernetes TLS Secret could not be updated. Review the cluster connection, '
                'access permissions, and uploaded certificate pair, then retry.'
            ),
        }


def apply_bulk_update(files: Any, target_ids: Iterable[int]) -> dict[str, Any]:
    cert_bytes, key_bytes = _read_uploaded_pair(files)
    validation = validate_certificate_pair(cert_bytes, key_bytes)
    if not validation.is_valid or validation.parsed_certificate is None:
        return {'status': 'failed', 'message': ' '.join(validation.errors), 'errors': validation.errors, 'results': []}

    ids = [int(item) for item in target_ids if str(item).isdigit()]
    targets = TLSCertificateInventory.query.filter(TLSCertificateInventory.id.in_(ids)).all() if ids else []
    if not targets:
        return {'status': 'failed', 'message': 'No TLS Secrets were selected.', 'results': []}

    parsed = validation.parsed_certificate
    bulk_job_id = uuid.uuid4().hex[:16]
    actor = cast(User, current_user)
    results: list[dict[str, Any]] = []

    for target in targets:
        old_fingerprint = target.fingerprint_sha256
        old_not_after = target.not_after
        try:
            _patch_tls_secret(target, cert_bytes, key_bytes)
            target.common_name = parsed.common_name
            target.issuer = parsed.issuer
            target.serial_number = parsed.serial_number
            target.fingerprint_sha256 = parsed.fingerprint_sha256
            target.dns_names = parsed.dns_names
            target.not_before = parsed.not_before
            target.not_after = parsed.not_after
            target.days_remaining = parsed.days_remaining
            target.status = parsed.status
            target.risk_level = parsed.risk_level
            target.parse_error = None
            target.updated_at = datetime.now(UTC)

            db.session.add(
                _new_tls_update_event(
                    cluster_id=target.cluster_id,
                    namespace=target.namespace,
                    secret_name=target.secret_name,
                    old_fingerprint_sha256=old_fingerprint,
                    new_fingerprint_sha256=parsed.fingerprint_sha256,
                    old_not_after=old_not_after,
                    new_not_after=parsed.not_after,
                    status='success',
                    message='TLS Secret updated by bulk upload.',
                    bulk_job_id=bulk_job_id,
                    actor_user_id=getattr(actor, 'id', None),
                )
            )
            results.append({'target': target, 'status': 'success', 'message': 'Updated.'})
        except Exception:
            current_app.logger.exception('Bulk TLS update failed for %s/%s', target.namespace, target.secret_name)
            db.session.add(
                _new_tls_update_event(
                    cluster_id=target.cluster_id,
                    namespace=target.namespace,
                    secret_name=target.secret_name,
                    old_fingerprint_sha256=old_fingerprint,
                    new_fingerprint_sha256=parsed.fingerprint_sha256,
                    old_not_after=old_not_after,
                    new_not_after=parsed.not_after,
                    status='failed',
                    message='The Kubernetes TLS Secret could not be updated by the bulk operation.',
                    bulk_job_id=bulk_job_id,
                    actor_user_id=getattr(actor, 'id', None),
                )
            )
            results.append(
                {
                    'target': target,
                    'status': 'failed',
                    'message': 'Update failed. Review the cluster connection and access permissions.',
                }
            )

    db.session.commit()
    success_count = sum(1 for result in results if result['status'] == 'success')
    return {
        'status': 'success' if success_count else 'failed',
        'message': f'{success_count} of {len(results)} selected TLS Secrets were updated.',
        'bulk_job_id': bulk_job_id,
        'results': results,
    }
