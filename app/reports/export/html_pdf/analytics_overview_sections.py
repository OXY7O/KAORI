from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.reports.export.html_pdf.normalization import sanitize_text


def _text(value: Any, fallback: str = 'Not Available') -> str:
    return sanitize_text(value, fallback=fallback)


def _number(value: Any, default: float = 0.0) -> float:
    if isinstance(value, str):
        value = value.replace('%', '').replace(',', '').strip()
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _integer(value: Any, default: int = 0) -> int:
    return int(round(_number(value, float(default))))


def recommendation_page(recommendations: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    items = list(recommendations[:8])
    if not items:
        items = [
            {
                'rank': 1,
                'priority': 'P3',
                'priority_label': 'Info',
                'tone': 'info',
                'title': 'Maintain current operational posture',
                'register_title': 'Maintain Current Posture',
                'description': 'No actionable recommendation was returned for the current reporting boundary.',
                'recommended_action': 'Continue monitoring committed evidence and validate the next reporting cut-off.',
                'scope': 'Selected reporting scope',
                'source': 'Analytics Overview',
                'owner': 'Platform Operations',
                'target': 'Policy Managed',
                'status': 'Planned',
                'evidence': 'No critical or warning recommendation was produced.',
                'validation': 'Confirm the next committed snapshot remains within configured thresholds.',
            }
        ]
    primary = items[0]
    owner_counts: dict[str, int] = {}
    for item in items:
        owner = _text(item.get('owner'))
        owner_counts[owner] = owner_counts.get(owner, 0) + 1
    return {
        'metrics': [
            {
                'label': 'P1 Actions',
                'value': str(sum(1 for item in items if item.get('priority') == 'P1')),
                'tone': 'critical',
            },
            {
                'label': 'P2 Actions',
                'value': str(sum(1 for item in items if item.get('priority') == 'P2')),
                'tone': 'warning',
            },
            {
                'label': 'Owner Assignment Pending',
                'value': str(sum(1 for item in items if 'required' in _text(item.get('owner')).lower())),
                'tone': 'info',
            },
            {'label': 'Validation Gates', 'value': str(len(items)), 'tone': 'normal'},
        ],
        'items': items,
        'primary': primary,
        'owners': [
            {'owner': owner, 'count': count, 'target': _owner_target(items, owner)}
            for owner, count in owner_counts.items()
        ],
        'guidance': (
            'Remediation must be validated against live state, ownership, maintenance windows, '
            'and approved change controls before implementation.'
        ),
    }


def _owner_target(items: Sequence[Mapping[str, Any]], owner: str) -> str:
    targets = [_text(item.get('target')) for item in items if _text(item.get('owner')) == owner]
    return targets[0] if targets else 'Policy Managed'


def methodology_page(
    *,
    source_rows: Sequence[Mapping[str, Any]],
    inventory: Mapping[str, Any],
    period_label: str,
    data_cutoff: str,
    forecast_snapshot: Mapping[str, Any],
    snapshot_summary: Mapping[str, Any],
) -> dict[str, Any]:
    totals = inventory.get('totals') if isinstance(inventory.get('totals'), Mapping) else {}
    coverage = f'{_integer(totals.get("nodes"))} Nodes / {_integer(totals.get("namespaces"))} Namespaces'
    return {
        'metrics': [
            {'label': 'Data Sources', 'value': str(len(source_rows)), 'tone': 'info'},
            {'label': 'Coverage', 'value': coverage, 'tone': 'info'},
            {
                'label': 'Forecast Window',
                'value': _text(forecast_snapshot.get('forecast_horizon'), 'Not Available'),
                'tone': 'info',
            },
            {'label': 'Observation Boundary', 'value': 'Committed Snapshot', 'tone': 'info'},
        ],
        'sources': list(source_rows),
        'methodology': [
            {'label': 'Reporting Period', 'value': period_label},
            {'label': 'Data Cut-Off', 'value': data_cutoff},
            {
                'label': 'Forecast Method',
                'value': 'Holt-Winters exponential smoothing where committed forecast evidence is available.',
            },
            {
                'label': 'Severity Interpretation',
                'value': 'Derived from thresholds, impact scope, and operational urgency.',
            },
            {
                'label': 'Priority Interpretation',
                'value': 'Based on operational impact, recoverability, and risk to service continuity.',
            },
            {'label': 'Snapshot Status', 'value': _text(snapshot_summary.get('status'), 'Unknown')},
        ],
        'included': (
            'Committed inventory snapshot as of the data cut-off.',
            'Committed metrics and alert observations within the reporting period.',
            'Alert summaries available at the report cut-off.',
            'Trend calculations based on historical observations.',
            'Forecast projections for the configured forecast window.',
        ),
        'excluded': (
            'Live cluster state after the data cut-off.',
            'Unapproved change windows and in-flight maintenance.',
            'Future deployments or changes not yet observed.',
            'Manual operator assumptions or hypothetical mitigations.',
        ),
        'limitations': (
            'Disconnected resources are excluded from active headroom calculations when evidence identifies them.',
            'Forecast results do not include planned deployments, infrastructure expansion, or workload migrations.',
            'Top-consumer sections show leading contributors only; complete rankings and full identities remain available in KAORI detail views.',
            'Data freshness may differ by source based on collection intervals and retention policies.',
        ),
        'status_language': (
            {
                'label': 'Not Available',
                'description': 'No data exists for the requested dimension within the reporting period.',
            },
            {
                'label': 'Not Collected',
                'description': 'Data was not collected because of configuration, permission, or collection failure.',
            },
            {
                'label': 'Partial Coverage',
                'description': 'Data was collected, but coverage is incomplete for the requested scope.',
            },
            {
                'label': 'Source Unavailable',
                'description': 'The source was unreachable or not providing data at the cut-off.',
            },
        ),
        'guidance': (
            'This report supports operational planning and decision-making. Validate all findings '
            'and recommendations against live cluster state before taking remediation or change actions.'
        ),
    }
