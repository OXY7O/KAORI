from __future__ import annotations

import base64
import uuid
from collections.abc import Iterable
from datetime import UTC, datetime
from math import ceil
from typing import Any, cast

from flask import current_app
from flask_login import current_user
from sqlalchemy import case, func, or_

from app.extensions.db import db
from app.governance.tls_certificates.certificate import (
    find_uncovered_hosts,
    matching_certificate_pattern,
    validate_certificate_pair,
    validity_policy_from_config,
)
from app.governance.tls_certificates.collector import (
    TLSProgressCallback,
    build_kubernetes_client,
    collect_tls_certificate_batch,
)
from app.governance.tls_certificates.constants import (
    TLS_COLLECTION_COLLECTED,
    TLS_COVERAGE_FULL,
    TLS_COVERAGE_NONE,
    TLS_COVERAGE_NOT_REPORTED,
    TLS_COVERAGE_PARTIAL,
    TLS_COVERAGE_UNCOVERED,
    TLS_CRT_KEY,
    TLS_DEFAULT_PER_PAGE,
    TLS_KEY_KEY,
    TLS_PER_PAGE_OPTIONS,
    TLS_SECRET_TYPE,
    TLS_STATUS_OPTIONS,
)
from app.models import (
    Cluster,
    TLSCertificateCollectionState,
    TLSCertificateInventory,
    TLSCertificateUpdateEvent,
    User,
)


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
    status_counts = {
        status: count
        for status, count in query.with_entities(
            TLSCertificateInventory.status,
            func.count(TLSCertificateInventory.id),
        ).group_by(TLSCertificateInventory.status).all()
    }
    coverage_counts = {
        state: count
        for state, count in query.with_entities(
            TLSCertificateInventory.coverage_state,
            func.count(TLSCertificateInventory.id),
        ).group_by(TLSCertificateInventory.coverage_state).all()
    }
    total = sum(status_counts.values())
    return {
        'total': total,
        'healthy': status_counts.get('healthy', 0),
        'warning': status_counts.get('warning', 0),
        'critical': status_counts.get('critical', 0),
        'expired': status_counts.get('expired', 0),
        'invalid': status_counts.get('invalid', 0),
        'unknown': status_counts.get('unknown', 0),
        'coverage_full': coverage_counts.get(TLS_COVERAGE_FULL, 0),
        'coverage_partial': coverage_counts.get(TLS_COVERAGE_PARTIAL, 0),
        'coverage_uncovered': coverage_counts.get(TLS_COVERAGE_UNCOVERED, 0),
        'coverage_none': coverage_counts.get(TLS_COVERAGE_NONE, 0),
        'coverage_not_reported': coverage_counts.get(TLS_COVERAGE_NOT_REPORTED, 0),
        'issuer_count': query.with_entities(
            func.count(func.distinct(TLSCertificateInventory.issuer))
        ).scalar() or 0,
    }


_STATUS_PRESENTATION = {
    'healthy': ('Valid', 'normal', 'circle-check'),
    'warning': ('Renewal Window', 'warning', 'calendar-clock'),
    'critical': ('Critical Window', 'critical', 'triangle-alert'),
    'expired': ('Expired', 'critical', 'circle-x'),
    'invalid': ('Invalid', 'critical', 'badge-x'),
    'unknown': ('Unknown', 'unknown', 'circle-help'),
}

_COVERAGE_PRESENTATION = {
    TLS_COVERAGE_FULL: ('Fully Covered', 'normal', 'shield-check'),
    TLS_COVERAGE_PARTIAL: ('Partial', 'warning', 'shield-alert'),
    TLS_COVERAGE_UNCOVERED: ('Uncovered', 'critical', 'shield-x'),
    TLS_COVERAGE_NONE: ('No Declared Hosts', 'info', 'route-off'),
    TLS_COVERAGE_NOT_REPORTED: ('Not Reported', 'unknown', 'circle-help'),
}

_COLLECTION_PRESENTATION = {
    'collected': ('Collected', 'normal'),
    'permission_unavailable': ('Permission Unavailable', 'warning'),
    'api_unavailable': ('API Unavailable', 'warning'),
    'collection_failed': ('Collection Failed', 'critical'),
    'not_reported': ('Not Reported', 'unknown'),
}


def _collection_states(cluster_ids: Iterable[str]) -> dict[str, TLSCertificateCollectionState]:
    ids = [str(item) for item in cluster_ids if item]
    if not ids:
        return {}
    return {
        str(state.cluster_id): state
        for state in TLSCertificateCollectionState.query.filter(
            TLSCertificateCollectionState.cluster_id.in_(ids)
        ).all()
    }


def _host_coverage_rows(record: TLSCertificateInventory) -> list[dict[str, Any]]:
    ingress_by_host: dict[str, list[str]] = {}
    for consumer in record.used_by or []:
        if not isinstance(consumer, dict):
            continue
        ingress_name = str(consumer.get('name') or 'Ingress')
        for host in consumer.get('hosts') or []:
            ingress_by_host.setdefault(str(host), []).append(ingress_name)

    rows: list[dict[str, Any]] = []
    uncovered = set(record.uncovered_hosts or [])
    for host in sorted({str(item) for item in (record.ingress_hosts or []) if item}):
        matched = matching_certificate_pattern(host, record.dns_names or [], record.common_name)
        rows.append(
            {
                'host': host,
                'state': 'Uncovered' if host in uncovered else 'Covered',
                'tone': 'critical' if host in uncovered else 'normal',
                'matched_identity': matched or 'No Matching SAN',
                'ingresses': sorted(set(ingress_by_host.get(host, []))),
            }
        )
    return rows


def _present_record(
    record: TLSCertificateInventory,
    collection_state: TLSCertificateCollectionState | None,
) -> TLSCertificateInventory:
    status_label, status_tone, status_icon = _STATUS_PRESENTATION.get(
        record.status or 'unknown', _STATUS_PRESENTATION['unknown']
    )
    coverage_label, coverage_tone, coverage_icon = _COVERAGE_PRESENTATION.get(
        record.coverage_state or TLS_COVERAGE_NOT_REPORTED,
        _COVERAGE_PRESENTATION[TLS_COVERAGE_NOT_REPORTED],
    )
    secret_state = collection_state.secret_collection_status if collection_state else 'not_reported'
    ingress_state = collection_state.ingress_mapping_status if collection_state else 'not_reported'
    ingress_resources = []
    for consumer in record.used_by or []:
        if not isinstance(consumer, dict):
            continue
        hosts = [str(item) for item in (consumer.get('hosts') or []) if item]
        ingress_resources.append(
            {
                'name': str(consumer.get('name') or 'Ingress'),
                'supporting_primary': f"Namespace · {consumer.get('namespace') or record.namespace}",
                'supporting_secondary': f"{len(hosts)} Declared Host{'s' if len(hosts) != 1 else ''}",
                'status': None,
                'status_tone': None,
            }
        )

    record.presentation = {
        'status_label': status_label,
        'status_tone': status_tone,
        'status_icon': status_icon,
        'coverage_label': coverage_label,
        'coverage_tone': coverage_tone,
        'coverage_icon': coverage_icon,
        'host_coverage_rows': _host_coverage_rows(record),
        'ingress_resources': ingress_resources,
        'secret_collection_label': _COLLECTION_PRESENTATION.get(secret_state, ('Not Reported', 'unknown'))[0],
        'secret_collection_tone': _COLLECTION_PRESENTATION.get(secret_state, ('Not Reported', 'unknown'))[1],
        'ingress_mapping_label': _COLLECTION_PRESENTATION.get(ingress_state, ('Not Reported', 'unknown'))[0],
        'ingress_mapping_tone': _COLLECTION_PRESENTATION.get(ingress_state, ('Not Reported', 'unknown'))[1],
        'secret_collection_detail': collection_state.secret_collection_detail if collection_state else None,
        'ingress_mapping_detail': collection_state.ingress_mapping_detail if collection_state else None,
    }
    return record


def _collection_snapshot(
    *,
    clusters: list[Cluster],
    selected_cluster_id: str,
    summary: dict[str, int],
    sync_state: dict[str, Any],
) -> dict[str, Any]:
    scoped_clusters = [cluster for cluster in clusters if not selected_cluster_id or str(cluster.id) == selected_cluster_id]
    states = _collection_states([cluster.id for cluster in scoped_clusters])
    selected_cluster = next((cluster for cluster in scoped_clusters if str(cluster.id) == selected_cluster_id), None)
    scope_label = selected_cluster.name if selected_cluster else 'All Clusters'
    scoped_state_values = [states.get(str(cluster.id)) for cluster in scoped_clusters]
    secret_exceptions = sum(
        1
        for item in scoped_state_values
        if item is None or item.secret_collection_status != TLS_COLLECTION_COLLECTED
    )
    ingress_exceptions = sum(
        1
        for item in scoped_state_values
        if item is None or item.ingress_mapping_status != TLS_COLLECTION_COLLECTED
    )
    exceptions = secret_exceptions + ingress_exceptions
    if not scoped_clusters or all(item is None for item in scoped_state_values):
        evidence_label, evidence_tone = 'Not Reported', 'unknown'
    elif secret_exceptions:
        evidence_label, evidence_tone = 'Collection Exceptions', 'critical'
    elif ingress_exceptions:
        evidence_label, evidence_tone = 'Partial Mapping', 'warning'
    else:
        evidence_label, evidence_tone = 'Complete', 'normal'
    return {
        'source_label': 'Kubernetes TLS Secrets + Ingresses',
        'status': evidence_label,
        'tone': evidence_tone,
        'description': 'Worker-generated certificate metadata and declared Ingress host relationships.',
        'latest_collected': sync_state['last_success_label'],
        'scope_label': scope_label,
        'coverage_label': f"{summary['total']} TLS Secrets",
        'exceptions_label': 'No Exceptions' if exceptions == 0 else f'{exceptions} Collection Exceptions',
        'secret_collection_exceptions': secret_exceptions,
        'ingress_mapping_exceptions': ingress_exceptions,
    }


def get_tls_certificate_page(args: Any) -> dict[str, Any]:
    filters = _filters(args)
    clusters = Cluster.query.order_by(Cluster.name.asc()).all()

    namespace_query = db.session.query(TLSCertificateInventory.namespace).distinct()
    if filters['cluster_id']:
        namespace_query = namespace_query.filter(TLSCertificateInventory.cluster_id == filters['cluster_id'])

    namespaces = [row[0] for row in namespace_query.order_by(TLSCertificateInventory.namespace.asc()).all()]
    if filters['namespace'] and filters['namespace'] not in namespaces:
        filters['namespace'] = ''
        filters['page'] = 1

    severity_order = case(
        (TLSCertificateInventory.status == 'expired', 0),
        (TLSCertificateInventory.status == 'invalid', 1),
        (TLSCertificateInventory.status == 'critical', 2),
        (TLSCertificateInventory.status == 'warning', 3),
        (TLSCertificateInventory.status == 'unknown', 4),
        else_=5,
    )
    query = _base_query(filters).order_by(
        severity_order,
        TLSCertificateInventory.days_remaining.asc().nullslast(),
        TLSCertificateInventory.namespace.asc(),
        TLSCertificateInventory.secret_name.asc(),
    )
    total_items = query.count()
    pagination = _build_pagination(page=filters['page'], per_page=filters['per_page'], total_items=total_items)
    records = query.offset((pagination['page'] - 1) * pagination['per_page']).limit(pagination['per_page']).all()

    base_query = _base_query({**filters, 'page': 1})
    summary = _summary(base_query)
    from app.governance.tls_certificates.sync_state import build_tls_sync_state
    sync_state = build_tls_sync_state(cluster_id=filters['cluster_id'] or None)
    state_map = _collection_states([record.cluster_id for record in records])
    records = [_present_record(record, state_map.get(str(record.cluster_id))) for record in records]
    validity_policy = validity_policy_from_config(current_app.config)

    return {
        'records': records,
        'clusters': clusters,
        'namespaces': namespaces,
        'filters': filters,
        'pagination': pagination,
        'summary': summary,
        'status_options': TLS_STATUS_OPTIONS,
        'sync_state': sync_state,
        'snapshot': _collection_snapshot(
            clusters=clusters,
            selected_cluster_id=filters['cluster_id'],
            summary=summary,
            sync_state=sync_state,
        ),
        'validity_policy': {
            'renewal_window_days': validity_policy.renewal_window_days,
            'critical_window_days': validity_policy.critical_window_days,
        },
    }


def get_tls_certificate_detail(certificate_id: int) -> TLSCertificateInventory | None:
    record = TLSCertificateInventory.query.get(certificate_id)
    if record is None:
        return None
    state = TLSCertificateCollectionState.query.get(record.cluster_id)
    return _present_record(record, state)


def _persist_collection_state(
    cluster_id: str,
    *,
    secret_status: str,
    ingress_status: str,
    secret_detail: str | None,
    ingress_detail: str | None,
    collected_at: datetime | None,
) -> TLSCertificateCollectionState:
    state = TLSCertificateCollectionState.query.get(cluster_id)
    if state is None:
        state = TLSCertificateCollectionState()
        state.cluster_id = cluster_id
        db.session.add(state)
    state.secret_collection_status = secret_status
    state.ingress_mapping_status = ingress_status
    state.secret_collection_detail = secret_detail
    state.ingress_mapping_detail = ingress_detail
    state.collected_at = collected_at
    state.updated_at = datetime.now(UTC)
    return state


def sync_tls_certificates_for_cluster(
    cluster: Cluster,
    *,
    progress_callback: TLSProgressCallback | None = None,
) -> tuple[int, str | None]:
    policy = validity_policy_from_config(current_app.config)
    batch = collect_tls_certificate_batch(
        cluster,
        progress_callback=progress_callback,
        validity_policy=policy,
    )
    evidence = batch.evidence
    _persist_collection_state(
        cluster.id,
        secret_status=evidence.secret_collection_status,
        ingress_status=evidence.ingress_mapping_status,
        secret_detail=evidence.secret_collection_detail,
        ingress_detail=evidence.ingress_mapping_detail,
        collected_at=datetime.now(UTC),
    )

    if batch.error:
        db.session.commit()
        current_app.logger.error('TLS certificate sync failed for cluster %s: %s', cluster.name, batch.error)
        return 0, batch.error

    records = batch.records
    if progress_callback is not None:
        progress_callback(76, f'Reconciling TLS inventory records for {cluster.name}.')

    existing = {
        (record.namespace, record.secret_name): record
        for record in TLSCertificateInventory.query.filter(TLSCertificateInventory.cluster_id == cluster.id).all()
    }
    seen: set[tuple[str, str]] = set()
    total_records = len(records)

    for index, payload in enumerate(records, start=1):
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

        if progress_callback is not None and total_records:
            reconcile_percent = 76 + int((index / total_records) * 14)
            progress_callback(
                reconcile_percent,
                f'Reconciled {index} of {total_records} TLS inventory records for {cluster.name}.',
            )

    stale_records = [record for key, record in existing.items() if key not in seen]
    if progress_callback is not None:
        progress_callback(93, f'Removing stale TLS inventory records for {cluster.name}.')
    for record in stale_records:
        db.session.delete(record)

    if progress_callback is not None:
        progress_callback(97, f'Committing TLS inventory snapshot for {cluster.name}.')
    db.session.commit()
    if progress_callback is not None:
        progress_callback(100, f'TLS inventory snapshot committed for {cluster.name}.')
    return len(records), None


def _refresh_record_coverage(record: TLSCertificateInventory) -> None:
    hosts = sorted({str(item) for item in (record.ingress_hosts or []) if item})
    state = TLSCertificateCollectionState.query.get(record.cluster_id)
    if state is None or state.ingress_mapping_status != TLS_COLLECTION_COLLECTED:
        record.coverage_state = TLS_COVERAGE_NOT_REPORTED
        record.declared_host_count = len(hosts)
        record.covered_host_count = 0
        record.uncovered_hosts = []
        return
    if not hosts:
        record.coverage_state = TLS_COVERAGE_NONE
        record.declared_host_count = 0
        record.covered_host_count = 0
        record.uncovered_hosts = []
        return
    uncovered = [
        host
        for host in hosts
        if matching_certificate_pattern(host, record.dns_names or [], record.common_name) is None
    ]
    covered = len(hosts) - len(uncovered)
    record.coverage_state = (
        TLS_COVERAGE_FULL if not uncovered else TLS_COVERAGE_UNCOVERED if covered == 0 else TLS_COVERAGE_PARTIAL
    )
    record.declared_host_count = len(hosts)
    record.covered_host_count = covered
    record.uncovered_hosts = uncovered


def _read_uploaded_pair(files: Any) -> tuple[bytes, bytes]:
    cert_file = files.get('tls_crt_file') or files.get('tls_crt')
    key_file = files.get('tls_key_file') or files.get('tls_key')
    cert_bytes = cert_file.read() if cert_file else b''
    key_bytes = key_file.read() if key_file else b''
    return cert_bytes, key_bytes


def preview_uploaded_pair(files: Any, target_ids: Iterable[int] | None = None) -> dict[str, Any]:
    cert_bytes, key_bytes = _read_uploaded_pair(files)
    validation = validate_certificate_pair(
        cert_bytes, key_bytes, policy=validity_policy_from_config(current_app.config)
    )
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
    validation = validate_certificate_pair(
        cert_bytes, key_bytes, policy=validity_policy_from_config(current_app.config)
    )
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
        _refresh_record_coverage(record)
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
    validation = validate_certificate_pair(
        cert_bytes, key_bytes, policy=validity_policy_from_config(current_app.config)
    )
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
            _refresh_record_coverage(target)
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
