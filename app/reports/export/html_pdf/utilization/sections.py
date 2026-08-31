from __future__ import annotations

from typing import Any

from app.reports.export.html_pdf.normalization import sanitize_text

from .actions import (
    consumer_register,
    cpu_assessment,
    direction_tone,
    distribution_interpretation,
    forecast_confidence,
    forecast_eta,
    leading_interpretation,
    memory_assessment_body,
    memory_assessment_title,
    priority_findings,
    trend_direction,
    trend_interpretation,
    trend_row,
)
from .charts import donut_svg, participation_donut_svg
from .model import UtilizationState, consumer_value, int_value, metric, optional_percent, percent


def forecast_method(state: UtilizationState) -> str:
    return sanitize_text(
        state.forecast_payload.get('method_label') or state.forecast_payload.get('forecast_method'),
        fallback='Not Available',
    )


def build_cover(state: UtilizationState, *, cluster_scope: str) -> dict[str, str]:
    return {
        'cluster': sanitize_text(state.cluster.get('name'), fallback=cluster_scope),
        'environment': sanitize_text(state.cluster.get('environment'), fallback='Not Available'),
        'purpose': (
            'Support operational review of shared-resource use, saturation direction, '
            'concentration, and accountable utilization actions.'
        ),
        'context': (
            'Use the report cut-off as the evidence boundary. Confirm live state, workload ownership, '
            'and approved change controls before remediation.'
        ),
    }


def build_executive(
    state: UtilizationState,
    *,
    source_rows: list[dict[str, str]],
) -> dict[str, Any]:
    leading = max((state.cpu, state.memory, state.pods), key=lambda item: item['percent'])
    return {
        'metrics': (
            metric('CPU P95', state.cpu['value'], state.cpu['status'], state.cpu['tone']),
            metric('Memory P95', state.memory['value'], state.memory['status'], state.memory['tone']),
            metric('Pod Utilization', state.pods['value'], state.pods['status'], state.pods['tone']),
            metric(
                'Coverage',
                percent(state.node_participation),
                'Current' if state.total_nodes else 'Not Available',
                'normal' if state.total_nodes and not state.not_ready_nodes else 'warning',
            ),
        ),
        'resources': (
            {**state.cpu, 'label': 'CPU'},
            {**state.memory, 'label': 'Memory'},
            {**state.pods, 'label': 'Pods'},
            {
                'label': 'Nodes',
                'percent': state.node_participation,
                'value': f'{state.ready_nodes} / {state.total_nodes}' if state.total_nodes else 'Not Available',
                'status': 'Current' if state.total_nodes and not state.not_ready_nodes else 'Review',
                'tone': 'normal' if state.total_nodes and not state.not_ready_nodes else 'warning',
            },
        ),
        'leading_title': f'{leading["label"]} is the leading shared-resource signal.',
        'leading_body': leading_interpretation(leading),
        'leading_note': (
            'CPU and pod utilization remain within normal operating bands. '
            f'{state.ready_nodes} of {state.total_nodes} nodes are ready at the committed cut-off.'
            if state.total_nodes
            else 'Node participation evidence was not available at the committed cut-off.'
        ),
        'findings': priority_findings(state, source_rows),
    }


def build_cpu(state: UtilizationState, *, chart_svg: str) -> dict[str, Any]:
    return {
        'metrics': (
            metric('Current Signal', state.cpu['value'], state.cpu['status'], state.cpu['tone']),
            metric('P95', state.cpu['value'], state.cpu['status'], state.cpu['tone']),
            metric('Headroom', percent(state.cpu['headroom']), 'Available', 'normal'),
            metric(
                'Highest Displayed',
                consumer_value(state.cpu_consumers, 0),
                'cores',
                'warning' if state.cpu_consumers else 'muted',
            ),
        ),
        'chart_svg': chart_svg,
        'chart_available': bool(state.cpu_history),
        'consumers': state.cpu_consumers[:3],
        'assessment_title': (
            'CPU pressure is not currently a capacity constraint.'
            if state.cpu['percent'] < 70
            else 'CPU utilization requires operational review.'
        ),
        'assessment_body': cpu_assessment(state),
        'assessment_note': (
            'Low aggregate utilization can coexist with short-lived workload spikes; '
            'live-state validation remains required.'
        ),
        'decision': (
            'Validate whether the highest displayed CPU consumers are expected for the selected '
            'reporting boundary. Do not infer aggregate expansion need from a single consumer record.'
        ),
    }


def build_memory(state: UtilizationState, *, chart_svg: str) -> dict[str, Any]:
    return {
        'metrics': (
            metric('Current Signal', state.memory['value'], state.memory['status'], state.memory['tone']),
            metric('P95', state.memory['value'], state.memory['status'], state.memory['tone']),
            metric(
                'Headroom',
                percent(state.memory['headroom']),
                'Available',
                'normal' if state.memory['headroom'] > 15 else 'warning',
            ),
            metric(
                'Projection',
                optional_percent(state.memory_projection),
                forecast_eta(state),
                'warning' if state.memory_projection is not None and state.memory_projection >= 70 else 'info',
            ),
        ),
        'chart_svg': chart_svg,
        'chart_available': bool(state.memory_history),
        'projection_available': state.memory_projection is not None,
        'consumers': state.memory_consumers[:3],
        'assessment_title': memory_assessment_title(state),
        'assessment_body': memory_assessment_body(state),
        'assessment_note': (
            'Projection supports planning, not autonomous remediation. Approved deployments and '
            'infrastructure changes remain outside the model.'
        ),
        'decision': (
            'Confirm whether the displayed memory concentration is expected and include any forecast '
            'threshold exposure in the next capacity planning gate.'
        ),
    }


def build_pod_node(state: UtilizationState) -> dict[str, Any]:
    pod_capacity = int_value(state.summary.get('pod_capacity'))
    pod_count = int_value(state.summary.get('pod_count'))
    return {
        'metrics': (
            metric('Pod Utilization', state.pods['value'], state.pods['status'], state.pods['tone']),
            metric('Pod Headroom', percent(state.pods['headroom']), 'Available', 'normal'),
            metric(
                'Ready Nodes',
                f'{state.ready_nodes} / {state.total_nodes}' if state.total_nodes else 'Not Available',
                'Current' if not state.not_ready_nodes else 'Review',
                'normal' if state.total_nodes and not state.not_ready_nodes else 'warning',
            ),
            metric(
                'Not Ready',
                str(state.not_ready_nodes),
                'Clear' if not state.not_ready_nodes else 'Review',
                'normal' if not state.not_ready_nodes else 'critical',
            ),
        ),
        'pods_used': state.pods['percent'],
        'pods_headroom': state.pods['headroom'],
        'pod_capacity': pod_capacity,
        'pod_count': pod_count,
        'ready_nodes': state.ready_nodes,
        'not_ready_nodes': state.not_ready_nodes,
        'total_nodes': state.total_nodes,
        'participation': state.node_participation,
        'node_donut_svg': participation_donut_svg(state.node_participation, state.ready_nodes),
        'register': (
            {
                'ref': 'P1',
                'resource': 'Pods',
                'used': state.pods['value'],
                'capacity': f'{pod_capacity} Total'
                if state.summary.get('pod_capacity') is not None
                else 'Not Available',
                'headroom': (
                    f'{max(pod_capacity - pod_count, 0)} Remaining'
                    if state.summary.get('pod_capacity') is not None
                    else 'Not Available'
                ),
                'status': state.pods['status'],
                'tone': state.pods['tone'],
            },
            {
                'ref': 'N1',
                'resource': 'Nodes',
                'used': f'{state.ready_nodes} Ready' if state.total_nodes else 'Not Available',
                'capacity': f'{state.total_nodes} Total' if state.total_nodes else 'Not Available',
                'headroom': f'{state.not_ready_nodes} Not Ready' if state.total_nodes else 'Not Available',
                'status': 'Current' if state.total_nodes and not state.not_ready_nodes else 'Review',
                'tone': 'normal' if state.total_nodes and not state.not_ready_nodes else 'warning',
            },
        ),
        'interpretation': (
            f'Pod utilization is {percent(state.pods["percent"])}, leaving '
            f'{percent(state.pods["headroom"])} schedulable headroom. '
            f'{state.ready_nodes} of {state.total_nodes} committed nodes are ready.'
            if state.total_nodes
            else 'Pod utilization is available, but node participation evidence was not returned.'
        ),
    }


def build_distribution(state: UtilizationState) -> dict[str, Any]:
    return {
        'memory_total': sum(item['raw_value'] for item in state.memory_consumers[:3]),
        'memory_donut_svg': donut_svg(state.memory_consumers[:3]),
        'memory_consumers': state.memory_consumers[:3],
        'cpu_consumers': state.cpu_consumers[:3],
        'register': consumer_register(state),
        'interpretation': distribution_interpretation(state),
    }


def build_trend(state: UtilizationState, *, chart_svg: str) -> dict[str, Any]:
    confidence = forecast_confidence(state)
    return {
        'metrics': (
            metric(
                'CPU Direction',
                trend_direction(state.cpu_history),
                state.cpu['value'],
                direction_tone(state.cpu_history),
            ),
            metric(
                'Memory Direction',
                trend_direction(state.memory_history),
                state.memory['value'],
                direction_tone(state.memory_history),
            ),
            metric(
                'Pod Direction',
                trend_direction(state.pod_history),
                state.pods['value'],
                direction_tone(state.pod_history),
            ),
            metric(
                'Forecast Confidence',
                confidence,
                'Committed' if state.forecast_items else 'Not Available',
                'normal' if state.forecast_items else 'muted',
            ),
        ),
        'chart_svg': chart_svg,
        'chart_available': any((state.cpu_history, state.memory_history, state.pod_history)),
        'rows': (
            trend_row('T1', 'CPU', state.cpu['percent'], state.cpu_projection, state.cpu_history),
            trend_row('T2', 'Memory', state.memory['percent'], state.memory_projection, state.memory_history),
            trend_row('T3', 'Pods', state.pods['percent'], state.pod_projection, state.pod_history),
        ),
        'interpretation': trend_interpretation(state),
        'evidence': (
            'Forecast values use committed historical observations. Planned deployments, approved '
            'infrastructure expansion, workload migrations, and live state after the report cut-off '
            'are not modeled.'
            if state.forecast_items
            else 'Historical utilization remains visible, but forecast evidence was not available for this report run.'
        ),
    }


def build_methodology(
    state: UtilizationState,
    *,
    source_rows: list[dict[str, str]],
    namespace_scope: str,
    period_label: str,
    data_cutoff: str,
) -> dict[str, Any]:
    method = forecast_method(state)
    return {
        'metrics': (
            metric(
                'Data Sources',
                str(len(source_rows)),
                'Active' if source_rows else 'Not Available',
                'normal' if source_rows else 'muted',
            ),
            metric(
                'Coverage',
                f'{state.total_nodes} Nodes' if state.total_nodes else 'Not Available',
                namespace_scope,
                'normal' if state.total_nodes else 'muted',
            ),
            metric(
                'Forecast Method',
                method,
                'Committed' if state.forecast_items else 'Optional Evidence',
                'info' if state.forecast_items else 'muted',
            ),
            metric('Observation Boundary', 'Snapshot', 'Committed', 'normal'),
        ),
        'sources': source_rows,
        'rules': (
            {'ref': 'M1', 'rule': 'Reporting Period', 'setting': period_label},
            {'ref': 'M2', 'rule': 'Data Cut-Off', 'setting': data_cutoff},
            {'ref': 'M3', 'rule': 'Threshold Bands', 'setting': '70% / 85%'},
            {'ref': 'M4', 'rule': 'Forecast Method', 'setting': method},
            {'ref': 'M5', 'rule': 'Utilization Basis', 'setting': 'P95 + committed state'},
        ),
        'references': (
            {
                'ref': 'M3',
                'title': 'Threshold Bands',
                'description': 'Normal below 70%, warning from 70% to 84.9%, and critical at 85% or above.',
            },
            {
                'ref': 'M4',
                'title': 'Forecast Method',
                'description': (
                    f'{method} is used where committed historical evidence is available.'
                    if state.forecast_items
                    else 'Forecast evidence was not available; current utilization remains reportable.'
                ),
            },
            {
                'ref': 'M5',
                'title': 'Utilization Basis',
                'description': 'Shared-resource posture uses committed summary metrics and P95 where the dataset provides it.',
            },
        ),
        'included': (
            'Committed cluster-scoped utilization observations.',
            'Committed CPU, memory, pod, and node participation evidence.',
            'Top-consumer and forecast evidence when available.',
        ),
        'excluded': (
            'Live cluster state after the data cut-off.',
            'Unapproved change windows and in-flight maintenance.',
            'Planned deployments not represented by committed evidence.',
        ),
        'limitations': (
            'Distribution charts describe displayed top-consumer records unless a complete denominator is available.',
            'Unavailable observations remain explicit and are not interpreted as zero.',
            'Validate all recommendations against live cluster state before remediation.',
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
