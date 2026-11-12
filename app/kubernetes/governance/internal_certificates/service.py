from __future__ import annotations

from datetime import UTC, datetime, timedelta
from math import ceil
from typing import Any

from sqlalchemy import and_, func, or_, select

from app.extensions.db import db
from app.models.cluster import Cluster
from app.models.internal_certificates import InternalPKICertificateInventory, InternalPKIEvidenceBatch
from app.models.kubernetes import KubernetesConnection

_DEFAULT_PER_PAGE = 5
_PER_PAGE_OPTIONS = (5, 10, 25, 50)


def _page_number(raw: Any) -> int:
    try:
        return min(max(int(raw or 1), 1), 10000)
    except (TypeError, ValueError):
        return 1


def _per_page(raw: Any) -> int:
    try:
        parsed = int(raw or _DEFAULT_PER_PAGE)
    except (TypeError, ValueError):
        return _DEFAULT_PER_PAGE
    return parsed if parsed in _PER_PAGE_OPTIONS else _DEFAULT_PER_PAGE


def get_internal_certificates_source_page(args: Any) -> dict[str, Any]:
    """Read only non-secret committed registration fields; never probe PKI.

    Internal certificate expiry and health remain unreported until a qualified
    collector commits actual evidence in the independent #4443 workstream.
    Explicit column projections never load/decrypt KubernetesConnection.kubeconfig.
    """
    selected_cluster_id = str(args.get('cluster_id') or '').strip()
    search = str(args.get('search') or '').strip()[:100]
    page = _page_number(args.get('page'))
    per_page = _per_page(args.get('per_page'))

    count_stmt = select(func.count(Cluster.id))
    stmt = (
        select(
            Cluster.id,
            Cluster.name,
            Cluster.environment,
            KubernetesConnection.detected_platform,
            KubernetesConnection.detected_version,
        )
        .select_from(Cluster)
        .outerjoin(KubernetesConnection, KubernetesConnection.cluster_id == Cluster.id)
    )
    if selected_cluster_id:
        count_stmt = count_stmt.where(Cluster.id == selected_cluster_id)
        stmt = stmt.where(Cluster.id == selected_cluster_id)
    if search:
        count_stmt = count_stmt.where(Cluster.name.ilike(f'%{search}%'))
        stmt = stmt.where(Cluster.name.ilike(f'%{search}%'))

    total_items = db.session.scalar(count_stmt) or 0
    total_pages = max(ceil(total_items / per_page), 1)
    page = min(page, total_pages)
    rows = db.session.execute(
        stmt.order_by(Cluster.name.asc(), Cluster.id.asc()).offset((page - 1) * per_page).limit(per_page)
    ).all()

    records = [
        {
            'id': row.id,
            'name': row.name,
            'environment': row.environment,
            'connection_platform': row.detected_platform,
            'connection_version': row.detected_version,
            'collection_status': 'Not Collected',
            'authority_status': 'Not Verified',
            'expiry_status': 'Unknown',
        }
        for row in rows
    ]

    return {
        'records': records,
        'selected_cluster_id': selected_cluster_id,
        'search': search,
        'registered_total': db.session.scalar(select(func.count(Cluster.id))) or 0,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'allowed_per_page': _PER_PAGE_OPTIONS,
            'total_items': total_items,
            'total_pages': total_pages,
            'start_item': (page - 1) * per_page + 1 if total_items else 0,
            'end_item': min(page * per_page, total_items),
            'has_prev': page > 1,
            'has_next': page < total_pages,
            'prev_page': max(page - 1, 1),
            'next_page': min(page + 1, total_pages),
        },
        'status': 'Not Collected',
        'source_authority': 'Not Verified',
        'renewal_state': 'Monitor Only',
    }


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def enrich_internal_pki_source_states(payload: dict[str, Any]) -> None:
    """Apply the newest attested source batch without conflating it with installed PKI."""
    ids = [record['id'] for record in payload['records']]
    if not ids:
        return
    source_rows = db.session.execute(
        select(
            InternalPKIEvidenceBatch.cluster_id,
            func.max(InternalPKIEvidenceBatch.collected_at),
        )
        .where(InternalPKIEvidenceBatch.cluster_id.in_(ids))
        .group_by(InternalPKIEvidenceBatch.cluster_id)
    ).all()
    latest = {cluster_id: timestamp for cluster_id, timestamp in source_rows}
    for record in payload['records']:
        collected_at = latest.get(record['id'])
        if collected_at is None:
            continue
        stale = datetime.now(UTC) - _aware(collected_at) > timedelta(days=30)
        record['collection_status'] = 'Stale Evidence' if stale else 'Operator Attested'
        record['collection_tone'] = 'warning' if stale else 'info'
        record['authority_status'] = 'Operator Supplied'
        record['expiry_status'] = 'Expiry Evidence Available'


def _expiry_presentation(not_before: datetime | None, not_after: datetime) -> tuple[str, str]:
    """Reported expiry posture; freshness is shown separately from expiration."""
    now = datetime.now(UTC)
    if not_before is not None and _aware(not_before) > now:
        return 'Not Yet Valid', 'unknown'
    remaining = _aware(not_after) - now
    if remaining <= timedelta(0):
        return 'Expired', 'critical'
    if remaining <= timedelta(days=7):
        return 'Critical Window', 'critical'
    if remaining <= timedelta(days=30):
        return 'Renewal Window', 'warning'
    return 'Outside Window', 'normal'


def get_internal_pki_operational_summary(cluster_id: str) -> dict[str, Any]:
    """Summarize committed source-reported PKI evidence, never installed certificate health."""
    now = datetime.now(UTC)
    inventory = InternalPKICertificateInventory
    batch = InternalPKIEvidenceBatch
    valid_from = or_(inventory.not_before.is_(None), inventory.not_before <= now)
    statement = (
        select(
            func.count(inventory.id).label('total'),
            func.count(inventory.id)
            .filter(and_(valid_from, inventory.not_after > now + timedelta(days=30)))
            .label('outside_window'),
            func.count(inventory.id)
            .filter(
                and_(
                    valid_from,
                    inventory.not_after > now + timedelta(days=7),
                    inventory.not_after <= now + timedelta(days=30),
                )
            )
            .label('renewal_window'),
            func.count(inventory.id)
            .filter(
                and_(
                    valid_from,
                    inventory.not_after > now,
                    inventory.not_after <= now + timedelta(days=7),
                )
            )
            .label('critical_window'),
            func.count(inventory.id).filter(inventory.not_after <= now).label('expired'),
            func.count(inventory.id).filter(inventory.not_before > now).label('not_yet_valid'),
            func.count(inventory.id)
            .filter(inventory.collected_at < now - timedelta(days=30))
            .label('stale'),
            func.count(inventory.id).filter(batch.coverage_state == 'partial').label('partial_evidence'),
            func.max(inventory.collected_at).label('latest_collected'),
        )
        .select_from(inventory)
        .join(batch, batch.id == inventory.evidence_batch_id)
    )
    if cluster_id:
        statement = statement.where(inventory.cluster_id == cluster_id)
    result = db.session.execute(statement).one()
    total = int(result.total or 0)
    stale = int(result.stale or 0)
    partial_evidence = int(result.partial_evidence or 0)
    exceptions = int(result.expired or 0) + int(result.critical_window or 0) + stale
    latest = _aware(result.latest_collected) if result.latest_collected else None
    return {
        'total': total,
        'outside_window': int(result.outside_window or 0),
        'renewal_window': int(result.renewal_window or 0),
        'critical_window': int(result.critical_window or 0),
        'expired': int(result.expired or 0),
        'not_yet_valid': int(result.not_yet_valid or 0),
        'stale': stale,
        'partial_evidence': partial_evidence,
        'status': 'Not Collected' if not total else ('Stale Evidence' if stale else 'Operator Attested'),
        'tone': 'unknown' if not total else ('warning' if stale else 'info'),
        'source_label': 'Operator-attested kubeadm metadata' if total else 'No admitted PKI source',
        'latest_collected': latest.strftime('%d %b %Y %H:%M UTC') if latest else 'Not Collected',
        'coverage_label': 'Not Assessed'
        if not total
        else ('Partial Source Evidence' if partial_evidence else 'Source-Declared Coverage'),
        'exceptions_label': 'Not Assessed' if not total else f'{exceptions} Reported Signals',
    }


def get_internal_certificate_inventory_page(args: Any) -> dict[str, Any]:
    """Bounded page of committed operator-attested PKI metadata, never live provider data."""
    cluster_id = str(args.get('cluster_id') or '').strip()
    search = str(args.get('cert_search') or '').strip()[:100]
    page = _page_number(args.get('cert_page'))
    per_page = _per_page(args.get('cert_per_page'))
    query = InternalPKICertificateInventory.query.join(
        Cluster, Cluster.id == InternalPKICertificateInventory.cluster_id
    ).join(
        InternalPKIEvidenceBatch,
        InternalPKIEvidenceBatch.id == InternalPKICertificateInventory.evidence_batch_id,
    )
    if cluster_id:
        query = query.filter(InternalPKICertificateInventory.cluster_id == cluster_id)
    if search:
        pattern = f'%{search}%'
        query = query.filter(
            or_(
                InternalPKICertificateInventory.component.ilike(pattern),
                InternalPKICertificateInventory.node_name.ilike(pattern),
                Cluster.name.ilike(pattern),
            )
        )

    total = query.count()
    pages = max(ceil(total / per_page), 1)
    page = min(page, pages)
    source_rows = (
        query.with_entities(
            InternalPKICertificateInventory,
            Cluster.name,
            InternalPKIEvidenceBatch.source_version,
            InternalPKIEvidenceBatch.coverage_state,
            InternalPKIEvidenceBatch.operator_reference,
        )
        .order_by(
            Cluster.name.asc(),
            InternalPKICertificateInventory.node_name.asc(),
            InternalPKICertificateInventory.component.asc(),
        )
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    records = []
    for certificate, cluster_name, version, coverage, reference in source_rows:
        status, tone = _expiry_presentation(certificate.not_before, certificate.not_after)
        stale = datetime.now(UTC) - _aware(certificate.collected_at) > timedelta(days=30)
        records.append(
            {
                'cluster_name': cluster_name,
                'node_name': certificate.node_name,
                'component': certificate.component,
                'kind': certificate.kind,
                'issuer': certificate.issuer,
                'not_before': certificate.not_before,
                'not_after': certificate.not_after,
                'externally_managed': certificate.externally_managed,
                'collected_at': certificate.collected_at,
                'source_kind': certificate.source_kind,
                'source_version': version,
                'coverage': coverage,
                'reference': reference,
                'status': status,
                'tone': tone,
                'freshness': 'Stale Evidence' if stale else 'Recently Collected',
                'freshness_tone': 'warning' if stale else 'info',
            }
        )
    operational = get_internal_pki_operational_summary(cluster_id)
    return {
        'records': records,
        'search': search,
        'cluster_id': cluster_id,
        'operational': operational,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'allowed_per_page': _PER_PAGE_OPTIONS,
            'total_items': total,
            'total_pages': pages,
            'start_item': (page - 1) * per_page + 1 if total else 0,
            'end_item': min(page * per_page, total),
            'has_prev': page > 1,
            'has_next': page < pages,
            'prev_page': max(page - 1, 1),
            'next_page': min(page + 1, pages),
        },
        'total': total,
        'committed_total': operational['total'],
        'source_label': 'Operator Attested',
    }
