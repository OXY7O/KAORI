from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from math import ceil
from typing import Any

from flask import current_app
from sqlalchemy import case, func, or_

from app.extensions.db import db
from app.governance.tls_certificates.certificate import matching_certificate_pattern, validity_policy_from_config
from app.governance.tls_certificates.collector import TLSProgressCallback, collect_tls_certificate_batch
from app.governance.tls_certificates.constants import (
    TLS_COLLECTION_COLLECTED,
    TLS_COVERAGE_FULL,
    TLS_COVERAGE_NONE,
    TLS_COVERAGE_NOT_REPORTED,
    TLS_COVERAGE_PARTIAL,
    TLS_COVERAGE_UNCOVERED,
    TLS_DEFAULT_PER_PAGE,
    TLS_PER_PAGE_OPTIONS,
    TLS_STATUS_OPTIONS,
)
from app.governance.tls_certificates.readiness import (
    TLSGovernanceSchemaReadiness,
    check_tls_governance_schema_readiness,
)
from app.models import Cluster, TLSCertificateCollectionState, TLSCertificateInventory


@dataclass(frozen=True)
class TLSClusterSyncResult:
    collected_count: int
    fatal_error: str | None = None
    warning: str | None = None


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
        )
        .group_by(TLSCertificateInventory.status)
        .all()
    }
    coverage_counts = {
        state: count
        for state, count in query.with_entities(
            TLSCertificateInventory.coverage_state,
            func.count(TLSCertificateInventory.id),
        )
        .group_by(TLSCertificateInventory.coverage_state)
        .all()
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
        'issuer_count': query.with_entities(func.count(func.distinct(TLSCertificateInventory.issuer))).scalar() or 0,
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
        for state in TLSCertificateCollectionState.query.filter(TLSCertificateCollectionState.cluster_id.in_(ids)).all()
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
                'supporting_primary': f'Namespace · {consumer.get("namespace") or record.namespace}',
                'supporting_secondary': f'{len(hosts)} Declared Host{"s" if len(hosts) != 1 else ""}',
                'status': None,
                'status_tone': None,
            }
        )

    setattr(record, 'presentation', {
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
        'coverage_reported': (record.coverage_state or TLS_COVERAGE_NOT_REPORTED) != TLS_COVERAGE_NOT_REPORTED,
        'ingress_mapping_reported': ingress_state == TLS_COLLECTION_COLLECTED,
        'ingress_consumer_count': len(ingress_resources) if ingress_state == TLS_COLLECTION_COLLECTED else None,
        'declared_host_count': record.declared_host_count if ingress_state == TLS_COLLECTION_COLLECTED else None,
    })
    return record


def _collection_snapshot(
    *,
    clusters: list[Cluster],
    selected_cluster_id: str,
    summary: dict[str, int],
    sync_state: dict[str, Any],
) -> dict[str, Any]:
    scoped_clusters = [
        cluster for cluster in clusters if not selected_cluster_id or str(cluster.id) == selected_cluster_id
    ]
    states = _collection_states([cluster.id for cluster in scoped_clusters])
    selected_cluster = next((cluster for cluster in scoped_clusters if str(cluster.id) == selected_cluster_id), None)
    scope_label = selected_cluster.name if selected_cluster else 'All Clusters'
    scoped_state_values = [states.get(str(cluster.id)) for cluster in scoped_clusters]
    secret_exceptions = sum(
        1 for item in scoped_state_values if item is None or item.secret_collection_status != TLS_COLLECTION_COLLECTED
    )
    ingress_exceptions = sum(
        1 for item in scoped_state_values if item is None or item.ingress_mapping_status != TLS_COLLECTION_COLLECTED
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
        'latest_supporting': 'Worker-generated snapshot',
        'scope_label': scope_label,
        'scope_supporting': 'Selected cluster' if selected_cluster else 'Fleet scope',
        'coverage_label': f'{summary["total"]} TLS Secrets',
        'coverage_supporting': 'Collected certificate inventory',
        'coverage_tone': evidence_tone,
        'exceptions_label': 'No Exceptions' if exceptions == 0 else f'{exceptions} Collection Exceptions',
        'exceptions_supporting': 'No issues detected' if exceptions == 0 else 'Review required',
        'exceptions_tone': 'normal' if exceptions == 0 else evidence_tone,
        'secret_collection_exceptions': secret_exceptions,
        'ingress_mapping_exceptions': ingress_exceptions,
    }


def _schema_blocked_payload(
    args: Any,
    readiness: TLSGovernanceSchemaReadiness,
) -> dict[str, Any]:
    filters = _filters(args)
    pagination = _build_pagination(
        page=filters['page'],
        per_page=filters['per_page'],
        total_items=0,
    )
    summary = {
        'total': 0,
        'healthy': 0,
        'warning': 0,
        'critical': 0,
        'expired': 0,
        'invalid': 0,
        'unknown': 0,
        'coverage_full': 0,
        'coverage_partial': 0,
        'coverage_uncovered': 0,
        'coverage_none': 0,
        'coverage_not_reported': 0,
        'issuer_count': 0,
    }
    validity_policy = validity_policy_from_config(current_app.config)
    return {
        'records': [],
        'clusters': [],
        'namespaces': [],
        'filters': filters,
        'pagination': pagination,
        'summary': summary,
        'status_options': TLS_STATUS_OPTIONS,
        'sync_state': {
            'is_active': False,
            'active_job_public_id': None,
            'icon': 'database-zap',
            'label': 'Upgrade Required',
            'tone': 'warning',
            'progress_message': None,
            'helper': readiness.detail,
            'automatic_enabled': False,
            'last_success_label': 'Unavailable',
            'next_run_label': 'Unavailable',
            'progress_percent': 0,
        },
        'snapshot': {
            'source_label': 'TLS Governance Database',
            'status': 'Upgrade Required',
            'tone': 'warning',
            'description': readiness.detail,
            'latest_collected': 'Unavailable',
            'latest_supporting': 'Schema migration required',
            'scope_label': 'Schema Blocked',
            'scope_supporting': 'No collection scope',
            'coverage_label': '0 TLS Secrets',
            'coverage_supporting': 'Collection unavailable',
            'coverage_tone': 'warning',
            'exceptions_label': 'Migration Required',
            'exceptions_supporting': 'Review required',
            'exceptions_tone': 'warning',
            'secret_collection_exceptions': 0,
            'ingress_mapping_exceptions': 0,
        },
        'validity_policy': {
            'renewal_window_days': validity_policy.renewal_window_days,
            'critical_window_days': validity_policy.critical_window_days,
        },
        'schema_readiness': readiness.as_dict(),
    }


def get_tls_certificate_page(args: Any) -> dict[str, Any]:
    schema_readiness = check_tls_governance_schema_readiness()
    if not schema_readiness.ready:
        return _schema_blocked_payload(args, schema_readiness)

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
        'schema_readiness': schema_readiness.as_dict(),
    }


def get_tls_certificate_detail(certificate_id: int) -> TLSCertificateInventory | None:
    if not check_tls_governance_schema_readiness().ready:
        return None
    record = db.session.get(TLSCertificateInventory, certificate_id)
    if record is None:
        return None
    state = db.session.get(TLSCertificateCollectionState, record.cluster_id)
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
    state = db.session.get(TLSCertificateCollectionState, cluster_id)
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
) -> TLSClusterSyncResult:
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
        return TLSClusterSyncResult(collected_count=0, fatal_error=batch.error)

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
    warning = evidence.ingress_mapping_detail if evidence.ingress_mapping_status != TLS_COLLECTION_COLLECTED else None
    return TLSClusterSyncResult(
        collected_count=len(records),
        warning=warning,
    )
