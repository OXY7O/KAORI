from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from app.kubernetes.analytics.common.base_service import raw_percent, safe_round
from app.kubernetes.analytics.storage.evidence import (
    StorageEvidence,
    VectorEvidence,
    sample_metric,
    sample_value,
)
from app.kubernetes.analytics.storage.parsing import (
    claim_numeric_map,
    claim_phase_map,
    node_numeric_map,
    pv_claim_map,
    pv_info_map,
    pvc_info_map,
    split_claim_key,
    volume_numeric_map,
    volume_phase_map,
)

_CRITICAL = {'critical'}
_WARNING = {'warning'}


def format_storage_bytes(value: float | None, *, available: bool = True) -> str:
    if not available or value is None:
        return 'N/A'
    normalized = max(float(value), 0.0)
    if normalized == 0:
        return '0 B'
    tib = normalized / 1024**4
    if tib >= 1:
        return f'{tib:.2f}'.rstrip('0').rstrip('.') + ' TiB'
    gib = normalized / 1024**3
    if gib >= 1:
        return f'{gib:.2f}'.rstrip('0').rstrip('.') + ' GiB'
    mib = normalized / 1024**2
    if mib >= 1:
        return f'{mib:.0f} MiB'
    kib = normalized / 1024
    if kib >= 1:
        return f'{kib:.0f} KiB'
    return f'{normalized:.0f} B'


def pressure_risk(percent: float | None) -> dict[str, str]:
    if percent is None:
        return {'label': 'Unknown', 'tone': 'unknown'}
    if percent >= 90:
        return {'label': 'Critical', 'tone': 'critical'}
    if percent >= 75:
        return {'label': 'Watch', 'tone': 'warning'}
    return {'label': 'Healthy', 'tone': 'normal'}


def pvc_status_tone(status: str) -> str:
    return {
        'Bound': 'normal',
        'Pending': 'warning',
        'Lost': 'critical',
    }.get(status, 'unknown')


def pvc_risk(
    status: str,
    usage_percent: float | None,
    *,
    pressure_available: bool,
) -> dict[str, str]:
    pressure = (
        pressure_risk(usage_percent)
        if pressure_available and usage_percent is not None
        else {'label': 'Unknown', 'tone': 'unknown'}
    )
    if status == 'Lost' or pressure['tone'] == 'critical':
        return {'label': 'Critical', 'tone': 'critical'}
    if status == 'Pending' or pressure['tone'] == 'warning':
        return {'label': 'Watch', 'tone': 'warning'}
    if status != 'Bound':
        return {'label': 'Unknown', 'tone': 'unknown'}
    return pressure


def pv_status_tone(status: str) -> str:
    return {
        'Bound': 'normal',
        'Available': 'info',
        'Released': 'warning',
        'Failed': 'critical',
    }.get(status, 'unknown')


def pv_risk(status: str) -> dict[str, str]:
    if status == 'Bound':
        return {'label': 'Healthy', 'tone': 'normal'}
    if status == 'Available':
        return {'label': 'Available', 'tone': 'info'}
    if status == 'Released':
        return {'label': 'Watch', 'tone': 'warning'}
    if status == 'Failed':
        return {'label': 'Critical', 'tone': 'critical'}
    return {'label': 'Unknown', 'tone': 'unknown'}


def build_storage_payload(evidence: StorageEvidence) -> dict[str, Any]:
    filesystem_rows = build_filesystem_rows(evidence)
    pvc_rows = build_pvc_rows(evidence)
    pv_rows = build_pv_rows(evidence)
    namespace_options = build_namespace_options(evidence.namespaces, pvc_rows)

    filesystem_observed = any(
        item.observed
        for item in (
            evidence.filesystem_var_size,
            evidence.filesystem_var_available,
            evidence.filesystem_root_size,
            evidence.filesystem_root_available,
        )
    )
    pvc_inventory_observed = evidence.pvc_info.observed
    pvc_status_observed = evidence.pvc_status.observed
    pv_inventory_observed = evidence.pv_info.observed
    pv_status_observed = evidence.pv_status.observed

    filesystem_summary = summarize_filesystem(
        filesystem_rows,
        query_observed=filesystem_observed,
    )
    pvc_summary = summarize_pvc(
        pvc_rows,
        inventory_observed=pvc_inventory_observed,
        status_observed=pvc_status_observed,
        scope_label='All Namespaces',
    )
    pv_summary = summarize_pv(
        pv_rows,
        inventory_observed=pv_inventory_observed,
        status_observed=pv_status_observed,
        claim_rows=pvc_rows,
        claim_inventory_observed=pvc_inventory_observed,
    )
    posture = build_storage_posture(filesystem_summary, pvc_summary, pv_summary)

    return {
        'storage_summary': {
            'node_filesystem': {
                'query_observed': filesystem_observed,
                'selected_node': '',
                'available_nodes': sorted(
                    str(row.get('node') or '') for row in filesystem_rows if str(row.get('node') or '')
                ),
                'scope_label': 'All Nodes',
                'summary': filesystem_summary,
                'all_rows': filesystem_rows,
                'rows': filesystem_rows,
            },
            'persistent_storage': {
                'pvc_inventory_observed': pvc_inventory_observed,
                'pvc_status_observed': pvc_status_observed,
                'pv_inventory_observed': pv_inventory_observed,
                'pv_status_observed': pv_status_observed,
                'pvc': pvc_summary,
                'pv': pv_summary,
                'pvc_all_rows': pvc_rows,
                'pvc_rows': pvc_rows,
                'pv_all_rows': pv_rows,
                'pv_rows': pv_rows,
            },
        },
        'namespace_options': namespace_options,
        'storage_posture': posture,
        'storage_evidence': build_evidence_state(evidence),
    }


def build_filesystem_rows(evidence: StorageEvidence) -> list[dict[str, Any]]:
    var_size = node_numeric_map(evidence.filesystem_var_size)
    var_available = node_numeric_map(evidence.filesystem_var_available)
    root_size = node_numeric_map(evidence.filesystem_root_size)
    root_available = node_numeric_map(evidence.filesystem_root_available)
    nodes = set(var_size) | set(var_available) | set(root_size) | set(root_available)
    rows: list[dict[str, Any]] = []

    for node in sorted(nodes):
        mountpoint, size, available = _select_filesystem_pair(
            var_size.get(node),
            var_available.get(node),
            root_size.get(node),
            root_available.get(node),
        )
        capacity_available = size is not None and size > 0
        free_available = available is not None and available >= 0
        complete = capacity_available and free_available
        if size is not None and available is not None and capacity_available and free_available:
            used = max(size - available, 0.0)
            usage_percent = raw_percent(used, size)
        else:
            used = None
            usage_percent = None
        rows.append(
            {
                'node': node,
                'mountpoint': mountpoint,
                'capacity': format_storage_bytes(size, available=capacity_available),
                'used': format_storage_bytes(used, available=complete),
                'free': format_storage_bytes(available, available=complete),
                'usage_percent': (safe_round(usage_percent, 1) if usage_percent is not None else None),
                'risk': pressure_risk(usage_percent),
                'evidence_available': complete,
                'capacity_evidence_available': capacity_available,
                'free_evidence_available': free_available,
                'capacity_bytes': size if capacity_available else None,
                'used_bytes': used if complete else None,
                'free_bytes': available if complete else None,
            }
        )
    return rows


def _select_filesystem_pair(
    var_size: float | None,
    var_available: float | None,
    root_size: float | None,
    root_available: float | None,
) -> tuple[str, float | None, float | None]:
    candidates = (
        ('/var', var_size, var_available),
        ('/', root_size, root_available),
    )
    for mountpoint, size, available in candidates:
        if size is not None and size > 0 and available is not None and available >= 0:
            return mountpoint, size, available
    for mountpoint, size, available in candidates:
        if size is not None or available is not None:
            return mountpoint, size, available
    return '-', None, None


def build_pvc_rows(evidence: StorageEvidence) -> list[dict[str, Any]]:
    requested = claim_numeric_map(evidence.pvc_requested)
    capacity = claim_numeric_map(evidence.pvc_capacity)
    used = claim_numeric_map(evidence.pvc_used)
    available = claim_numeric_map(evidence.pvc_available)
    status = claim_phase_map(evidence.pvc_status)
    info = pvc_info_map(evidence.pvc_info)
    keys = set(requested) | set(capacity) | set(used) | set(available) | set(status) | set(info)
    rows: list[dict[str, Any]] = []

    for key in sorted(keys):
        namespace, name = split_claim_key(key)
        request_value = requested.get(key)
        capacity_value = capacity.get(key)
        used_value = used.get(key)
        observed_available = available.get(key)
        capacity_known = capacity_value is not None and capacity_value > 0
        used_known = used_value is not None and used_value >= 0
        pressure_available = capacity_known and used_known
        usage_percent = (
            raw_percent(used_value, capacity_value)
            if pressure_available and used_value is not None and capacity_value is not None
            else None
        )
        if observed_available is not None and observed_available >= 0:
            free_value = observed_available
            free_source = 'Observed'
        elif pressure_available and capacity_value is not None and used_value is not None:
            free_value = max(capacity_value - used_value, 0.0)
            free_source = 'Derived'
        else:
            free_value = None
            free_source = 'Unavailable'
        lifecycle = status.get(key, 'Unknown')
        metadata = info.get(key, {})
        rows.append(
            {
                'name': name,
                'namespace': namespace,
                'status': lifecycle,
                'status_tone': pvc_status_tone(lifecycle),
                'storage_class': str(
                    metadata.get('storage_class') or ('No StorageClass' if evidence.pvc_info.observed else 'Unknown')
                ),
                'volume_name': str(metadata.get('volume_name') or '-'),
                'requested': format_storage_bytes(
                    request_value,
                    available=request_value is not None and request_value >= 0,
                ),
                'capacity': format_storage_bytes(
                    capacity_value,
                    available=capacity_known,
                ),
                'used': format_storage_bytes(used_value, available=used_known),
                'free': format_storage_bytes(
                    free_value,
                    available=free_value is not None,
                ),
                'free_source': free_source,
                'requested_bytes': request_value,
                'capacity_bytes': capacity_value if capacity_known else None,
                'used_bytes': used_value if used_known else None,
                'free_bytes': free_value,
                'usage_percent': (safe_round(usage_percent, 1) if usage_percent is not None else None),
                'evidence_available': pressure_available,
                'risk': pvc_risk(
                    lifecycle,
                    usage_percent,
                    pressure_available=pressure_available,
                ),
            }
        )
    return rows


def build_pv_rows(evidence: StorageEvidence) -> list[dict[str, Any]]:
    capacities = volume_numeric_map(evidence.pv_capacity)
    status = volume_phase_map(evidence.pv_status)
    info = pv_info_map(evidence.pv_info)
    claim_map = pv_claim_map(evidence.pvc_info)
    volumes = set(capacities) | set(status) | set(info) | set(claim_map)
    rows: list[dict[str, Any]] = []

    for volume in sorted(volumes):
        capacity = capacities.get(volume)
        capacity_known = capacity is not None and capacity > 0
        lifecycle = status.get(volume, 'Unknown')
        metadata = info.get(volume, {})
        rows.append(
            {
                'name': volume,
                'status': lifecycle,
                'status_tone': pv_status_tone(lifecycle),
                'capacity': format_storage_bytes(
                    capacity,
                    available=capacity_known,
                ),
                'capacity_bytes': capacity if capacity_known else None,
                'evidence_available': capacity_known,
                'storage_class': str(
                    metadata.get('storage_class') or ('No StorageClass' if evidence.pv_info.observed else 'Unknown')
                ),
                'claim': claim_map.get(volume, '-'),
                'reclaim_policy': str(metadata.get('reclaim_policy') or '-'),
                'risk': pv_risk(lifecycle),
            }
        )
    return rows


def build_namespace_options(
    namespaces: VectorEvidence,
    pvc_rows: list[dict[str, Any]],
) -> list[str]:
    values = {
        str(sample_metric(row).get('namespace') or '').strip() for row in namespaces.rows if sample_value(row) == 1
    }
    values.update(
        str(row.get('namespace') or '').strip() for row in pvc_rows if str(row.get('namespace') or '').strip()
    )
    return sorted(value for value in values if value)


def summarize_filesystem(
    rows: list[dict[str, Any]],
    *,
    query_observed: bool,
) -> dict[str, Any]:
    complete_rows = [row for row in rows if row.get('evidence_available')]
    total_capacity = sum(float(row['capacity_bytes']) for row in complete_rows)
    total_used = sum(float(row['used_bytes']) for row in complete_rows)
    total_free = sum(float(row['free_bytes']) for row in complete_rows)
    highest = max(
        complete_rows,
        key=lambda row: float(row.get('usage_percent') or 0),
        default=None,
    )
    evidence_available = bool(complete_rows) and total_capacity > 0
    usage_percent = raw_percent(total_used, total_capacity) if evidence_available else None
    free_percent = raw_percent(total_free, total_capacity) if evidence_available else None
    incomplete_count = len(rows) - len(complete_rows)
    risk = pressure_risk(float(highest['usage_percent']) if highest is not None else None)
    return {
        'query_observed': query_observed,
        'evidence_available': evidence_available,
        'evidence_complete': evidence_available and incomplete_count == 0,
        'observed_node_count': len(rows),
        'complete_node_count': len(complete_rows),
        'incomplete_node_count': incomplete_count,
        'capacity': format_storage_bytes(
            total_capacity,
            available=evidence_available,
        ),
        'used': format_storage_bytes(total_used, available=evidence_available),
        'free': format_storage_bytes(total_free, available=evidence_available),
        'usage_percent': (safe_round(usage_percent, 1) if usage_percent is not None else None),
        'free_percent': (safe_round(free_percent, 1) if free_percent is not None else None),
        'highest_usage': (float(highest['usage_percent']) if highest is not None else None),
        'highest_node': str(highest.get('node') or '-') if highest else '-',
        'highest_mountpoint': str(highest.get('mountpoint') or '-') if highest else '-',
        'risk': risk,
    }


def summarize_pvc(
    rows: list[dict[str, Any]],
    *,
    inventory_observed: bool,
    status_observed: bool,
    scope_label: str,
) -> dict[str, Any]:
    inventory_available = inventory_observed or bool(rows)
    count = len(rows)

    requested_rows = [row for row in rows if row.get('requested_bytes') is not None]
    capacity_rows = [row for row in rows if row.get('capacity_bytes') is not None]
    used_rows = [row for row in rows if row.get('used_bytes') is not None]
    free_rows = [row for row in rows if row.get('free_bytes') is not None]
    pressure_rows = [row for row in rows if row.get('capacity_bytes') is not None and row.get('used_bytes') is not None]

    requested_observed_count = len(requested_rows)
    capacity_observed_count = len(capacity_rows)
    used_observed_count = len(used_rows)
    free_observed_count = len(free_rows)
    pressure_observed_count = len(pressure_rows)

    requested_complete = inventory_available and requested_observed_count == count
    capacity_complete = inventory_available and capacity_observed_count == count
    used_complete = inventory_available and used_observed_count == count
    free_complete = inventory_available and free_observed_count == count
    pressure_complete = inventory_available and pressure_observed_count == count
    lifecycle_complete = (
        inventory_available
        and status_observed
        and all(str(row.get('status') or 'Unknown') != 'Unknown' for row in rows)
    )

    requested_available = inventory_available and (count == 0 or requested_observed_count > 0)
    capacity_available = inventory_available and (count == 0 or capacity_observed_count > 0)
    used_available = inventory_available and (count == 0 or used_observed_count > 0)
    free_available = inventory_available and (count == 0 or free_observed_count > 0)

    requested_total = _sum_known(requested_rows, 'requested_bytes')
    capacity_total = _sum_known(capacity_rows, 'capacity_bytes')
    used_total = _sum_known(used_rows, 'used_bytes')
    free_total = _sum_known(free_rows, 'free_bytes')

    pressure_capacity_total = _sum_known(pressure_rows, 'capacity_bytes')
    pressure_used_total = _sum_known(pressure_rows, 'used_bytes')
    pressure_free_total = sum(
        max(float(row['capacity_bytes']) - float(row['used_bytes']), 0.0) for row in pressure_rows
    )
    pressure_available = pressure_observed_count > 0 and pressure_capacity_total > 0
    used_percent = raw_percent(pressure_used_total, pressure_capacity_total) if pressure_available else None
    free_percent = raw_percent(pressure_free_total, pressure_capacity_total) if pressure_available else None

    risk = _highest_row_risk(rows)
    if count == 0 and inventory_available:
        risk = {'label': 'No Claims', 'tone': 'info'}
    elif inventory_available and count > 0 and risk['tone'] not in {'critical', 'warning'} and not pressure_complete:
        risk = {'label': 'Limited Evidence', 'tone': 'unknown'}

    evidence_gap_count = max(count - pressure_observed_count, 0)
    return {
        'inventory_evidence_available': inventory_available,
        'status_evidence_available': lifecycle_complete,
        'requested_evidence_available': requested_available,
        'capacity_evidence_available': capacity_available,
        'used_evidence_available': used_available,
        'free_evidence_available': free_available,
        'pressure_evidence_available': pressure_available,
        'requested_evidence_complete': requested_complete,
        'capacity_evidence_complete': capacity_complete,
        'used_evidence_complete': used_complete,
        'free_evidence_complete': free_complete,
        'pressure_evidence_complete': pressure_complete,
        'evidence_available': pressure_available,
        'evidence_complete': (inventory_available and lifecycle_complete and (count == 0 or pressure_complete)),
        'has_resources': count > 0,
        'count': count,
        'count_display': str(count) if inventory_available else 'N/A',
        'total_pvc_count': count,
        'requested_observed_count': requested_observed_count,
        'capacity_observed_count': capacity_observed_count,
        'used_observed_count': used_observed_count,
        'free_observed_count': free_observed_count,
        'pressure_observed_count': pressure_observed_count,
        'evidence_gap_count': evidence_gap_count,
        'requested_coverage_percent': _coverage_percent(requested_observed_count, count, inventory_available),
        'capacity_coverage_percent': _coverage_percent(capacity_observed_count, count, inventory_available),
        'used_coverage_percent': _coverage_percent(used_observed_count, count, inventory_available),
        'free_coverage_percent': _coverage_percent(free_observed_count, count, inventory_available),
        'pressure_coverage_percent': _coverage_percent(pressure_observed_count, count, inventory_available),
        'requested_coverage_display': _coverage_display(requested_observed_count, count, inventory_available),
        'capacity_coverage_display': _coverage_display(capacity_observed_count, count, inventory_available),
        'used_coverage_display': _coverage_display(used_observed_count, count, inventory_available),
        'free_coverage_display': _coverage_display(free_observed_count, count, inventory_available),
        'pressure_coverage_display': _coverage_display(pressure_observed_count, count, inventory_available),
        'requested': format_storage_bytes(
            requested_total,
            available=requested_available,
        ),
        'capacity': format_storage_bytes(
            capacity_total,
            available=capacity_available,
        ),
        'used': format_storage_bytes(used_total, available=used_available),
        'free': format_storage_bytes(free_total, available=free_available),
        'pressure_capacity': format_storage_bytes(
            pressure_capacity_total,
            available=pressure_available,
        ),
        'pressure_used': format_storage_bytes(
            pressure_used_total,
            available=pressure_available,
        ),
        'pressure_free': format_storage_bytes(
            pressure_free_total,
            available=pressure_available,
        ),
        'used_percent': (safe_round(used_percent, 1) if used_percent is not None else None),
        'free_percent': (safe_round(free_percent, 1) if free_percent is not None else None),
        'scope_label': scope_label,
        'risk': risk,
        'critical_count': _count_risk(rows, 'critical'),
        'warning_count': _count_risk(rows, 'warning'),
        'unknown_count': _count_risk(rows, 'unknown'),
    }


def _coverage_percent(
    observed_count: int,
    total_count: int,
    inventory_available: bool,
) -> float | None:
    if not inventory_available:
        return None
    if total_count == 0:
        return 100.0
    return safe_round(raw_percent(observed_count, total_count), 1)


def _coverage_display(
    observed_count: int,
    total_count: int,
    inventory_available: bool,
) -> str:
    if not inventory_available:
        return 'N/A'
    return f'{observed_count} of {total_count} PVC'


def summarize_pv(
    rows: list[dict[str, Any]],
    *,
    inventory_observed: bool,
    status_observed: bool,
    claim_rows: list[dict[str, Any]] | None = None,
    claim_inventory_observed: bool = False,
) -> dict[str, Any]:
    inventory_available = inventory_observed or bool(rows)
    count = len(rows)
    capacity_rows = [row for row in rows if row.get('capacity_bytes') is not None]
    capacity_observed_count = len(capacity_rows)
    capacity_available = inventory_available and (count == 0 or capacity_observed_count > 0)
    capacity_complete = inventory_available and capacity_observed_count == count
    lifecycle_complete = (
        inventory_available
        and status_observed
        and all(str(row.get('status') or 'Unknown') != 'Unknown' for row in rows)
    )
    capacity_total = _sum_known(capacity_rows, 'capacity_bytes')

    claims = claim_rows or []
    claims_observed = claim_inventory_observed or bool(claims)
    claim_count = len(claims)
    requested_rows = [row for row in claims if row.get('requested_bytes') is not None]
    used_rows = [row for row in claims if row.get('used_bytes') is not None]
    requested_observed_count = len(requested_rows)
    used_observed_count = len(used_rows)
    requested_available = claims_observed and (claim_count == 0 or requested_observed_count > 0)
    used_available = claims_observed and (claim_count == 0 or used_observed_count > 0)
    requested_complete = claims_observed and requested_observed_count == claim_count
    used_complete = claims_observed and used_observed_count == claim_count
    requested_total = _sum_known(requested_rows, 'requested_bytes')
    used_total = _sum_known(used_rows, 'used_bytes')

    unallocated = max(capacity_total - requested_total, 0.0) if capacity_complete and requested_complete else None
    requested_percent = (
        raw_percent(requested_total, capacity_total)
        if capacity_complete and requested_complete and capacity_total > 0
        else None
    )
    usage_percent = (
        raw_percent(used_total, capacity_total) if capacity_complete and used_complete and capacity_total > 0 else None
    )
    risk = _highest_row_risk(rows)
    if count == 0 and inventory_available:
        risk = {'label': 'No Volumes', 'tone': 'info'}

    requested_gap_count = max(claim_count - requested_observed_count, 0)
    used_gap_count = max(claim_count - used_observed_count, 0)
    return {
        'inventory_evidence_available': inventory_available,
        'status_evidence_available': lifecycle_complete,
        'capacity_evidence_available': capacity_available,
        'capacity_evidence_complete': capacity_complete,
        'requested_claim_evidence_available': requested_available,
        'requested_claim_evidence_complete': requested_complete,
        'observed_claim_usage_evidence_available': used_available,
        'observed_claim_usage_evidence_complete': used_complete,
        'unallocated_evidence_available': (capacity_complete and requested_complete),
        'evidence_available': capacity_available,
        'evidence_complete': (inventory_available and lifecycle_complete and capacity_complete),
        'has_resources': count > 0,
        'count': count,
        'count_display': str(count) if inventory_available else 'N/A',
        'capacity_observed_count': capacity_observed_count,
        'total_claim_count': claim_count,
        'requested_claim_observed_count': requested_observed_count,
        'observed_claim_usage_count': used_observed_count,
        'requested_claim_gap_count': requested_gap_count,
        'observed_claim_usage_gap_count': used_gap_count,
        'requested_claim_coverage_percent': _coverage_percent(
            requested_observed_count,
            claim_count,
            claims_observed,
        ),
        'observed_claim_usage_coverage_percent': _coverage_percent(
            used_observed_count,
            claim_count,
            claims_observed,
        ),
        'requested_claim_coverage_display': _coverage_display(
            requested_observed_count,
            claim_count,
            claims_observed,
        ),
        'observed_claim_usage_coverage_display': _coverage_display(
            used_observed_count,
            claim_count,
            claims_observed,
        ),
        'capacity': format_storage_bytes(
            capacity_total,
            available=capacity_available,
        ),
        'observed_claim_usage': format_storage_bytes(
            used_total,
            available=used_available,
        ),
        'requested_claim_capacity': format_storage_bytes(
            requested_total,
            available=requested_available,
        ),
        'unallocated_provisioned_difference': format_storage_bytes(
            unallocated,
            available=unallocated is not None,
        ),
        'claim_usage_vs_provisioned_percent': (safe_round(usage_percent, 1) if usage_percent is not None else None),
        'requested_vs_provisioned_percent': (
            safe_round(requested_percent, 1) if requested_percent is not None else None
        ),
        'scope_label': 'Cluster',
        'risk': risk,
        'critical_count': _count_risk(rows, 'critical'),
        'warning_count': _count_risk(rows, 'warning'),
        'unknown_count': _count_risk(rows, 'unknown'),
    }


def build_storage_posture(
    filesystem: dict[str, Any],
    pvc: dict[str, Any],
    pv: dict[str, Any],
) -> dict[str, Any]:
    critical_count = sum(int(item.get('critical_count') or 0) for item in (pvc, pv)) + (
        1 if filesystem.get('risk', {}).get('tone') == 'critical' else 0
    )
    warning_count = sum(int(item.get('warning_count') or 0) for item in (pvc, pv)) + (
        1 if filesystem.get('risk', {}).get('tone') == 'warning' else 0
    )
    complete_domains = sum(bool(item.get('evidence_complete')) for item in (filesystem, pvc, pv))
    observed_domains = sum(
        bool(item.get('query_observed') or item.get('inventory_evidence_available') or item.get('evidence_available'))
        for item in (filesystem, pvc, pv)
    )

    if critical_count:
        return {
            'label': 'Critical',
            'tone': 'critical',
            'reason': f'{critical_count} critical storage signal(s) require action.',
            'evidence_complete': complete_domains == 3,
            'critical_count': critical_count,
            'warning_count': warning_count,
        }
    if warning_count:
        return {
            'label': 'Watch',
            'tone': 'warning',
            'reason': f'{warning_count} storage signal(s) require review.',
            'evidence_complete': complete_domains == 3,
            'critical_count': 0,
            'warning_count': warning_count,
        }
    if complete_domains == 3:
        return {
            'label': 'Healthy',
            'tone': 'normal',
            'reason': 'Filesystem, PVC, and PV evidence is complete with no active risk.',
            'evidence_complete': True,
            'critical_count': 0,
            'warning_count': 0,
        }
    if observed_domains:
        return {
            'label': 'Limited Evidence',
            'tone': 'unknown',
            'reason': (
                f'{complete_domains} of 3 storage evidence domains are complete. '
                'Missing evidence is not treated as healthy.'
            ),
            'evidence_complete': False,
            'critical_count': 0,
            'warning_count': 0,
        }
    return {
        'label': 'Unknown',
        'tone': 'unknown',
        'reason': 'No committed storage evidence is available.',
        'evidence_complete': False,
        'critical_count': 0,
        'warning_count': 0,
    }


def build_evidence_state(evidence: StorageEvidence) -> dict[str, Any]:
    domains = {
        'filesystem': (
            evidence.filesystem_var_size,
            evidence.filesystem_var_available,
            evidence.filesystem_root_size,
            evidence.filesystem_root_available,
        ),
        'pvc': (
            evidence.pvc_requested,
            evidence.pvc_capacity,
            evidence.pvc_used,
            evidence.pvc_available,
            evidence.pvc_status,
            evidence.pvc_info,
        ),
        'pv': (evidence.pv_capacity, evidence.pv_status, evidence.pv_info),
    }
    return {
        key: {
            'observed_queries': sum(item.observed for item in items),
            'query_count': len(items),
            'errors': [item.error for item in items if item.error],
            'complete': all(item.observed for item in items),
        }
        for key, items in domains.items()
    }


def _sum_known(rows: Iterable[dict[str, Any]], key: str) -> float:
    return sum(float(row[key]) for row in rows if row.get(key) is not None)


def _count_risk(rows: Iterable[dict[str, Any]], tone: str) -> int:
    return sum(1 for row in rows if isinstance(row.get('risk'), dict) and row['risk'].get('tone') == tone)


def _highest_row_risk(rows: list[dict[str, Any]]) -> dict[str, str]:
    risks = [risk for row in rows if isinstance((risk := row.get('risk')), dict)]
    for tone, label in (
        ('critical', 'Critical'),
        ('warning', 'Watch'),
        ('unknown', 'Unknown'),
    ):
        if any(risk.get('tone') == tone for risk in risks):
            return {'label': label, 'tone': tone}
    if risks:
        return {'label': 'Healthy', 'tone': 'normal'}
    return {'label': 'Unknown', 'tone': 'unknown'}
