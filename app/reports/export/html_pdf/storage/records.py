from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.reports.export.html_pdf.storage.model import (
    percent,
    risk_label,
    risk_tone,
    safe_float,
    safe_int,
    status_from_percent,
    text,
)


def capacity_resource(summary: Mapping[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    capacity_bytes = sum(
        max(0.0, safe_float(item.get('capacity_bytes'), 0.0) or 0.0) for item in rows if item.get('evidence_available')
    )
    used_bytes = sum(
        max(0.0, safe_float(item.get('used_bytes'), 0.0) or 0.0) for item in rows if item.get('evidence_available')
    )
    free_bytes = sum(
        max(0.0, safe_float(item.get('free_bytes'), 0.0) or 0.0) for item in rows if item.get('evidence_available')
    )
    evidence_available = bool(summary.get('evidence_available')) or capacity_bytes > 0
    used_percent = safe_float(summary.get('usage_percent'))
    headroom_percent = safe_float(summary.get('free_percent'))
    if evidence_available and used_percent is None and capacity_bytes > 0:
        used_percent = used_bytes / capacity_bytes * 100
    if evidence_available and headroom_percent is None and capacity_bytes > 0:
        headroom_percent = free_bytes / capacity_bytes * 100
    status, tone = status_from_percent(used_percent)
    return {
        'evidence_available': evidence_available,
        'used_display': text(summary.get('used')) if evidence_available else 'Not Available',
        'capacity_display': text(summary.get('capacity')) if evidence_available else 'Not Available',
        'available_display': text(summary.get('free')) if evidence_available else 'Not Available',
        'used_percent': round(max(0.0, min(100.0, used_percent or 0.0)), 1),
        'headroom_percent': round(max(0.0, min(100.0, headroom_percent or 0.0)), 1),
        'used_percent_display': percent(used_percent),
        'headroom_display': percent(headroom_percent),
        'status': status,
        'tone': tone,
    }


def count_risk_rows(rows: list[dict[str, Any]]) -> int:
    count = 0
    for row in rows:
        tone = risk_tone(row.get('risk'))
        status = text(row.get('status'), '').lower()
        if tone in {'warning', 'critical'} or status in {'pending', 'lost', 'released', 'failed'}:
            count += 1
    return count


def filesystem_records(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        if not row.get('evidence_available'):
            continue
        result.append(
            {
                'ref': f'N{index}',
                'node': text(row.get('node'), '-'),
                'mountpoint': text(row.get('mountpoint'), '-'),
                'used': text(row.get('used')),
                'capacity': text(row.get('capacity')),
                'free': text(row.get('free')),
                'usage': percent(row.get('usage_percent')),
                'risk': risk_label(row.get('risk')),
                'tone': risk_tone(row.get('risk')),
            }
        )
    return sorted(result, key=lambda item: safe_float(item['usage'].rstrip('%'), 0.0) or 0.0, reverse=True)


def persistent_volume_summary(summary: Mapping[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    count = safe_int(summary.get('count'), len(rows))
    evidence_available = bool(summary.get('capacity_evidence_available')) or bool(rows)
    return {
        'evidence_available': evidence_available,
        'count': count,
        'count_display': str(count) if summary.get('inventory_evidence_available') or rows else 'Not Available',
        'capacity': text(summary.get('capacity')) if evidence_available else 'Not Available',
        'observed_claim_usage': text(summary.get('observed_claim_usage')) if evidence_available else 'Not Available',
        'requested_claim_capacity': text(summary.get('requested_claim_capacity'))
        if evidence_available
        else 'Not Available',
        'unallocated': text(summary.get('unallocated_provisioned_difference'))
        if evidence_available
        else 'Not Available',
    }


def persistent_claim_summary(summary: Mapping[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    count = safe_int(summary.get('count'), len(rows))
    used_percent = safe_float(summary.get('used_percent'))
    evidence_available = bool(summary.get('pressure_evidence_available')) or any(
        item.get('evidence_available') for item in rows
    )
    status, tone = status_from_percent(used_percent) if evidence_available else ('Unknown', 'muted')
    return {
        'evidence_available': evidence_available,
        'count': count,
        'count_display': str(count) if summary.get('inventory_evidence_available') or rows else 'Not Available',
        'requested': text(summary.get('requested')) if summary.get('requested_evidence_available') else 'Not Available',
        'used': text(summary.get('used')) if evidence_available else 'Not Available',
        'free': text(summary.get('free')) if evidence_available else 'Not Available',
        'used_percent': round(used_percent, 1) if used_percent is not None else None,
        'used_percent_display': percent(used_percent),
        'free_percent_display': percent(summary.get('free_percent')),
        'scope': text(summary.get('scope_label'), 'All Namespaces'),
        'status': status,
        'tone': tone,
    }


def pv_records(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            'ref': f'PV{index}',
            'name': text(row.get('name'), '-'),
            'status': text(row.get('status'), 'Unknown'),
            'capacity': text(row.get('capacity')),
            'storage_class': text(row.get('storage_class'), 'No StorageClass'),
            'claim': text(row.get('claim'), '-'),
            'risk': risk_label(row.get('risk')),
            'tone': risk_tone(row.get('risk')),
        }
        for index, row in enumerate(rows, start=1)
    ]


def pvc_records(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            'ref': f'PVC{index}',
            'name': text(row.get('name'), '-'),
            'namespace': text(row.get('namespace'), '-'),
            'status': text(row.get('status'), 'Unknown'),
            'requested': text(row.get('requested')),
            'used': text(row.get('used')),
            'usage': percent(row.get('usage_percent')),
            'risk': risk_label(row.get('risk')),
            'tone': risk_tone(row.get('risk')),
        }
        for index, row in enumerate(rows, start=1)
    ]


def binding_coverage(pv_rows: list[dict[str, Any]], pvc_rows: list[dict[str, Any]]) -> str:
    if not pv_rows and not pvc_rows:
        return 'Not Available'
    bound = sum(1 for row in pv_rows if text(row.get('status'), '').lower() == 'bound')
    if pv_rows:
        return f'{bound} / {len(pv_rows)} Bound'
    return f'{len(pvc_rows)} PVC Records'


def expansion_evidence_available(pv_rows: list[dict[str, Any]], pvc_rows: list[dict[str, Any]]) -> bool:
    return any(bool(row.get('allow_expansion') or row.get('expansion_supported')) for row in [*pv_rows, *pvc_rows])
