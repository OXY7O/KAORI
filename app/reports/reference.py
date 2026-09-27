from __future__ import annotations

from datetime import UTC, date, datetime
from hashlib import blake2s
from typing import Any

from app.reports.catalog import REPORT_FAMILY_ANALYTICS, REPORT_FAMILY_INVENTORY, get_report_type_spec

REPORT_FAMILY_CODES = {
    REPORT_FAMILY_ANALYTICS: 'ANL',
    REPORT_FAMILY_INVENTORY: 'INV',
}

REPORT_TYPE_CODES = {
    'analytics_overview': 'AOV',
    'resource_utilization': 'RUT',
    'capacity_analysis': 'CAP',
    'storage_analysis': 'STO',
    'workload_analysis': 'WLA',
    'tenant_governance': 'TNG',
    'resource_forecast': 'FCT',
    'top_consumers': 'TPC',
    'alerts_anomalies': 'ALA',
    'object_storage_analysis': 'OSA',
    'object_storage_inventory': 'OSI',
    'inventory_overview': 'IOV',
    'node_inventory': 'NOD',
    'namespace_inventory': 'NSP',
    'workload_inventory': 'WLD',
    'pod_inventory': 'POD',
    'service_inventory': 'SVC',
    'ingress_inventory': 'ING',
    'configuration_inventory': 'CFG',
    'storage_inventory': 'STR',
    'tls_inventory': 'TLS',
}


def build_report_reference(report: Any, *, generated_at: datetime | None = None) -> str:
    """Build the stable, human-readable KAORI document reference.

    The database primary key remains an internal implementation detail. The
    publication reference is deterministic for the report definition and the
    generation date, and works for every report family and output format.
    """

    spec = get_report_type_spec(str(getattr(report, 'report_type', '') or ''))
    family_code = REPORT_FAMILY_CODES[spec.family]
    type_code = REPORT_TYPE_CODES.get(spec.value, 'RPT')
    generated = generated_at or datetime.now(UTC)
    date_code = generated.astimezone(UTC).strftime('%Y%m%d')
    fingerprint = _report_fingerprint(report)
    return f'KAORI-{family_code}-{type_code}-{date_code}-{fingerprint}'


def report_reference_filename(report: Any, *, generated_at: datetime | None = None) -> str:
    return build_report_reference(report, generated_at=generated_at).lower()


def _report_fingerprint(report: Any) -> str:
    stable_parts = (
        str(getattr(report, 'id', '') or ''),
        str(getattr(report, 'report_type', '') or ''),
        str(getattr(report, 'cluster_id', '') or ''),
        str(getattr(report, 'namespace', '') or 'all-namespaces'),
        str(getattr(report, 'period', '') or ''),
        str(getattr(report, 'template_id', '') or ''),
        _date_part(getattr(report, 'created_at', None)),
    )
    digest = blake2s('|'.join(stable_parts).encode('utf-8'), digest_size=4)
    return digest.hexdigest().upper()


def _date_part(value: Any) -> str:
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value or '')
