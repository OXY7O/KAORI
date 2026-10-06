from __future__ import annotations

from typing import Any

from app.reports.export.html_pdf.normalization import sanitize_text

from .actions import (
    CapacityActionState,
    compute_register_row,
    executive_interpretation,
    owner_summary,
    risk_interpretation,
)
from .forecast import CapacityForecastState, projection_status, projection_tone
from .model import CapacityState, metric, optional_percent, risk_metric


def build_cover_section(state: CapacityState, cluster_scope: str) -> dict[str, Any]:
    return {
        'cluster': sanitize_text(state.cluster.get('name'), fallback=cluster_scope),
        'environment': sanitize_text(state.cluster.get('environment'), fallback='Not Available'),
        'purpose': (
            'Support management and platform review of shared-capacity posture, committed '
            'headroom, evidence gaps, projected pressure, and validation gates.'
        ),
        'context': (
            'Use the report cut-off as the evidence boundary. Missing capacity evidence remains '
            'explicit and is never converted to zero or a healthy posture.'
        ),
    }


def build_executive_section(
    state: CapacityState,
    forecast: CapacityForecastState,
    actions: CapacityActionState,
) -> dict[str, Any]:
    cpu = state.resources['cpu']
    memory = state.resources['memory']
    pods = state.resources['pods']
    storage = state.resources['storage']
    available_resources = [item for item in state.resources.values() if item['evidence_available']]
    leading = max(available_resources, key=lambda item: item['used_percent'], default=None)
    return {
        'metrics': (
            metric('CPU Headroom', cpu['headroom_display'], cpu['status'], cpu['tone']),
            metric('Memory Headroom', memory['headroom_display'], memory['status'], memory['tone']),
            metric('Pod Headroom', pods['headroom_display'], pods['status'], pods['tone']),
            metric('Storage Evidence', storage['headroom_display'], storage['status'], storage['tone']),
        ),
        'resources': (
            {**cpu, 'label': 'CPU'},
            {**memory, 'label': 'Memory'},
            {**pods, 'label': 'Pods'},
            {
                'key': 'nodes',
                'label': 'Nodes',
                'evidence_available': state.total_nodes > 0,
                'used_percent': state.participation,
                'used_display': f'{state.ready_nodes} / {state.total_nodes}' if state.total_nodes else 'Not Available',
                'headroom_display': f'{state.not_ready_nodes} Not Ready' if state.total_nodes else 'Not Available',
                'status': 'Current' if state.total_nodes and not state.not_ready_nodes else 'Review',
                'tone': 'normal' if state.total_nodes and not state.not_ready_nodes else 'warning',
            },
        ),
        'interpretation_title': (
            f'{leading["label"]} is the leading committed capacity signal.'
            if leading
            else 'Capacity posture requires committed evidence.'
        ),
        'interpretation_body': executive_interpretation(leading, actions.evidence_gap_count),
        'interpretation_note': (
            f'{state.ready_nodes} of {state.total_nodes} nodes are ready at the committed cut-off. '
            f'{actions.evidence_gap_count} capacity evidence gap(s) remain explicit.'
            if state.total_nodes
            else f'{actions.evidence_gap_count} capacity evidence gap(s) remain explicit.'
        ),
        'findings': actions.executive_findings,
    }


def build_compute_section(
    state: CapacityState,
    forecast: CapacityForecastState,
) -> dict[str, Any]:
    cpu = state.resources['cpu']
    memory = state.resources['memory']
    return {
        'metrics': (
            metric('CPU Used', cpu['used_display'], cpu['status'], cpu['tone']),
            metric('CPU Headroom', cpu['headroom_display'], cpu['status'], cpu['tone']),
            metric('Memory Used', memory['used_display'], memory['status'], memory['tone']),
            metric('Memory Headroom', memory['headroom_display'], memory['status'], memory['tone']),
        ),
        'cpu': {**cpu, 'allocation': state.allocations['cpu']},
        'memory': {**memory, 'allocation': state.allocations['memory']},
        'register': (
            compute_register_row('C1', cpu, forecast.projections['cpu']),
            compute_register_row('C2', memory, forecast.projections['memory']),
        ),
        'decision': (
            'Do not infer aggregate expansion need from a single workload or allocation record. '
            'Validate sustained utilization, committed requests and limits, headroom, and the '
            'approved growth plan before changing worker capacity.'
        ),
    }


def build_scheduling_section(state: CapacityState, donut_svg: str) -> dict[str, Any]:
    pods = state.resources['pods']
    nodes_current = state.total_nodes and not state.not_ready_nodes
    return {
        'metrics': (
            metric('Pod Utilization', pods['used_display'], pods['status'], pods['tone']),
            metric('Pod Headroom', pods['headroom_display'], pods['status'], pods['tone']),
            metric(
                'Ready Nodes',
                f'{state.ready_nodes} / {state.total_nodes}' if state.total_nodes else 'Not Available',
                'Current' if nodes_current else 'Review',
                'normal' if nodes_current else 'warning',
            ),
            metric(
                'Not Ready',
                str(state.not_ready_nodes) if state.total_nodes else 'Not Available',
                'Clear' if nodes_current else 'Review',
                'normal' if nodes_current else 'warning',
            ),
        ),
        'pods': {**pods, 'allocation': state.allocations['pods']},
        'nodes': {
            'total': state.total_nodes,
            'ready': state.ready_nodes,
            'not_ready': state.not_ready_nodes,
            'workers': state.worker_nodes,
            'control_plane': state.master_nodes,
            'participation': state.participation,
            'donut_svg': donut_svg,
        },
        'register': (
            {
                'ref': 'P1',
                'resource': 'Pods',
                'used_state': pods['used_display'],
                'capacity': pods['capacity_display'],
                'headroom': pods['available_display'],
                'status': pods['status'],
                'tone': pods['tone'],
            },
            {
                'ref': 'N1',
                'resource': 'Nodes',
                'used_state': f'{state.ready_nodes} Ready' if state.total_nodes else 'Not Available',
                'capacity': f'{state.total_nodes} Total' if state.total_nodes else 'Not Available',
                'headroom': f'{state.not_ready_nodes} Not Ready' if state.total_nodes else 'Not Available',
                'status': 'Current' if nodes_current else 'Review',
                'tone': 'normal' if nodes_current else 'warning',
            },
        ),
        'interpretation': (
            f'Pod utilization is {pods["used_display"]}, leaving {pods["headroom_display"]} '
            f'reported schedulable headroom. {state.ready_nodes} of {state.total_nodes} committed nodes are ready.'
            if pods['evidence_available'] and state.total_nodes
            else 'Scheduling conclusions remain limited to the committed evidence available at the cut-off.'
        ),
    }


def build_storage_section(state: CapacityState) -> dict[str, Any]:
    storage = state.resources['storage']
    available = storage['evidence_available']
    return {
        'metrics': (
            metric('Storage Used', storage['used_value_display'], storage['status'], storage['tone']),
            metric('Storage Capacity', storage['capacity_value_display'], storage['status'], storage['tone']),
            metric('Storage Headroom', storage['headroom_display'], storage['status'], storage['tone']),
            metric('Evidence Status', 'Ready' if available else 'Gap', storage['status'], storage['tone']),
        ),
        'resource': storage,
        'requirements': (
            {
                'ref': 'S1',
                'evidence': 'Used Capacity',
                'definition': 'Committed storage use in bytes or GiB',
                'status': 'Current' if available else 'Missing',
                'action': 'Monitor' if available else 'Required',
            },
            {
                'ref': 'S2',
                'evidence': 'Total Capacity',
                'definition': 'Committed allocatable storage capacity',
                'status': 'Current' if available else 'Missing',
                'action': 'Monitor' if available else 'Required',
            },
            {
                'ref': 'S3',
                'evidence': 'Headroom',
                'definition': 'Derived from matching scope and units',
                'status': 'Current' if available else 'Missing',
                'action': 'Monitor' if available else 'Required',
            },
            {
                'ref': 'S4',
                'evidence': 'Risk Evidence',
                'definition': 'PVC, PV, filesystem, and local-volume posture',
                'status': 'Partial' if available else 'Missing',
                'action': 'Validate' if available else 'Required',
            },
        ),
        'decision': (
            'Validate committed storage units, scope, and collection time before assigning a storage capacity status.'
            if available
            else 'Collect and commit storage used, total capacity, headroom, and risk evidence for the same reporting boundary before assigning a storage capacity status.'
        ),
    }


def build_forecast_section(
    forecast: CapacityForecastState,
    chart_svg: str,
) -> dict[str, Any]:
    return {
        'metrics': (
            metric(
                'CPU Projection',
                optional_percent(forecast.projections['cpu']),
                projection_status(forecast.projections['cpu']),
                projection_tone(forecast.projections['cpu']),
            ),
            metric(
                'Memory Projection',
                optional_percent(forecast.projections['memory']),
                projection_status(forecast.projections['memory']),
                projection_tone(forecast.projections['memory']),
            ),
            metric(
                'Pod Projection',
                optional_percent(forecast.projections['pods']),
                projection_status(forecast.projections['pods']),
                projection_tone(forecast.projections['pods']),
            ),
            metric('Warning Threshold', '70%', 'Operating Band', 'warning'),
        ),
        'chart_svg': chart_svg,
        'available': forecast.available,
        'rows': forecast.rows,
        'method': forecast.method,
        'interpretation': forecast.interpretation,
    }


def build_risk_section(state: CapacityState, actions: CapacityActionState) -> dict[str, Any]:
    return {
        'metrics': (
            risk_metric('Critical Risks', sum(1 for row in actions.risks if row['tone'] == 'critical'), 'critical'),
            risk_metric('Review Risks', sum(1 for row in actions.risks if row['tone'] == 'warning'), 'warning'),
            metric(
                'Evidence Gaps',
                str(actions.evidence_gap_count),
                'Requires Review' if actions.evidence_gap_count else 'Clear',
                'warning' if actions.evidence_gap_count else 'normal',
            ),
            metric('Validation Gates', str(len(actions.recommendations)), 'Required', 'info'),
        ),
        'rows': actions.risks,
        'interpretation': risk_interpretation(state.resources, actions.risks),
    }


def build_recommendation_section(actions: CapacityActionState) -> dict[str, Any]:
    recommendations = actions.recommendations
    return {
        'metrics': (
            metric(
                'P1 Actions',
                str(actions.p1_count),
                'Open' if actions.p1_count else 'None',
                'critical' if actions.p1_count else 'normal',
            ),
            metric(
                'P2 Actions',
                str(actions.p2_count),
                'Open' if actions.p2_count else 'None',
                'warning' if actions.p2_count else 'normal',
            ),
            metric(
                'P3 Actions',
                str(actions.p3_count),
                'Planned' if actions.p3_count else 'None',
                'info' if actions.p3_count else 'normal',
            ),
            metric('Validation Gates', str(len(recommendations)), 'Required', 'info'),
        ),
        'rows': recommendations,
        'governance': (
            {
                'field': 'Primary Action',
                'requirement': recommendations[0]['title'] if recommendations else 'Continue capacity monitoring.',
            },
            {
                'field': 'Validation Criteria',
                'requirement': 'Confirm unit, scope, cut-off, live metric, owner, and approved response before closure.',
            },
            {'field': 'Assigned Owners', 'requirement': owner_summary(recommendations)},
            {
                'field': 'Change Control',
                'requirement': 'No infrastructure or workload change is authorized by this report alone.',
            },
        ),
    }


def build_methodology_section(
    state: CapacityState,
    forecast: CapacityForecastState,
    actions: CapacityActionState,
    namespace_scope: str,
    period_label: str,
    data_cutoff: str,
) -> dict[str, Any]:
    return {
        'metrics': (
            metric(
                'Data Sources',
                str(len(actions.source_rows)),
                'Active' if actions.source_rows else 'Not Available',
                'normal' if actions.source_rows else 'muted',
            ),
            metric(
                'Coverage',
                f'{state.total_nodes} Nodes' if state.total_nodes else 'Not Available',
                namespace_scope,
                'normal' if state.total_nodes else 'muted',
            ),
            metric(
                'Forecast Method',
                forecast.method,
                'Committed' if forecast.available else 'Optional Evidence',
                'info' if forecast.available else 'muted',
            ),
            metric('Observation Boundary', 'Snapshot', 'Committed', 'normal'),
        ),
        'sources': actions.source_rows,
        'rules': (
            {'ref': 'M1', 'rule': 'Reporting Period', 'setting': period_label},
            {'ref': 'M2', 'rule': 'Data Cut-Off', 'setting': data_cutoff},
            {'ref': 'M3', 'rule': 'Headroom Bands', 'setting': 'Healthy >= 40%'},
            {'ref': 'M4', 'rule': 'Forecast Method', 'setting': forecast.method},
            {'ref': 'M5', 'rule': 'Missing Evidence', 'setting': 'Explicit Not Available'},
        ),
        'references': (
            {
                'ref': 'M3',
                'title': 'Headroom Bands',
                'description': 'Healthy at 40% or more, Watch below 40%, and Critical below 15% remaining headroom.',
            },
            {
                'ref': 'M4',
                'title': 'Forecast Method',
                'description': (
                    f'{forecast.method} is used where committed historical evidence is available.'
                    if forecast.available
                    else 'Forecast evidence was not available; current capacity remains reportable.'
                ),
            },
            {
                'ref': 'M5',
                'title': 'Missing Evidence',
                'description': 'Unavailable capacity evidence remains explicit and is never converted to zero.',
            },
        ),
        'included': (
            'Committed CPU, memory, pod, node, and available storage capacity evidence.',
            'Committed allocation and headroom evidence.',
            'Committed forecast endpoints when available.',
        ),
        'excluded': (
            'Live cluster state after the data cut-off.',
            'Unapproved change windows and in-flight maintenance.',
            'Unavailable capacity values not present in committed evidence.',
        ),
        'limitations': (
            'Capacity conclusions depend on matching units, scope, and cut-off.',
            'Forecast results exclude planned deployments and infrastructure expansion.',
            'Validate recommendations against live cluster state before remediation.',
        ),
        'status_language': (
            {'ref': 'S1', 'title': 'Not Available', 'description': 'No evidence exists for the requested dimension.'},
            {
                'ref': 'S2',
                'title': 'Not Collected',
                'description': 'Collection was prevented by configuration or failure.',
            },
            {
                'ref': 'S3',
                'title': 'Partial Coverage',
                'description': 'Evidence exists but does not cover the full requested scope.',
            },
            {
                'ref': 'S4',
                'title': 'Source Unavailable',
                'description': 'The source was unreachable or not providing data at the cut-off.',
            },
        ),
    }
