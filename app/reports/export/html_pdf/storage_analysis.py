from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, datetime
from html import escape
from typing import Any

from app.reports.export.html_pdf.analytics_publication_standard import (
    ANALYTICS_CANONICAL_REFERENCE,
    ANALYTICS_PUBLICATION_FAMILY,
    ANALYTICS_PUBLICATION_STANDARD,
    analytics_layout_contract,
)


def build_storage_analysis_presentation(
    report: Any,
    payload: Mapping[str, Any],
    *,
    report_id: str,
    report_name: str,
    cluster_scope: str,
    namespace_scope: str,
    period_label: str,
    data_cutoff: str,
    generated_at: str,
    generated_by: str,
    classification: str,
) -> dict[str, Any]:
    cluster = _mapping(payload.get('cluster'))
    storage_summary = _mapping(payload.get('storage_summary'))
    filesystem = _mapping(storage_summary.get('node_filesystem'))
    filesystem_summary = _mapping(filesystem.get('summary'))
    persistent = _mapping(storage_summary.get('persistent_storage'))
    pv = _mapping(persistent.get('pv'))
    pvc = _mapping(persistent.get('pvc'))

    filesystem_rows = _rows(filesystem.get('all_rows') or filesystem.get('rows'))
    pv_rows = _rows(persistent.get('pv_all_rows') or persistent.get('pv_rows'))
    pvc_rows = _rows(persistent.get('pvc_all_rows') or persistent.get('pvc_rows'))

    capacity = _capacity_resource(filesystem_summary, filesystem_rows)
    filesystem_records = _filesystem_records(filesystem_rows)
    pv_summary = _persistent_volume_summary(pv, pv_rows)
    pvc_summary = _persistent_claim_summary(pvc, pvc_rows)

    local_risks = _count_risk_rows(filesystem_rows)
    pvc_risks = _count_risk_rows(pvc_rows)
    pv_risks = _count_risk_rows(pv_rows)
    recommendation_cards = _recommendation_cards(payload)
    actionable_count = sum(1 for item in recommendation_cards if item['actionable'])

    trend = _storage_trend(payload, current=capacity['used_percent'])
    source_rows = _source_rows(payload)
    node_count = _node_count(payload, filesystem)
    evidence_gap_count = sum(
        1
        for available in (
            capacity['evidence_available'],
            bool(filesystem_records),
            pv_summary['evidence_available'],
            pvc_summary['evidence_available'],
            trend['available'],
        )
        if not available
    )

    findings = _executive_findings(
        capacity=capacity,
        local_risks=local_risks,
        filesystem_available=bool(filesystem_records),
        pvc_available=pvc_summary['evidence_available'],
        pv_available=pv_summary['evidence_available'],
    )
    risk_register = _risk_register(
        capacity=capacity,
        local_risks=local_risks,
        filesystem_available=bool(filesystem_records),
        pvc_risks=pvc_risks,
        pvc_available=pvc_summary['evidence_available'],
        pv_risks=pv_risks,
        expansion_available=_expansion_evidence_available(pv_rows, pvc_rows),
    )
    recommendations = _recommendation_plan(
        recommendation_cards=recommendation_cards,
        risk_register=risk_register,
        capacity=capacity,
    )

    environment = _text(cluster.get('environment'), 'Unknown')
    purpose = (
        'Support operational review of aggregate storage utilization, node filesystem evidence, '
        'persistent storage posture, expansion readiness, local-volume exposure, and validation gates.'
    )
    context = (
        'Committed source evidence is collected before rendering. Aggregate capacity, node filesystem, '
        'PV/PVC lifecycle, claim utilization, and expansion support remain separate evidence boundaries.'
    )

    return {
        'presentation_version': 'v3.0-storage-analysis-publication',
        'publication_family': ANALYTICS_PUBLICATION_FAMILY,
        'publication_standard': ANALYTICS_PUBLICATION_STANDARD,
        'canonical_reference': ANALYTICS_CANONICAL_REFERENCE,
        'page_count': 9,
        'layout_contract': analytics_layout_contract(
            page_count=9,
            table_policy='concise-register-plus-reference',
            missing_evidence_policy='explicit-not-available',
        ),
        'report_id': report_id,
        'report_name': report_name,
        'cluster_scope': cluster_scope,
        'namespace_scope': namespace_scope,
        'period_label': period_label,
        'data_cutoff': data_cutoff,
        'generated_at': generated_at,
        'generated_by': generated_by,
        'classification': classification,
        'cover': {
            'environment': environment,
            'purpose': purpose,
            'context': context,
        },
        'executive': {
            'metrics': (
                _metric('Storage Used', capacity['used_display'], capacity['status'], capacity['tone']),
                _metric('Total Capacity', capacity['capacity_display'], capacity['status'], capacity['tone']),
                _metric('Headroom', capacity['headroom_display'], capacity['status'], capacity['tone']),
                _metric(
                    'Local Risks',
                    str(local_risks),
                    'Review' if local_risks else 'Clear',
                    'warning' if local_risks else 'normal',
                ),
            ),
            'capacity': capacity,
            'interpretation_title': _executive_title(capacity, local_risks),
            'interpretation_body': _executive_body(capacity, local_risks, evidence_gap_count),
            'interpretation_note': (
                f'{evidence_gap_count} storage evidence gap(s) remain explicit. '
                'Aggregate headroom does not clear localized filesystem, PV, or PVC risk.'
            ),
            'findings': findings,
        },
        'capacity': {
            'metrics': (
                _metric('Used', capacity['used_display'], capacity['status'], capacity['tone']),
                _metric('Capacity', capacity['capacity_display'], capacity['status'], capacity['tone']),
                _metric('Available', capacity['available_display'], capacity['status'], capacity['tone']),
                _metric('Threshold', '70%', 'Warning Band', 'warning'),
            ),
            'resource': capacity,
            'register': (
                {
                    'ref': 'C1',
                    'scope': 'Node Filesystems',
                    'used': capacity['used_display'],
                    'capacity': capacity['capacity_display'],
                    'available': capacity['available_display'],
                    'headroom': capacity['headroom_display'],
                    'status': capacity['status'],
                    'tone': capacity['tone'],
                },
            ),
            'decision': (
                'No aggregate expansion is indicated by the committed utilization alone. '
                'Validate localized filesystem, PVC, PV, and expansion evidence before approving remediation.'
                if capacity['evidence_available']
                else 'Restore matching used, capacity, and available evidence before assigning an aggregate storage status.'
            ),
        },
        'filesystem': {
            'metrics': (
                _metric(
                    'Filesystem Records',
                    str(len(filesystem_records)) if filesystem_records else 'Not Available',
                    'Committed' if filesystem_records else 'Not Available',
                    'normal' if filesystem_records else 'warning',
                ),
                _metric('Nodes in Scope', str(node_count) if node_count else 'Not Available', 'Committed Inventory' if node_count else 'Unknown', 'normal' if node_count else 'muted'),
                _metric('Highest Usage', _percent(filesystem_summary.get('highest_usage')), _risk_label(filesystem_summary.get('risk')), _risk_tone(filesystem_summary.get('risk'))),
                _metric('Coverage', 'Current' if filesystem_records else 'Partial', 'Query Ready' if filesystem_records else 'Requires Validation', 'normal' if filesystem_records else 'warning'),
            ),
            'available': bool(filesystem_records),
            'summary': capacity,
            'rows': filesystem_records[:5],
            'requirements': (
                {'ref': 'N1', 'evidence': 'Node Identity', 'definition': 'Node and role', 'status': 'Current' if filesystem_records else 'Missing', 'action': 'Monitor' if filesystem_records else 'Required'},
                {'ref': 'N2', 'evidence': 'Filesystem Identity', 'definition': 'Device, mount, and filesystem type', 'status': 'Partial' if filesystem_records else 'Missing', 'action': 'Validate'},
                {'ref': 'N3', 'evidence': 'Capacity Position', 'definition': 'Used, total, and available', 'status': 'Current' if capacity['evidence_available'] else 'Missing', 'action': 'Monitor' if capacity['evidence_available'] else 'Required'},
                {'ref': 'N4', 'evidence': 'Operational State', 'definition': 'Read-only, inode, and pressure state', 'status': 'Partial' if filesystem_records else 'Missing', 'action': 'Validate'},
            ),
            'interpretation': (
                f'{len(filesystem_records)} committed filesystem row(s) are available. '
                f'The highest observed usage is {_percent(filesystem_summary.get("highest_usage"))} on '
                f'{_text(filesystem_summary.get("highest_node"), "an unidentified node")}.'
                if filesystem_records
                else 'Collect and commit node filesystem rows using the same reporting boundary. Missing rows must never become 0% used, 100% free, or Normal.'
            ),
        },
        'persistent': {
            'metrics': (
                _metric('Persistent Volumes', pv_summary['count_display'], 'Committed Inventory' if pv_summary['count'] else 'Not Available', 'normal' if pv_summary['count'] else 'warning'),
                _metric('PVC Utilization', pvc_summary['used_percent_display'], pvc_summary['status'], pvc_summary['tone']),
                _metric('Binding Coverage', _binding_coverage(pv_rows, pvc_rows), 'Review' if pv_rows or pvc_rows else 'Not Available', 'warning' if pv_rows or pvc_rows else 'muted'),
                _metric('Expansion Evidence', 'Available' if _expansion_evidence_available(pv_rows, pvc_rows) else 'Not Available', 'Validate' if _expansion_evidence_available(pv_rows, pvc_rows) else 'Coverage Gap', 'normal' if _expansion_evidence_available(pv_rows, pvc_rows) else 'warning'),
            ),
            'pv': pv_summary,
            'pvc': pvc_summary,
            'pv_donut_svg': _count_donut_svg(pv_summary['count'], 'Persistent Volumes'),
            'register': (
                {'ref': 'P1', 'evidence': 'Persistent Volumes', 'value': pv_summary['count_display'], 'boundary': 'Committed Inventory', 'status': 'Current' if pv_summary['count'] else 'Not Available', 'tone': 'normal' if pv_summary['count'] else 'warning'},
                {'ref': 'P2', 'evidence': 'Persistent Volume Claims', 'value': pvc_summary['count_display'], 'boundary': pvc_summary['scope'], 'status': pvc_summary['status'], 'tone': pvc_summary['tone']},
                {'ref': 'P3', 'evidence': 'Claim Filesystem Usage', 'value': pvc_summary['used_percent_display'], 'boundary': 'Requested Capacity', 'status': pvc_summary['status'], 'tone': pvc_summary['tone']},
                {'ref': 'P4', 'evidence': 'Expansion Support', 'value': 'Available' if _expansion_evidence_available(pv_rows, pvc_rows) else 'Not Available', 'boundary': 'StorageClass / PVC', 'status': 'Review', 'tone': 'warning'},
            ),
            'pv_rows': _pv_records(pv_rows)[:3],
            'pvc_rows': _pvc_records(pvc_rows)[:3],
            'decision': (
                'Use inventory to establish object scope and lifecycle. Do not infer claim free space or expansion readiness from object counts alone.'
            ),
        },
        'risk': {
            'metrics': (
                _metric('Actionable Findings', str(max(actionable_count, len([item for item in risk_register if item['priority'] in {'P1', 'P2'}]))), 'Storage Review', 'warning'),
                _metric('Local Risks', str(local_risks), 'Open' if local_risks else 'Clear', 'warning' if local_risks else 'normal'),
                _metric('Expansion Candidates', 'Not Available' if not _expansion_evidence_available(pv_rows, pvc_rows) else 'Review', 'Coverage Gap' if not _expansion_evidence_available(pv_rows, pvc_rows) else 'Validate', 'warning'),
                _metric('Validation Gates', '5', 'Required', 'info'),
            ),
            'local_risks': local_risks,
            'local_risk_title': (
                f'{local_risks} local filesystem risk item(s) require review.'
                if local_risks
                else 'No committed local filesystem risk item is currently classified as Warning or Critical.'
            ),
            'local_risk_body': (
                'Resolve node, filesystem, mount point, owner, current pressure, and operational impact before remediation.'
                if local_risks
                else 'Continue monitoring filesystem pressure and preserve complete identity evidence.'
            ),
            'expansion_checklist': (
                'StorageClass allows expansion',
                'PVC and PV identities match',
                'Filesystem supports online or offline growth',
                'Application owner and maintenance window are confirmed',
                'Post-change free-capacity target is defined',
            ),
            'register': risk_register,
            'interpretation': 'No expansion, cleanup, migration, or local-volume remediation is authorized by this report alone.',
        },
        'trend': {
            'metrics': (
                _metric('Current Utilization', capacity['used_display'], capacity['status'], capacity['tone']),
                _metric('Current Headroom', capacity['headroom_display'], capacity['status'], capacity['tone']),
                _metric('Historical Series', 'Committed' if trend['historical_available'] else 'Not Available', 'Evidence State', 'normal' if trend['historical_available'] else 'warning'),
                _metric('Forecast Evidence', trend['projection_display'], trend['status'], trend['tone']),
            ),
            **trend,
            'register': (
                {
                    'ref': 'T1',
                    'signal': 'Storage',
                    'current': capacity['used_display'],
                    'projection': trend['projection_display'],
                    'assessment': trend['assessment'],
                    'tone': trend['tone'],
                },
                {
                    'ref': 'T2',
                    'signal': 'Evidence',
                    'current': 'Committed Snapshot' if capacity['evidence_available'] else 'Not Available',
                    'projection': 'Committed Series' if trend['available'] else 'Not Available',
                    'assessment': 'Current' if trend['available'] else 'Review',
                    'tone': 'normal' if trend['available'] else 'warning',
                },
            ),
            'interpretation': _trend_interpretation(capacity, trend),
        },
        'recommendations': {
            'metrics': _recommendation_metrics(recommendations),
            'items': recommendations,
            'governance': (
                {'field': 'Primary Action', 'requirement': recommendations[0]['title'] if recommendations else 'Maintain committed storage evidence.'},
                {'field': 'Validation Criteria', 'requirement': 'Confirm unit, scope, identity, live metric, owner, maintenance window, and rollback plan.'},
                {'field': 'Assigned Owners', 'requirement': _assigned_owners(recommendations)},
                {'field': 'Change Control', 'requirement': 'No storage expansion, cleanup, or migration is authorized by this report alone.'},
            ),
        },
        'methodology': {
            'metrics': (
                _metric('Data Sources', str(len(source_rows)), 'Active / Partial', 'warning' if evidence_gap_count else 'normal'),
                _metric('Coverage', f'{node_count} Nodes' if node_count else 'Node Scope', namespace_scope, 'normal' if node_count else 'muted'),
                _metric('Capacity Basis', 'Used / Total', 'Committed', 'normal'),
                _metric('Observation Boundary', 'Snapshot', 'Committed', 'normal'),
            ),
            'sources': source_rows,
            'rules': (
                {'ref': 'M1', 'rule': 'Reporting Period', 'setting': period_label},
                {'ref': 'M2', 'rule': 'Data Cut-Off', 'setting': data_cutoff},
                {'ref': 'M3', 'rule': 'Threshold Bands', 'setting': '70% / 85%'},
                {'ref': 'M4', 'rule': 'Capacity Basis', 'setting': 'Used / total; matching scope'},
                {'ref': 'M5', 'rule': 'Missing Evidence', 'setting': 'Explicit Not Available'},
            ),
            'references': (
                {'ref': 'M3', 'title': 'Threshold Bands', 'description': 'Normal below 70%, warning from 70% to 84.9%, and critical at 85% or above.'},
                {'ref': 'M4', 'title': 'Capacity Basis', 'description': 'Used and total must share units, scope, resource identity, and data cut-off.'},
                {'ref': 'M5', 'title': 'Missing Evidence', 'description': 'Unavailable evidence remains explicit and is never converted to zero.'},
            ),
            'included': (
                'Committed aggregate filesystem capacity and utilization when available.',
                'Committed filesystem, PV, PVC, lifecycle, and risk evidence returned by the collector.',
                'Optional committed storage forecast evidence when available.',
            ),
            'excluded': (
                'Live cluster state after the data cut-off.',
                'Unapproved change windows and in-flight maintenance.',
                'Filesystem or claim utilization not present in committed evidence.',
            ),
            'limitations': (
                'Aggregate headroom does not clear localized filesystem or claim risk.',
                'Inventory objects do not establish filesystem utilization or expansion support.',
                'Validate all recommendations against live cluster state before remediation.',
            ),
            'status_language': (
                {'ref': 'S1', 'title': 'Not Available', 'description': 'No evidence exists for the requested dimension.'},
                {'ref': 'S2', 'title': 'Not Collected', 'description': 'Collection was prevented by configuration, permission, or failure.'},
                {'ref': 'S3', 'title': 'Partial Coverage', 'description': 'Evidence exists but does not cover the full requested scope.'},
                {'ref': 'S4', 'title': 'Source Unavailable', 'description': 'The source was unreachable or not providing data at the cut-off.'},
            ),
        },
    }


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _rows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if number != number:
        return default
    return number


def _safe_int(value: Any, default: int = 0) -> int:
    number = _safe_float(value)
    return int(number) if number is not None else default


def _text(value: Any, fallback: str = 'Not Available') -> str:
    if value is None:
        return fallback
    result = str(value).strip()
    return result or fallback


def _metric(label: str, value: str, status: str, tone: str) -> dict[str, str]:
    return {'label': label, 'value': value, 'status': status, 'tone': tone}


def _percent(value: Any, fallback: str = 'Not Available') -> str:
    number = _safe_float(value)
    return f'{number:.1f}%' if number is not None else fallback


def _status_from_percent(percent: float | None) -> tuple[str, str]:
    if percent is None:
        return 'Not Available', 'warning'
    if percent >= 85:
        return 'Critical', 'critical'
    if percent >= 70:
        return 'Warning', 'warning'
    return 'Normal', 'normal'


def _capacity_resource(summary: Mapping[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    capacity_bytes = sum(max(0.0, _safe_float(item.get('capacity_bytes'), 0.0) or 0.0) for item in rows if item.get('evidence_available'))
    used_bytes = sum(max(0.0, _safe_float(item.get('used_bytes'), 0.0) or 0.0) for item in rows if item.get('evidence_available'))
    free_bytes = sum(max(0.0, _safe_float(item.get('free_bytes'), 0.0) or 0.0) for item in rows if item.get('evidence_available'))
    evidence_available = bool(summary.get('evidence_available')) or capacity_bytes > 0
    used_percent = _safe_float(summary.get('usage_percent'))
    headroom_percent = _safe_float(summary.get('free_percent'))
    if evidence_available and used_percent is None and capacity_bytes > 0:
        used_percent = used_bytes / capacity_bytes * 100
    if evidence_available and headroom_percent is None and capacity_bytes > 0:
        headroom_percent = free_bytes / capacity_bytes * 100
    status, tone = _status_from_percent(used_percent)
    return {
        'evidence_available': evidence_available,
        'used_display': _text(summary.get('used')) if evidence_available else 'Not Available',
        'capacity_display': _text(summary.get('capacity')) if evidence_available else 'Not Available',
        'available_display': _text(summary.get('free')) if evidence_available else 'Not Available',
        'used_percent': round(max(0.0, min(100.0, used_percent or 0.0)), 1),
        'headroom_percent': round(max(0.0, min(100.0, headroom_percent or 0.0)), 1),
        'used_percent_display': _percent(used_percent),
        'headroom_display': _percent(headroom_percent),
        'status': status,
        'tone': tone,
    }


def _risk_tone(value: Any) -> str:
    mapping = _mapping(value)
    tone = _text(mapping.get('tone'), '').lower()
    if tone in {'normal', 'warning', 'critical', 'info'}:
        return tone
    label = _text(mapping.get('label'), '').lower()
    if label in {'critical', 'high'}:
        return 'critical'
    if label in {'warning', 'watch', 'medium'}:
        return 'warning'
    if label in {'healthy', 'normal', 'available'}:
        return 'normal'
    return 'muted'


def _risk_label(value: Any) -> str:
    mapping = _mapping(value)
    return _text(mapping.get('label'), 'Not Available')


def _count_risk_rows(rows: list[dict[str, Any]]) -> int:
    count = 0
    for row in rows:
        tone = _risk_tone(row.get('risk'))
        status = _text(row.get('status'), '').lower()
        if tone in {'warning', 'critical'} or status in {'pending', 'lost', 'released', 'failed'}:
            count += 1
    return count


def _filesystem_records(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        if not row.get('evidence_available'):
            continue
        result.append(
            {
                'ref': f'N{index}',
                'node': _text(row.get('node'), '-'),
                'mountpoint': _text(row.get('mountpoint'), '-'),
                'used': _text(row.get('used')),
                'capacity': _text(row.get('capacity')),
                'free': _text(row.get('free')),
                'usage': _percent(row.get('usage_percent')),
                'risk': _risk_label(row.get('risk')),
                'tone': _risk_tone(row.get('risk')),
            }
        )
    return sorted(result, key=lambda item: _safe_float(item['usage'].rstrip('%'), 0.0) or 0.0, reverse=True)


def _persistent_volume_summary(summary: Mapping[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    count = _safe_int(summary.get('count'), len(rows))
    evidence_available = bool(summary.get('evidence_available')) or bool(rows)
    return {
        'evidence_available': evidence_available,
        'count': count,
        'count_display': str(count) if count else 'Not Available',
        'capacity': _text(summary.get('capacity')) if evidence_available else 'Not Available',
        'observed_claim_usage': _text(summary.get('observed_claim_usage')) if evidence_available else 'Not Available',
        'requested_claim_capacity': _text(summary.get('requested_claim_capacity')) if evidence_available else 'Not Available',
        'unallocated': _text(summary.get('unallocated_provisioned_difference')) if evidence_available else 'Not Available',
    }


def _persistent_claim_summary(summary: Mapping[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    count = _safe_int(summary.get('count'), len(rows))
    used_percent = _safe_float(summary.get('used_percent'))
    evidence_available = bool(summary.get('evidence_available')) or any(item.get('evidence_available') for item in rows)
    status, tone = _status_from_percent(used_percent)
    return {
        'evidence_available': evidence_available,
        'count': count,
        'count_display': str(count) if count else 'Not Available',
        'requested': _text(summary.get('requested')) if evidence_available else 'Not Available',
        'used': _text(summary.get('used')) if evidence_available else 'Not Available',
        'free': _text(summary.get('free')) if evidence_available else 'Not Available',
        'used_percent': round(used_percent, 1) if used_percent is not None else None,
        'used_percent_display': _percent(used_percent),
        'free_percent_display': _percent(summary.get('free_percent')),
        'scope': _text(summary.get('scope_label'), 'All Namespaces'),
        'status': status,
        'tone': tone,
    }


def _pv_records(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        result.append(
            {
                'ref': f'PV{index}',
                'name': _text(row.get('name'), '-'),
                'status': _text(row.get('status'), 'Unknown'),
                'capacity': _text(row.get('capacity')),
                'storage_class': _text(row.get('storage_class'), 'No StorageClass'),
                'claim': _text(row.get('claim'), '-'),
                'risk': _risk_label(row.get('risk')),
                'tone': _risk_tone(row.get('risk')),
            }
        )
    return result


def _pvc_records(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        result.append(
            {
                'ref': f'PVC{index}',
                'name': _text(row.get('name'), '-'),
                'namespace': _text(row.get('namespace'), '-'),
                'status': _text(row.get('status'), 'Unknown'),
                'requested': _text(row.get('requested')),
                'used': _text(row.get('used')),
                'usage': _percent(row.get('usage_percent')),
                'risk': _risk_label(row.get('risk')),
                'tone': _risk_tone(row.get('risk')),
            }
        )
    return result


def _binding_coverage(pv_rows: list[dict[str, Any]], pvc_rows: list[dict[str, Any]]) -> str:
    if not pv_rows and not pvc_rows:
        return 'Not Available'
    bound = sum(1 for row in pv_rows if _text(row.get('status'), '').lower() == 'bound')
    if pv_rows:
        return f'{bound} / {len(pv_rows)} Bound'
    return f'{len(pvc_rows)} PVC Records'


def _expansion_evidence_available(pv_rows: list[dict[str, Any]], pvc_rows: list[dict[str, Any]]) -> bool:
    # Current collector does not expose StorageClass allowVolumeExpansion. Keep the
    # state explicit unless a future row supplies a positive expansion field.
    return any(bool(row.get('allow_expansion') or row.get('expansion_supported')) for row in [*pv_rows, *pvc_rows])


def _recommendation_cards(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = payload.get('recommendation_cards') or payload.get('actionable_recommendations') or ()
    result: list[dict[str, Any]] = []
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes, bytearray)):
        return result
    for item in raw:
        if not isinstance(item, Mapping):
            continue
        priority_raw = _text(item.get('priority'), 'Info')
        priority = {'critical': 'P1', 'warning': 'P2', 'review': 'P2', 'normal': 'P3', 'info': 'P3'}.get(priority_raw.lower(), priority_raw if priority_raw in {'P1', 'P2', 'P3'} else 'P3')
        result.append(
            {
                'title': _text(item.get('title'), 'Review Storage Evidence'),
                'description': _text(item.get('description'), 'Validate the committed storage evidence and ownership boundary.'),
                'priority': priority,
                'owner': _owner_for_source(_text(item.get('source'), 'storage')),
                'actionable': bool(item.get('is_actionable', True)),
            }
        )
    return result


def _owner_for_source(source: str) -> str:
    if any(token in source.lower() for token in ('metric', 'observability', 'coverage')):
        return 'Observability Owner'
    return 'Platform Operations'


def _executive_findings(*, capacity: Mapping[str, Any], local_risks: int, filesystem_available: bool, pvc_available: bool, pv_available: bool) -> tuple[dict[str, str], ...]:
    findings: list[dict[str, str]] = []
    if local_risks:
        findings.append(_finding('F1', 'P2', 'Review Local Filesystem Risk', 'Platform Operations', 'Open', 'warning', f'{local_risks} filesystem risk item(s) require identity, owner, live-state, and remediation validation.'))
    if not filesystem_available:
        findings.append(_finding('F2', 'P2', 'Restore Node Filesystem Coverage', 'Observability Owner', 'Review', 'warning', 'Collect node, mount, used, capacity, available, and operational-state evidence.'))
    if not pvc_available or not pv_available:
        findings.append(_finding('F3', 'P3', 'Restore PV/PVC Evidence Coverage', 'Observability Owner', 'Planned', 'info', 'Keep persistent inventory, claim utilization, and lifecycle evidence explicit and scope-aligned.'))
    findings.append(_finding('F4', 'P3', 'Maintain Aggregate Headroom Monitoring', 'Platform Operations', 'Current' if capacity.get('evidence_available') else 'Review', 'normal' if capacity.get('evidence_available') else 'warning', 'Continue threshold monitoring without using aggregate headroom to clear localized risk.'))
    return tuple(findings[:4])


def _finding(ref: str, priority: str, title: str, owner: str, status: str, tone: str, description: str) -> dict[str, str]:
    return {'ref': ref, 'priority': priority, 'title': title, 'owner': owner, 'status': status, 'tone': tone, 'description': description}


def _executive_title(capacity: Mapping[str, Any], local_risks: int) -> str:
    if not capacity.get('evidence_available'):
        return 'Aggregate storage capacity evidence is not available.'
    if local_risks:
        return 'Aggregate storage remains below warning, with localized risk still open.'
    return 'Aggregate storage is below the warning band.'


def _executive_body(capacity: Mapping[str, Any], local_risks: int, gaps: int) -> str:
    if not capacity.get('evidence_available'):
        return 'No aggregate capacity conclusion can be assigned until matching used, total, and available evidence is committed.'
    return (
        f'Committed utilization is {capacity["used_percent_display"]}, leaving {capacity["headroom_display"]} headroom. '
        f'{local_risks} localized risk item(s) and {gaps} evidence gap(s) remain separate from the aggregate denominator.'
    )


def _risk_register(*, capacity: Mapping[str, Any], local_risks: int, filesystem_available: bool, pvc_risks: int, pvc_available: bool, pv_risks: int, expansion_available: bool) -> tuple[dict[str, str], ...]:
    rows: list[dict[str, str]] = []
    if local_risks:
        rows.append(_risk('R1', 'Local Filesystem Risk', 'P2', 'Medium', 'Platform Operations', 'Open', 'warning', 'Resolve filesystem identity, owner, impact, and live pressure before remediation.'))
    if not filesystem_available:
        rows.append(_risk('R2', 'Filesystem Coverage Gap', 'P2', 'Medium', 'Observability Owner', 'Review', 'warning', 'Node filesystem evidence is incomplete or unavailable.'))
    if pvc_risks or not pvc_available:
        rows.append(_risk('R3', 'PVC Utilization Coverage', 'P2' if pvc_risks else 'P3', 'Medium' if pvc_risks else 'Low', 'Observability Owner', 'Open' if pvc_risks else 'Planned', 'warning' if pvc_risks else 'info', f'{pvc_risks} PVC risk item(s) detected; claim utilization coverage must remain explicit.'))
    if pv_risks:
        rows.append(_risk('R4', 'PV Lifecycle Risk', 'P2', 'Medium', 'Platform Operations', 'Open', 'warning', f'{pv_risks} PV lifecycle risk item(s) require reclaim-policy and binding review.'))
    if not expansion_available:
        rows.append(_risk('R5', 'Expansion Support Unknown', 'P3', 'Low', 'Platform Operations', 'Planned', 'info', 'StorageClass expansion and filesystem growth capability are not committed in the current evidence.'))
    if not rows:
        rows.append(_risk('R1', 'Aggregate Capacity Monitoring', 'P3', 'Low', 'Platform Operations', 'Current', 'normal', f'Aggregate storage remains {capacity.get("status", "Normal")} at the committed cut-off.'))
    return tuple(rows[:5])


def _risk(ref: str, title: str, priority: str, impact: str, owner: str, status: str, tone: str, description: str) -> dict[str, str]:
    return {'ref': ref, 'title': title, 'priority': priority, 'impact': impact, 'owner': owner, 'status': status, 'tone': tone, 'description': description}


def _recommendation_plan(*, recommendation_cards: list[dict[str, Any]], risk_register: tuple[dict[str, str], ...], capacity: Mapping[str, Any]) -> tuple[dict[str, str], ...]:
    items: list[dict[str, str]] = []
    for card in recommendation_cards:
        if not card['actionable']:
            continue
        items.append(
            {
                'ref': '',
                'priority': card['priority'],
                'title': card['title'],
                'owner': card['owner'],
                'target': 'Next Week' if card['priority'] in {'P1', 'P2'} else 'This Month',
                'status': 'Open' if card['priority'] in {'P1', 'P2'} else 'Planned',
                'tone': 'critical' if card['priority'] == 'P1' else 'warning' if card['priority'] == 'P2' else 'info',
                'description': card['description'],
            }
        )
    for risk in risk_register:
        if any(item['title'].lower() == risk['title'].lower() for item in items):
            continue
        items.append(
            {
                'ref': '',
                'priority': risk['priority'],
                'title': _recommendation_title(risk['title']),
                'owner': risk['owner'],
                'target': 'Next Week' if risk['priority'] in {'P1', 'P2'} else 'This Month',
                'status': 'Open' if risk['priority'] in {'P1', 'P2'} else 'Planned',
                'tone': risk['tone'],
                'description': risk['description'],
            }
        )
    if capacity.get('evidence_available') and not any('headroom' in item['title'].lower() or 'capacity monitoring' in item['title'].lower() for item in items):
        items.append(
            {
                'ref': '', 'priority': 'P3', 'title': 'Maintain Aggregate Capacity Monitoring',
                'owner': 'Platform Operations', 'target': 'This Month', 'status': 'Current', 'tone': 'normal',
                'description': f'Continue monitoring {capacity.get("used_percent_display")} aggregate utilization while preserving threshold and denominator evidence.',
            }
        )
    rank = {'P1': 0, 'P2': 1, 'P3': 2}
    items.sort(key=lambda item: (rank.get(item['priority'], 9), item['title']))
    for index, item in enumerate(items[:5], start=1):
        item['ref'] = f'A{index}'
    return tuple(items[:5])


def _recommendation_title(risk_title: str) -> str:
    if risk_title.startswith('Local'):
        return f'Identify and Validate {risk_title}'
    if 'Coverage Gap' in risk_title:
        return f'Restore {risk_title.replace(" Gap", "")}'
    if 'Unknown' in risk_title:
        return f'Validate {risk_title.replace(" Unknown", "")}'
    return f'Review {risk_title}'


def _recommendation_metrics(items: tuple[dict[str, str], ...]) -> tuple[dict[str, str], ...]:
    counts = {priority: sum(1 for item in items if item['priority'] == priority) for priority in ('P1', 'P2', 'P3')}
    return (
        _metric('P1 Actions', str(counts['P1']), 'Open' if counts['P1'] else 'None', 'critical' if counts['P1'] else 'normal'),
        _metric('P2 Actions', str(counts['P2']), 'Open' if counts['P2'] else 'None', 'warning' if counts['P2'] else 'normal'),
        _metric('P3 Actions', str(counts['P3']), 'Planned' if counts['P3'] else 'None', 'info' if counts['P3'] else 'normal'),
        _metric('Validation Gates', str(len(items)), 'Required', 'info'),
    )


def _assigned_owners(items: tuple[dict[str, str], ...]) -> str:
    owners: dict[str, int] = {}
    for item in items:
        owners[item['owner']] = owners.get(item['owner'], 0) + 1
    return '; '.join(f'{owner}: {count} action(s)' for owner, count in owners.items()) or 'No action owner assigned.'


def _storage_trend(payload: Mapping[str, Any], *, current: float) -> dict[str, Any]:
    forecast = _mapping(payload.get('forecast_payload'))
    items = _rows(forecast.get('items'))
    storage_item = next((item for item in items if _text(item.get('key'), '').lower() == 'storage'), {})
    historical = _point_values(storage_item.get('historical_points'))
    projected = _point_values(storage_item.get('forecast_points'))
    projected_percent = _safe_float(storage_item.get('projected_percent'))
    if projected_percent is None and projected:
        projected_percent = projected[-1]
    historical_available = bool(historical)
    available = bool(historical or projected or projected_percent is not None)
    projection_display = _percent(projected_percent)
    assessment_status, assessment_tone = _status_from_percent(projected_percent if projected_percent is not None else current if available else None)
    assessment = 'Stable' if projected_percent is not None and projected_percent < 70 else assessment_status if available else 'Review'
    return {
        'available': available,
        'historical_available': historical_available,
        'projection_percent': projected_percent,
        'projection_display': projection_display,
        'status': 'Committed' if available else 'Not Available',
        'tone': assessment_tone if available else 'warning',
        'assessment': assessment,
        'method': _text(forecast.get('method_label') or forecast.get('forecast_method'), 'Not Available'),
        'horizon': _text(forecast.get('forecast_horizon'), 'Not Available'),
        'chart_svg': _trend_svg(historical, projected, current=current, projection=projected_percent) if available else '',
    }


def _point_values(value: Any) -> list[float]:
    result: list[float] = []
    for item in _rows(value):
        number = _safe_float(item.get('percent', item.get('value')))
        if number is not None:
            result.append(max(0.0, min(100.0, number)))
    return result


def _trend_interpretation(capacity: Mapping[str, Any], trend: Mapping[str, Any]) -> str:
    if not capacity.get('evidence_available'):
        return 'No aggregate trend conclusion can be made without committed current capacity evidence.'
    if not trend.get('available'):
        return 'Current aggregate capacity is available, but committed historical and forecast evidence are not available. Continue collection before using this report for expansion planning.'
    projection = _safe_float(trend.get('projection_percent'))
    if projection is not None and projection >= 70:
        return f'Storage is projected to reach {projection:.1f}%, which requires planning review before the warning-band exposure becomes operational.'
    return 'Current and projected aggregate storage remain below the warning band within the available committed horizon.'


def _source_rows(payload: Mapping[str, Any]) -> tuple[dict[str, str], ...]:
    rows = _rows(payload.get('source_evidence'))
    result: list[dict[str, str]] = []
    for item in rows[:4]:
        result.append(
            {
                'source': _text(item.get('source')),
                'freshness': _text(item.get('freshness')),
                'last_collected': _format_temporal(item.get('last_collected')),
            }
        )
    if result:
        return tuple(result)
    return (
        {'source': 'Prometheus Observation Cache', 'freshness': 'Not Available', 'last_collected': 'Not Available'},
        {'source': 'Kubernetes Storage Inventory', 'freshness': 'Committed', 'last_collected': 'At report cut-off'},
        {'source': 'Storage Analysis Evidence', 'freshness': 'Current', 'last_collected': 'At report cut-off'},
        {'source': 'Forecast Evidence', 'freshness': 'Not Available', 'last_collected': 'Not Available'},
    )


def _format_temporal(value: Any) -> str:
    if isinstance(value, datetime):
        return value.strftime('%d %b %Y %H:%M UTC')
    if isinstance(value, date):
        return value.strftime('%d %b %Y')
    return _text(value)


def _node_count(payload: Mapping[str, Any], filesystem: Mapping[str, Any]) -> int:
    cluster_info = _mapping(payload.get('cluster_info'))
    total = _safe_int(cluster_info.get('total_nodes'))
    if total:
        return total
    nodes = filesystem.get('available_nodes')
    if isinstance(nodes, Sequence) and not isinstance(nodes, (str, bytes, bytearray)):
        return len(set(str(item) for item in nodes if item))
    return len({str(row.get('node')) for row in _rows(filesystem.get('all_rows') or filesystem.get('rows')) if row.get('node')})


def _count_donut_svg(count: int, label: str) -> str:
    safe_count = max(0, count)
    return (
        '<svg viewBox="0 0 180 180" role="img" aria-label="'
        + escape(f'{safe_count} {label}')
        + '"><circle cx="90" cy="90" r="55" fill="none" stroke="#E2E8F0" stroke-width="24"/>'
        '<circle cx="90" cy="90" r="55" fill="none" stroke="#7C3AED" stroke-width="24" '
        'stroke-dasharray="345.6 345.6" transform="rotate(-90 90 90)"/>'
        f'<text x="90" y="88" text-anchor="middle" font-size="30" font-weight="700" fill="#172033">{safe_count}</text>'
        f'<text x="90" y="112" text-anchor="middle" font-size="10" fill="#64748B">{escape(label)}</text></svg>'
    )


def _trend_svg(historical: list[float], projected: list[float], *, current: float, projection: float | None) -> str:
    width, height = 760, 250
    left, right, top, bottom = 58, 22, 18, 42
    chart_w = width - left - right
    chart_h = height - top - bottom
    history_values = historical[:] or [current]
    if history_values[-1] != current:
        history_values.append(current)
    forecast_values = projected[:]
    if projection is not None and (not forecast_values or forecast_values[-1] != projection):
        forecast_values.append(projection)
    all_count = max(2, len(history_values) + len(forecast_values))
    cutoff_index = len(history_values) - 1

    def x(index: int) -> float:
        return left + chart_w * index / max(1, all_count - 1)

    def y(value: float) -> float:
        return top + chart_h * (1 - max(0.0, min(100.0, value)) / 100)

    parts = [f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="Storage utilization trend">']
    parts.append(f'<rect x="0" y="0" width="{width}" height="{height}" fill="#FFFFFF"/>')
    for tick in (0, 25, 50, 70, 85, 100):
        yy = y(float(tick))
        color = '#D97706' if tick == 70 else '#DC2626' if tick == 85 else '#E2E8F0'
        dash = ' stroke-dasharray="5 5"' if tick in {70, 85} else ''
        parts.append(f'<line x1="{left}" y1="{yy:.1f}" x2="{width-right}" y2="{yy:.1f}" stroke="{color}" stroke-width="1"{dash}/>')
        parts.append(f'<text x="{left-12}" y="{yy+3:.1f}" text-anchor="end" font-size="9" fill="#64748B">{tick}%</text>')
    cutoff_x = x(cutoff_index)
    parts.append(f'<line x1="{cutoff_x:.1f}" y1="{top}" x2="{cutoff_x:.1f}" y2="{height-bottom}" stroke="#A78BFA" stroke-width="1" stroke-dasharray="4 4"/>')
    history_points = ' '.join(f'{x(index):.1f},{y(value):.1f}' for index, value in enumerate(history_values))
    parts.append(f'<polyline points="{history_points}" fill="none" stroke="#7C3AED" stroke-width="4" stroke-linejoin="round" stroke-linecap="round"/>')
    if forecast_values:
        forecast_series = [history_values[-1], *forecast_values]
        forecast_points = ' '.join(f'{x(cutoff_index + index):.1f},{y(value):.1f}' for index, value in enumerate(forecast_series))
        parts.append(f'<polyline points="{forecast_points}" fill="none" stroke="#7C3AED" stroke-width="4" stroke-dasharray="8 6" stroke-linejoin="round" stroke-linecap="round"/>')
    end_value = forecast_values[-1] if forecast_values else history_values[-1]
    end_x = x(cutoff_index + len(forecast_values))
    end_y = y(end_value)
    parts.append(f'<circle cx="{end_x:.1f}" cy="{end_y:.1f}" r="5" fill="#7C3AED"/>')
    parts.append(f'<text x="{end_x-6:.1f}" y="{end_y-10:.1f}" text-anchor="end" font-size="12" font-weight="700" fill="#7C3AED">{end_value:.1f}%</text>')
    parts.append(f'<text x="{left}" y="{height-14}" font-size="10" fill="#64748B">Historical Start</text>')
    parts.append(f'<text x="{cutoff_x:.1f}" y="{height-14}" text-anchor="middle" font-size="10" fill="#64748B">Cut-off</text>')
    parts.append(f'<text x="{width-right}" y="{height-14}" text-anchor="end" font-size="10" fill="#64748B">Horizon</text>')
    parts.append('</svg>')
    return ''.join(parts)
