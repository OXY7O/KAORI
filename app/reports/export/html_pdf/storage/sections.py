from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.reports.export.html_pdf.publication_visuals import count_donut_svg
from app.reports.export.html_pdf.storage.actions import (
    assigned_owners,
    executive_body,
    executive_title,
    recommendation_metrics,
)
from app.reports.export.html_pdf.storage.model import (
    format_temporal,
    metric,
    percent,
    risk_label,
    risk_tone,
    rows,
    text,
)
from app.reports.export.html_pdf.storage.records import (
    binding_coverage,
    expansion_evidence_available,
    pv_records,
    pvc_records,
)
from app.reports.export.html_pdf.storage.trend import trend_interpretation


def cover_section(cluster: Mapping[str, Any]) -> dict[str, str]:
    return {
        'environment': text(cluster.get('environment'), 'Unknown'),
        'purpose': 'Support operational review of aggregate storage utilization, node filesystem evidence, persistent storage posture, expansion readiness, local-volume exposure, and validation gates.',
        'context': 'Committed source evidence is collected before rendering. Aggregate capacity, node filesystem, PV/PVC lifecycle, claim utilization, and expansion support remain separate evidence boundaries.',
    }


def executive_section(
    *, capacity: Mapping[str, Any], local_risks: int, evidence_gap_count: int, findings: tuple[dict[str, str], ...]
) -> dict[str, Any]:
    return {
        'metrics': (
            metric('Storage Used', capacity['used_display'], capacity['status'], capacity['tone']),
            metric('Total Capacity', capacity['capacity_display'], capacity['status'], capacity['tone']),
            metric('Headroom', capacity['headroom_display'], capacity['status'], capacity['tone']),
            metric('Local Risks', str(local_risks), 'Review' if local_risks else 'Clear', 'warning' if local_risks else 'normal'),
        ),
        'capacity': capacity,
        'interpretation_title': executive_title(capacity, local_risks),
        'interpretation_body': executive_body(capacity, local_risks, evidence_gap_count),
        'interpretation_note': f'{evidence_gap_count} storage evidence gap(s) remain explicit. Aggregate headroom does not clear localized filesystem, PV, or PVC risk.',
        'findings': findings,
    }


def capacity_section(capacity: Mapping[str, Any]) -> dict[str, Any]:
    return {
        'metrics': (
            metric('Used', capacity['used_display'], capacity['status'], capacity['tone']),
            metric('Capacity', capacity['capacity_display'], capacity['status'], capacity['tone']),
            metric('Available', capacity['available_display'], capacity['status'], capacity['tone']),
            metric('Threshold', '70%', 'Warning Band', 'warning'),
        ),
        'resource': capacity,
        'register': ({
            'ref': 'C1', 'scope': 'Node Filesystems', 'used': capacity['used_display'],
            'capacity': capacity['capacity_display'], 'available': capacity['available_display'],
            'headroom': capacity['headroom_display'], 'status': capacity['status'], 'tone': capacity['tone'],
        },),
        'decision': (
            'No aggregate expansion is indicated by the committed utilization alone. Validate localized filesystem, PVC, PV, and expansion evidence before approving remediation.'
            if capacity['evidence_available']
            else 'Restore matching used, capacity, and available evidence before assigning an aggregate storage status.'
        ),
    }


def filesystem_section(
    *, capacity: Mapping[str, Any], filesystem_summary: Mapping[str, Any], filesystem_records: list[dict[str, Any]], node_count: int
) -> dict[str, Any]:
    return {
        'metrics': (
            metric('Filesystem Records', str(len(filesystem_records)) if filesystem_records else 'Not Available', 'Committed' if filesystem_records else 'Not Available', 'normal' if filesystem_records else 'warning'),
            metric('Nodes in Scope', str(node_count) if node_count else 'Not Available', 'Committed Inventory' if node_count else 'Unknown', 'normal' if node_count else 'muted'),
            metric('Highest Usage', percent(filesystem_summary.get('highest_usage')), risk_label(filesystem_summary.get('risk')), risk_tone(filesystem_summary.get('risk'))),
            metric('Coverage', 'Current' if filesystem_records else 'Partial', 'Query Ready' if filesystem_records else 'Requires Validation', 'normal' if filesystem_records else 'warning'),
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
            f'{len(filesystem_records)} committed filesystem row(s) are available. The highest observed usage is {percent(filesystem_summary.get("highest_usage"))} on {text(filesystem_summary.get("highest_node"), "an unidentified node")}.'
            if filesystem_records
            else 'Collect and commit node filesystem rows using the same reporting boundary. Missing rows must never become 0% used, 100% free, or Normal.'
        ),
    }


def persistent_section(
    *, pv_summary: Mapping[str, Any], pvc_summary: Mapping[str, Any], pv_rows: list[dict[str, Any]], pvc_rows: list[dict[str, Any]]
) -> dict[str, Any]:
    expansion_available = expansion_evidence_available(pv_rows, pvc_rows)
    return {
        'metrics': (
            metric('Persistent Volumes', pv_summary['count_display'], 'Committed Inventory' if pv_summary['count'] else 'Not Available', 'normal' if pv_summary['count'] else 'warning'),
            metric('PVC Utilization', pvc_summary['used_percent_display'], pvc_summary['status'], pvc_summary['tone']),
            metric('Binding Coverage', binding_coverage(pv_rows, pvc_rows), 'Review' if pv_rows or pvc_rows else 'Not Available', 'warning' if pv_rows or pvc_rows else 'muted'),
            metric('Expansion Evidence', 'Available' if expansion_available else 'Not Available', 'Validate' if expansion_available else 'Coverage Gap', 'normal' if expansion_available else 'warning'),
        ),
        'pv': pv_summary,
        'pvc': pvc_summary,
        'pv_donut_svg': count_donut_svg(pv_summary['count'], 'Persistent Volumes'),
        'register': (
            {'ref': 'P1', 'evidence': 'Persistent Volumes', 'value': pv_summary['count_display'], 'boundary': 'Committed Inventory', 'status': 'Current' if pv_summary['count'] else 'Not Available', 'tone': 'normal' if pv_summary['count'] else 'warning'},
            {'ref': 'P2', 'evidence': 'Persistent Volume Claims', 'value': pvc_summary['count_display'], 'boundary': pvc_summary['scope'], 'status': pvc_summary['status'], 'tone': pvc_summary['tone']},
            {'ref': 'P3', 'evidence': 'Claim Filesystem Usage', 'value': pvc_summary['used_percent_display'], 'boundary': 'Observed Volume Capacity', 'status': pvc_summary['status'], 'tone': pvc_summary['tone']},
            {'ref': 'P4', 'evidence': 'Expansion Support', 'value': 'Available' if expansion_available else 'Not Available', 'boundary': 'StorageClass / PVC', 'status': 'Review', 'tone': 'warning'},
        ),
        'pv_rows': pv_records(pv_rows)[:2],
        'pvc_rows': pvc_records(pvc_rows)[:2],
        'decision': 'Use inventory to establish object scope and lifecycle. Do not infer claim free space or expansion readiness from object counts alone.',
    }


def risk_section(*, local_risks: int, actionable_count: int, risk_register: tuple[dict[str, str], ...], expansion_available: bool) -> dict[str, Any]:
    return {
        'metrics': (
            metric('Actionable Findings', str(max(actionable_count, len([item for item in risk_register if item['priority'] in {'P1', 'P2'}]))), 'Storage Review', 'warning'),
            metric('Local Risks', str(local_risks), 'Open' if local_risks else 'Clear', 'warning' if local_risks else 'normal'),
            metric('Expansion Candidates', 'Review' if expansion_available else 'Not Available', 'Validate' if expansion_available else 'Coverage Gap', 'warning'),
            metric('Validation Gates', '5', 'Required', 'info'),
        ),
        'local_risks': local_risks,
        'local_risk_title': f'{local_risks} local filesystem risk item(s) require review.' if local_risks else 'No committed local filesystem risk item is currently classified as Warning or Critical.',
        'local_risk_body': 'Resolve node, filesystem, mount point, owner, current pressure, and operational impact before remediation.' if local_risks else 'Continue monitoring filesystem pressure and preserve complete identity evidence.',
        'expansion_checklist': ('StorageClass allows expansion', 'PVC and PV identities match', 'Filesystem supports online or offline growth', 'Application owner and maintenance window are confirmed', 'Post-change free-capacity target is defined'),
        'register': risk_register,
        'interpretation': 'No expansion, cleanup, migration, or local-volume remediation is authorized by this report alone.',
    }


def trend_section(*, capacity: Mapping[str, Any], trend: Mapping[str, Any]) -> dict[str, Any]:
    return {
        'metrics': (
            metric('Current Utilization', capacity['used_display'], capacity['status'], capacity['tone']),
            metric('Current Headroom', capacity['headroom_display'], capacity['status'], capacity['tone']),
            metric('Historical Series', 'Committed' if trend['historical_available'] else 'Not Available', 'Evidence State', 'normal' if trend['historical_available'] else 'warning'),
            metric('Forecast Evidence', trend['projection_display'], trend['status'], trend['tone']),
        ),
        **trend,
        'register': (
            {'ref': 'T1', 'signal': 'Storage', 'current': capacity['used_display'], 'projection': trend['projection_display'], 'assessment': trend['assessment'], 'tone': trend['tone']},
            {'ref': 'T2', 'signal': 'Evidence', 'current': 'Committed Snapshot' if capacity['evidence_available'] else 'Not Available', 'projection': 'Committed Series' if trend['available'] else 'Not Available', 'assessment': 'Current' if trend['available'] else 'Review', 'tone': 'normal' if trend['available'] else 'warning'},
        ),
        'interpretation': trend_interpretation(capacity, trend),
    }


def recommendations_section(recommendations: tuple[dict[str, str], ...]) -> dict[str, Any]:
    return {
        'metrics': recommendation_metrics(recommendations),
        'items': recommendations,
        'governance': (
            {'field': 'Primary Action', 'requirement': recommendations[0]['title'] if recommendations else 'Maintain committed storage evidence.'},
            {'field': 'Validation Criteria', 'requirement': 'Confirm unit, scope, identity, live metric, owner, maintenance window, and rollback plan.'},
            {'field': 'Assigned Owners', 'requirement': assigned_owners(recommendations)},
            {'field': 'Change Control', 'requirement': 'No storage expansion, cleanup, or migration is authorized by this report alone.'},
        ),
    }


def methodology_section(
    *, payload: Mapping[str, Any], evidence_gap_count: int, node_count: int, namespace_scope: str, period_label: str, data_cutoff: str
) -> dict[str, Any]:
    source_rows = _source_rows(payload)
    return {
        'metrics': (
            metric('Data Sources', str(len(source_rows)), 'Active / Partial', 'warning' if evidence_gap_count else 'normal'),
            metric('Coverage', f'{node_count} Nodes' if node_count else 'Node Scope', namespace_scope, 'normal' if node_count else 'muted'),
            metric('Capacity Basis', 'Used / Total', 'Committed', 'normal'),
            metric('Observation Boundary', 'Snapshot', 'Committed', 'normal'),
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
        'included': ('Committed aggregate filesystem capacity and utilization when available.', 'Committed filesystem, PV, PVC, lifecycle, and risk evidence returned by the collector.', 'Optional committed storage forecast evidence when available.'),
        'excluded': ('Live cluster state after the data cut-off.', 'Unapproved change windows and in-flight maintenance.', 'Filesystem or claim utilization not present in committed evidence.'),
        'limitations': ('Aggregate headroom does not clear localized filesystem or claim risk.', 'Inventory objects do not establish filesystem utilization or expansion support.', 'Validate all recommendations against live cluster state before remediation.'),
        'status_language': (
            {'ref': 'S1', 'title': 'Not Available', 'description': 'No evidence exists for the requested dimension.'},
            {'ref': 'S2', 'title': 'Not Collected', 'description': 'Collection was prevented by configuration, permission, or failure.'},
            {'ref': 'S3', 'title': 'Partial Coverage', 'description': 'Evidence exists but does not cover the full requested scope.'},
            {'ref': 'S4', 'title': 'Source Unavailable', 'description': 'The source was unreachable or not providing data at the cut-off.'},
        ),
    }


def _source_rows(payload: Mapping[str, Any]) -> tuple[dict[str, str], ...]:
    source_rows = rows(payload.get('source_evidence'))
    result = tuple({'source': text(item.get('source')), 'freshness': text(item.get('freshness')), 'last_collected': format_temporal(item.get('last_collected'))} for item in source_rows[:4])
    if result:
        return result
    return (
        {'source': 'Metrics Source Observation Cache', 'freshness': 'Not Available', 'last_collected': 'Not Available'},
        {'source': 'Kubernetes Storage Inventory', 'freshness': 'Committed', 'last_collected': 'At report cut-off'},
        {'source': 'Storage Analysis Evidence', 'freshness': 'Current', 'last_collected': 'At report cut-off'},
        {'source': 'Forecast Evidence', 'freshness': 'Not Available', 'last_collected': 'Not Available'},
    )
