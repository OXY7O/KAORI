from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from typing import Any

from flask import current_app
from sqlalchemy import case
from sqlalchemy.orm import joinedload

from app.kubernetes.governance.tls_certificates.certificate import validity_policy_from_config
from app.kubernetes.governance.tls_certificates.constants import TLS_COLLECTION_COLLECTED
from app.kubernetes.governance.tls_certificates.readiness import check_tls_governance_schema_readiness
from app.models.cluster import Cluster
from app.models.governance import TLSCertificateCollectionState, TLSCertificateInventory
from app.models.report import Report
from app.reports.export.payloads.common import get_report_selected_cluster

_STATUS_ORDER = {
    'expired': 0,
    'invalid': 1,
    'critical': 2,
    'warning': 3,
    'unknown': 4,
    'healthy': 5,
}


def get_report_tls_inventory_payload(report: Report) -> dict[str, Any]:
    """Build a committed TLS certificate snapshot for governed report exports.

    The collector reads only the persisted TLS certificate inventory and
    relationship evidence. It never connects to Kubernetes and never reads
    Secret data during report generation.
    """

    selected_cluster = get_report_selected_cluster(report)
    cluster_id = str(selected_cluster.id)
    readiness = check_tls_governance_schema_readiness()
    policy = validity_policy_from_config(current_app.config)
    if not readiness.ready:
        return _schema_unavailable_payload(report, readiness.as_dict(), policy)

    scoped_clusters = _scoped_clusters(selected_cluster)
    scoped_cluster_ids = [str(cluster.id) for cluster in scoped_clusters]
    collection_states = _collection_state_map(scoped_cluster_ids)

    query = TLSCertificateInventory.query.options(joinedload(TLSCertificateInventory.cluster))
    query = query.filter(TLSCertificateInventory.cluster_id == cluster_id)
    if report.namespace:
        query = query.filter(TLSCertificateInventory.namespace == report.namespace)

    severity_order = case(
        *((TLSCertificateInventory.status == status, order) for status, order in _STATUS_ORDER.items()),
        else_=99,
    )
    records = query.order_by(
        severity_order,
        TLSCertificateInventory.days_remaining.asc().nullslast(),
        TLSCertificateInventory.cluster_id.asc(),
        TLSCertificateInventory.namespace.asc(),
        TLSCertificateInventory.secret_name.asc(),
    ).all()

    presented_records = [_present_record(record, collection_states.get(str(record.cluster_id))) for record in records]
    summary = _summary(presented_records, scoped_clusters, collection_states)
    latest_collected = _latest_datetime(
        [record.collected_at for record in records]
        + [state.collected_at for state in collection_states.values() if state.collected_at]
    )

    environments = sorted({cluster.environment for cluster in scoped_clusters if cluster.environment})
    environment = (
        environments[0]
        if len(environments) == 1
        else (f'{len(environments)} Environments' if environments else 'Not Available')
    )

    return {
        'cluster': {
            'environment': environment,
            'scope_count': len(scoped_clusters),
        },
        'records': presented_records,
        'summary': summary,
        'collection_states': [
            _present_collection_state(cluster, collection_states.get(str(cluster.id))) for cluster in scoped_clusters
        ],
        'source_evidence': _source_evidence(scoped_clusters, collection_states),
        'validity_policy': {
            'renewal_window_days': policy.renewal_window_days,
            'critical_window_days': policy.critical_window_days,
        },
        'schema_readiness': readiness.as_dict(),
        'collected_at': latest_collected,
        'data_cutoff': latest_collected,
        'sensitive_data_policy': {
            'private_key_collected': False,
            'secret_values_collected': False,
            'pair_validation_state': 'Not Collected',
            'chain_validation_state': 'Not Collected',
        },
    }


def _scoped_clusters(selected_cluster: Cluster) -> list[Cluster]:
    return [selected_cluster]


def _collection_state_map(cluster_ids: Iterable[str]) -> dict[str, TLSCertificateCollectionState]:
    ids = [str(cluster_id) for cluster_id in cluster_ids if cluster_id]
    if not ids:
        return {}
    return {
        str(state.cluster_id): state
        for state in TLSCertificateCollectionState.query.filter(TLSCertificateCollectionState.cluster_id.in_(ids)).all()
    }


def _present_record(
    record: TLSCertificateInventory,
    collection_state: TLSCertificateCollectionState | None,
) -> dict[str, Any]:
    ingress_mapping_collected = bool(
        collection_state and collection_state.ingress_mapping_status == TLS_COLLECTION_COLLECTED
    )
    consumers = [item for item in (record.used_by or []) if isinstance(item, Mapping)]
    if consumers:
        usage_state = 'in_use'
        usage_label = 'In Use'
        usage_tone = 'normal'
    elif ingress_mapping_collected:
        usage_state = 'unused'
        usage_label = 'Unused'
        usage_tone = 'info'
    else:
        usage_state = 'unknown_usage'
        usage_label = 'Unknown Usage'
        usage_tone = 'warning'

    references: list[str] = []
    for consumer in consumers:
        namespace = str(consumer.get('namespace') or record.namespace or 'default')
        name = str(consumer.get('name') or consumer.get('ingress_name') or 'Ingress')
        references.append(f'{namespace}/{name}')

    status = str(record.status or 'unknown').lower()
    coverage = str(record.coverage_state or 'not_reported').lower()
    parse_state = 'Failed' if record.parse_error else ('Passed' if record.not_after else 'Not Available')
    parse_tone = 'critical' if record.parse_error else ('normal' if record.not_after else 'warning')
    cluster_name = getattr(record.cluster, 'name', None) or str(record.cluster_id)
    fingerprint = str(record.fingerprint_sha256 or '')

    return {
        'id': record.id,
        'cluster_id': str(record.cluster_id),
        'cluster': cluster_name,
        'environment': getattr(record.cluster, 'environment', None) or 'Not Available',
        'namespace': record.namespace,
        'secret_name': record.secret_name,
        'secret_identity': f'{record.namespace}/{record.secret_name}',
        'secret_type': record.secret_type or 'Not Available',
        'common_name': record.common_name or 'Not Available',
        'issuer': record.issuer or 'Not Available',
        'serial_number': record.serial_number or 'Not Available',
        'fingerprint_sha256': fingerprint or 'Not Available',
        'fingerprint_short': fingerprint[-16:] if fingerprint else 'Not Available',
        'dns_names': [str(item) for item in (record.dns_names or []) if item],
        'dns_names_label': ', '.join(str(item) for item in (record.dns_names or []) if item) or 'Not Available',
        'ingress_hosts': [str(item) for item in (record.ingress_hosts or []) if item],
        'ingress_hosts_label': ', '.join(str(item) for item in (record.ingress_hosts or []) if item) or 'Not Available',
        'used_by': consumers,
        'reference_count': len(consumers),
        'references': references,
        'references_label': ', '.join(references[:2]) + (' +' if len(references) > 2 else '')
        if references
        else ('No committed reference' if usage_state == 'unused' else 'Not Available'),
        'usage_state': usage_state,
        'usage_label': usage_label,
        'usage_tone': usage_tone,
        'not_before': record.not_before,
        'not_after': record.not_after,
        'days_remaining': record.days_remaining,
        'status': status,
        'status_label': _status_label(status),
        'status_tone': _status_tone(status),
        'risk_level': record.risk_level or 'unknown',
        'parse_error': record.parse_error,
        'parse_state': parse_state,
        'parse_tone': parse_tone,
        'coverage_state': coverage,
        'coverage_label': _coverage_label(coverage),
        'coverage_tone': _coverage_tone(coverage),
        'declared_host_count': int(record.declared_host_count or 0),
        'covered_host_count': int(record.covered_host_count or 0),
        'uncovered_hosts': [str(item) for item in (record.uncovered_hosts or []) if item],
        'uncovered_hosts_label': ', '.join(str(item) for item in (record.uncovered_hosts or []) if item) or 'None',
        'collected_at': record.collected_at,
        'updated_at': record.updated_at,
        'key_pair_state': 'Not Collected',
        'chain_state': 'Not Collected',
    }


def _summary(
    records: list[dict[str, Any]],
    clusters: list[Cluster],
    states: dict[str, TLSCertificateCollectionState],
) -> dict[str, Any]:
    status_counts = {key: 0 for key in _STATUS_ORDER}
    usage_counts = {'in_use': 0, 'unused': 0, 'unknown_usage': 0}
    coverage_counts = {
        'fully_covered': 0,
        'partial': 0,
        'uncovered': 0,
        'no_declared_hosts': 0,
        'not_reported': 0,
    }
    issuer_values: set[str] = set()
    for record in records:
        status_counts[str(record['status'])] = status_counts.get(str(record['status']), 0) + 1
        usage_counts[str(record['usage_state'])] = usage_counts.get(str(record['usage_state']), 0) + 1
        coverage_counts[str(record['coverage_state'])] = coverage_counts.get(str(record['coverage_state']), 0) + 1
        issuer = str(record.get('issuer') or '')
        if issuer and issuer != 'Not Available':
            issuer_values.add(issuer)

    expired_in_use = sum(1 for record in records if record['status'] == 'expired' and record['usage_state'] == 'in_use')
    critical_in_use = sum(
        1 for record in records if record['status'] == 'critical' and record['usage_state'] == 'in_use'
    )
    warning_in_use = sum(1 for record in records if record['status'] == 'warning' and record['usage_state'] == 'in_use')
    invalid_in_use = sum(1 for record in records if record['status'] == 'invalid' and record['usage_state'] == 'in_use')
    uncovered_in_use = sum(
        1
        for record in records
        if record['coverage_state'] in {'partial', 'uncovered'} and record['usage_state'] == 'in_use'
    )
    secret_collection_exceptions = sum(
        1
        for cluster in clusters
        if states.get(str(cluster.id)) is None
        or states[str(cluster.id)].secret_collection_status != TLS_COLLECTION_COLLECTED
    )
    ingress_mapping_exceptions = sum(
        1
        for cluster in clusters
        if states.get(str(cluster.id)) is None
        or states[str(cluster.id)].ingress_mapping_status != TLS_COLLECTION_COLLECTED
    )

    action_required = sum(
        1
        for record in records
        if record['usage_state'] == 'in_use'
        and (
            record['status'] in {'expired', 'critical', 'invalid'}
            or record['coverage_state'] in {'partial', 'uncovered'}
        )
    )

    return {
        'total': len(records),
        **status_counts,
        **usage_counts,
        **coverage_counts,
        'issuer_count': len(issuer_values),
        'expired_in_use': expired_in_use,
        'critical_in_use': critical_in_use,
        'warning_in_use': warning_in_use,
        'invalid_in_use': invalid_in_use,
        'uncovered_in_use': uncovered_in_use,
        'action_required': action_required,
        'renewal_attention': warning_in_use,
        'cluster_count': len(clusters),
        'secret_collection_exceptions': secret_collection_exceptions,
        'ingress_mapping_exceptions': ingress_mapping_exceptions,
        'collection_exceptions': secret_collection_exceptions + ingress_mapping_exceptions,
        'missing_secret_count': None,
        'missing_secret_evidence': 'Not Collected',
    }


def _present_collection_state(
    cluster: Cluster,
    state: TLSCertificateCollectionState | None,
) -> dict[str, Any]:
    return {
        'cluster_id': str(cluster.id),
        'cluster': cluster.name,
        'environment': cluster.environment,
        'secret_collection_status': state.secret_collection_status if state else 'not_reported',
        'ingress_mapping_status': state.ingress_mapping_status if state else 'not_reported',
        'secret_collection_detail': state.secret_collection_detail if state else None,
        'ingress_mapping_detail': state.ingress_mapping_detail if state else None,
        'collected_at': state.collected_at if state else None,
    }


def _source_evidence(
    clusters: list[Cluster],
    states: dict[str, TLSCertificateCollectionState],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for cluster in clusters:
        state = states.get(str(cluster.id))
        rows.append(
            {
                'cluster': cluster.name,
                'environment': cluster.environment,
                'secret_collection_status': state.secret_collection_status if state else 'not_reported',
                'ingress_mapping_status': state.ingress_mapping_status if state else 'not_reported',
                'collected_at': state.collected_at if state else None,
            }
        )
    return rows


def _schema_unavailable_payload(report: Report, readiness: dict[str, Any], policy: Any) -> dict[str, Any]:
    return {
        'cluster': {'environment': 'Not Available', 'scope_count': 0},
        'records': [],
        'summary': {
            'total': 0,
            'healthy': 0,
            'warning': 0,
            'critical': 0,
            'expired': 0,
            'invalid': 0,
            'unknown': 0,
            'in_use': 0,
            'unused': 0,
            'unknown_usage': 0,
            'fully_covered': 0,
            'partial': 0,
            'uncovered': 0,
            'no_declared_hosts': 0,
            'not_reported': 0,
            'issuer_count': 0,
            'expired_in_use': 0,
            'critical_in_use': 0,
            'warning_in_use': 0,
            'invalid_in_use': 0,
            'uncovered_in_use': 0,
            'action_required': 0,
            'renewal_attention': 0,
            'cluster_count': 0,
            'secret_collection_exceptions': 0,
            'ingress_mapping_exceptions': 0,
            'collection_exceptions': 0,
            'missing_secret_count': None,
            'missing_secret_evidence': 'Not Collected',
        },
        'collection_states': [],
        'source_evidence': [],
        'validity_policy': {
            'renewal_window_days': policy.renewal_window_days,
            'critical_window_days': policy.critical_window_days,
        },
        'schema_readiness': readiness,
        'collected_at': None,
        'data_cutoff': None,
        'sensitive_data_policy': {
            'private_key_collected': False,
            'secret_values_collected': False,
            'pair_validation_state': 'Not Collected',
            'chain_validation_state': 'Not Collected',
        },
        'report_scope': {
            'cluster_id': report.cluster_id,
            'namespace': report.namespace,
        },
    }


def _status_label(status: str) -> str:
    return {
        'healthy': 'Valid',
        'warning': 'Renewal Window',
        'critical': 'Critical Expiry',
        'expired': 'Expired',
        'invalid': 'Invalid',
        'unknown': 'Unknown',
    }.get(status, 'Unknown')


def _status_tone(status: str) -> str:
    return {
        'healthy': 'normal',
        'warning': 'warning',
        'critical': 'critical',
        'expired': 'critical',
        'invalid': 'critical',
        'unknown': 'muted',
    }.get(status, 'muted')


def _coverage_label(coverage: str) -> str:
    return {
        'fully_covered': 'Fully Covered',
        'partial': 'Partial Coverage',
        'uncovered': 'Uncovered',
        'no_declared_hosts': 'No Declared Hosts',
        'not_reported': 'Not Reported',
    }.get(coverage, 'Not Reported')


def _coverage_tone(coverage: str) -> str:
    return {
        'fully_covered': 'normal',
        'partial': 'warning',
        'uncovered': 'critical',
        'no_declared_hosts': 'info',
        'not_reported': 'muted',
    }.get(coverage, 'muted')


def _latest_datetime(values: Iterable[datetime | None]) -> datetime | None:
    normalized = []
    for value in values:
        if value is None:
            continue
        if value.tzinfo is None:
            normalized.append(value.replace(tzinfo=UTC))
        else:
            normalized.append(value.astimezone(UTC))
    return max(normalized) if normalized else None
