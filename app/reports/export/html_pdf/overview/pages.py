from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .actions import evidence_summary, management_summary, overall_assessment, primary_concern
from .alerts import (
    alert_category_mix,
    alert_intelligence_summary,
    alert_metrics,
    alert_next_steps,
    alert_severity_svg,
)
from .common import sequence, text, tone
from .consumers import consumer_insight, consumer_mix, consumer_rows, normalize_consumer_bars, observation_scope
from .context import OverviewContext
from .forecast import forecast_headline, forecast_interpretation, forecast_rows, forecast_svg
from .resources import (
    capacity_forecast_rows,
    capacity_interpretation,
    capacity_pressure_rows,
    capacity_rows,
    executive_metric,
    headroom_distribution,
    resource_interpretation,
    resource_posture_card,
    storage_headroom_metric,
)
from .state import OverviewState


def cover_page(context: OverviewContext, state: OverviewState) -> dict[str, Any]:
    return {
        'overall_posture': context.overall_posture,
        'overall_tone': tone(context.overall_tone),
        'assessment': overall_assessment(state.health_summary, state.priority_findings),
        'primary_concern': primary_concern(state.priority_findings),
        'coverage': (
            ('Capacity posture', 'CPU, memory, storage, pods, and node headroom'),
            ('Trend and forecast', 'Historical direction and threshold projection'),
            ('Risks and anomalies', 'Ranked operational findings and affected scope'),
            ('Top consumers', 'Highest namespace, workload, and pod contributors'),
            ('Recommendation plan', 'Evidence-backed actions and validation gates'),
        ),
    }


def executive_page(state: OverviewState) -> dict[str, Any]:
    return {
        'metrics': state.executive_metrics,
        'summary': overall_assessment(state.health_summary, state.priority_findings),
        'management_summary': management_summary(
            resource_metrics=state.resource_metrics,
            storage_snapshot=state.storage_snapshot,
            inventory=state.inventory,
            alerts_snapshot=state.alerts_snapshot,
            forecast_snapshot=state.forecast_snapshot,
            priority_findings=state.priority_findings,
        ),
        'findings': state.priority_findings[:3],
        'decisions': state.decisions[:3],
        'evidence': evidence_summary(state.source_rows),
        'snapshot_status': text(state.snapshot_summary.get('status'), 'Unavailable'),
        'snapshot_tone': tone(state.snapshot_summary.get('tone')),
    }


def resource_posture_page(state: OverviewState) -> dict[str, Any]:
    return {
        'cpu': resource_posture_card(state.resource_metrics, 'cpu'),
        'memory': resource_posture_card(state.resource_metrics, 'memory'),
        'shared_rows': [
            resource_posture_card(state.resource_metrics, key)
            for key in ('cpu', 'memory', 'storage', 'pods')
        ],
        'capacity_rows': capacity_rows(
            resource_metrics=state.resource_metrics,
            capacity_snapshot=state.capacity_snapshot,
            storage_snapshot=state.storage_snapshot,
            inventory=state.inventory,
        ),
        'interpretation': resource_interpretation(
            state.resource_metrics,
            state.storage_snapshot,
            state.inventory,
        ),
        'thresholds': (
            {'label': 'Normal', 'condition': 'Below 70%', 'tone': 'normal'},
            {'label': 'Warning', 'condition': '70% - 84.9%', 'tone': 'warning'},
            {'label': 'Critical', 'condition': '85% or above', 'tone': 'critical'},
            {'label': 'Evaluation', 'condition': 'P95 and local headroom', 'tone': 'info'},
        ),
    }


def trend_forecast_page(state: OverviewState) -> dict[str, Any]:
    return {
        'headline': forecast_headline(state.forecast_snapshot),
        'summary': text(
            state.forecast_snapshot.get('risk_note'),
            'Forecast evidence is not available for the selected reporting window.',
        ),
        'chart_svg': forecast_svg(state.forecast_series),
        'resource_rows': forecast_rows(
            state.resource_metrics,
            state.forecast_snapshot,
            state.forecast_series,
        ),
        'interpretation': forecast_interpretation(state.forecast_snapshot),
        'limitation': (
            'Forecast values use committed historical observations. Planned deployments, '
            'approved infrastructure expansion, and live state after the report cut-off are not modeled.'
        ),
    }


def top_consumers_page(context: OverviewContext, state: OverviewState) -> dict[str, Any]:
    groups = _consumer_groups(state.top_consumers)
    for group in groups.values():
        normalize_consumer_bars(group)
    has_memory = bool(groups['memory'])
    return {
        'primary': groups['memory'] or groups['cpu'],
        'secondary': groups['cpu'] if has_memory else groups['storage'],
        'primary_label': 'By Namespace / Resource (Memory)' if has_memory else 'By Namespace / Resource (CPU)',
        'secondary_label': 'By Namespace / Resource (CPU)' if has_memory else 'By Namespace / Resource (Storage)',
        'mix': consumer_mix(groups['memory'] or groups['cpu']),
        'resource_view': tuple(state.executive_metrics[:3]),
        'observation_scope': observation_scope(state.source_rows, context.period_label),
        'insight': consumer_insight(groups),
    }


def _consumer_groups(top_consumers: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    return {
        'memory': consumer_rows(sequence(top_consumers.get('memory')), 'Memory'),
        'cpu': consumer_rows(sequence(top_consumers.get('cpu')), 'CPU'),
        'storage': consumer_rows(sequence(top_consumers.get('storage')), 'Storage'),
        'pods': consumer_rows(sequence(top_consumers.get('pods')), 'Pods'),
    }


def capacity_pressure_page(state: OverviewState) -> dict[str, Any]:
    return {
        'metrics': (
            executive_metric(state.resource_metrics, 'cpu', 'CPU P95'),
            executive_metric(state.resource_metrics, 'memory', 'Memory P95'),
            storage_headroom_metric(state.storage_snapshot),
            _active_risk_metric(state),
        ),
        'rows': capacity_pressure_rows(
            state.resource_metrics,
            state.capacity_snapshot,
            state.storage_snapshot,
            state.inventory,
        ),
        'risk_highlights': state.priority_findings[:3],
        'distribution': headroom_distribution(state.inventory),
        'forecast': capacity_forecast_rows(
            state.resource_metrics,
            state.forecast_snapshot,
            state.forecast_series,
        ),
        'interpretation': capacity_interpretation(state.resource_metrics, state.inventory),
        'actions': state.decisions[:3],
    }


def _active_risk_metric(state: OverviewState) -> dict[str, Any]:
    count = len(state.recommendation_items)
    return {
        'label': 'Active Risks',
        'value': str(count),
        'status': 'Elevated' if count else 'Normal',
        'tone': 'critical' if count >= 5 else 'warning' if count else 'normal',
        'note': 'Prioritized analytics recommendations.',
    }


def alerts_page(state: OverviewState) -> dict[str, Any]:
    return {
        'metrics': alert_metrics(state.alerts_snapshot, state.alert_detail),
        'severity_svg': alert_severity_svg(state.alerts_snapshot, state.alert_detail),
        'category_mix': alert_category_mix(state.alert_items),
        'alerts': state.alert_items[:5],
        'anomalies': state.anomaly_items[:4],
        'summary': alert_intelligence_summary(state.alerts_snapshot, state.alert_items),
        'next_steps': alert_next_steps(state.recommendation_items, state.alert_items),
    }
