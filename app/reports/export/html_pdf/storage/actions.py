from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.reports.export.html_pdf.storage.model import metric, text


def recommendation_cards(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = payload.get('recommendation_cards') or payload.get('actionable_recommendations') or ()
    result: list[dict[str, Any]] = []
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes, bytearray)):
        return result
    for item in raw:
        if not isinstance(item, Mapping):
            continue
        priority_raw = text(item.get('priority'), 'Info')
        priority = {'critical': 'P1', 'warning': 'P2', 'review': 'P2', 'normal': 'P3', 'info': 'P3'}.get(
            priority_raw.lower(), priority_raw if priority_raw in {'P1', 'P2', 'P3'} else 'P3'
        )
        result.append(
            {
                'title': text(item.get('title'), 'Review Storage Evidence'),
                'description': text(item.get('description'), 'Validate the committed storage evidence and ownership boundary.'),
                'priority': priority,
                'owner': _owner_for_source(text(item.get('source'), 'storage')),
                'actionable': bool(item.get('is_actionable', True)),
            }
        )
    return result


def executive_findings(
    *, capacity: Mapping[str, Any], local_risks: int, filesystem_available: bool, pvc_available: bool, pv_available: bool
) -> tuple[dict[str, str], ...]:
    findings: list[dict[str, str]] = []
    if local_risks:
        findings.append(_finding('F1', 'P2', 'Review Local Filesystem Risk', 'Platform Operations', 'Open', 'warning', f'{local_risks} filesystem risk item(s) require identity, owner, live-state, and remediation validation.'))
    if not filesystem_available:
        findings.append(_finding('F2', 'P2', 'Restore Node Filesystem Coverage', 'Observability Owner', 'Review', 'warning', 'Collect node, mount, used, capacity, available, and operational-state evidence.'))
    if not pvc_available or not pv_available:
        findings.append(_finding('F3', 'P3', 'Restore PV/PVC Evidence Coverage', 'Observability Owner', 'Planned', 'info', 'Keep persistent inventory, claim utilization, and lifecycle evidence explicit and scope-aligned.'))
    findings.append(_finding('F4', 'P3', 'Maintain Aggregate Headroom Monitoring', 'Platform Operations', 'Current' if capacity.get('evidence_available') else 'Review', 'normal' if capacity.get('evidence_available') else 'warning', 'Continue threshold monitoring without using aggregate headroom to clear localized risk.'))
    return tuple(findings[:4])


def executive_title(capacity: Mapping[str, Any], local_risks: int) -> str:
    if not capacity.get('evidence_available'):
        return 'Aggregate storage capacity evidence is not available.'
    if local_risks:
        return 'Aggregate storage remains below warning, with localized risk still open.'
    return 'Aggregate storage is below the warning band.'


def executive_body(capacity: Mapping[str, Any], local_risks: int, gaps: int) -> str:
    if not capacity.get('evidence_available'):
        return 'No aggregate capacity conclusion can be assigned until matching used, total, and available evidence is committed.'
    return f'Committed utilization is {capacity["used_percent_display"]}, leaving {capacity["headroom_display"]} headroom. {local_risks} localized risk item(s) and {gaps} evidence gap(s) remain separate from the aggregate denominator.'


def risk_register(
    *, capacity: Mapping[str, Any], local_risks: int, filesystem_available: bool, pvc_risks: int,
    pvc_available: bool, pv_risks: int, expansion_available: bool
) -> tuple[dict[str, str], ...]:
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


def recommendation_plan(
    *, recommendation_cards: list[dict[str, Any]], risk_register: tuple[dict[str, str], ...], capacity: Mapping[str, Any]
) -> tuple[dict[str, str], ...]:
    items: list[dict[str, str]] = []
    for card in recommendation_cards:
        if card['actionable']:
            items.append(_action(card['priority'], card['title'], card['owner'], card['description'], card['priority']))
    for risk in risk_register:
        if any(item['title'].lower() == risk['title'].lower() for item in items):
            continue
        items.append(_action(risk['priority'], _recommendation_title(risk['title']), risk['owner'], risk['description'], risk['priority'], tone=risk['tone']))
    if capacity.get('evidence_available') and not any('headroom' in item['title'].lower() or 'capacity monitoring' in item['title'].lower() for item in items):
        items.append({'ref': '', 'priority': 'P3', 'title': 'Maintain Aggregate Capacity Monitoring', 'owner': 'Platform Operations', 'target': 'This Month', 'status': 'Current', 'tone': 'normal', 'description': f'Continue monitoring {capacity.get("used_percent_display")} aggregate utilization while preserving threshold and denominator evidence.'})
    rank = {'P1': 0, 'P2': 1, 'P3': 2}
    items.sort(key=lambda item: (rank.get(item['priority'], 9), item['title']))
    for index, item in enumerate(items[:5], start=1):
        item['ref'] = f'A{index}'
    return tuple(items[:5])


def recommendation_metrics(items: tuple[dict[str, str], ...]) -> tuple[dict[str, str], ...]:
    counts = {priority: sum(1 for item in items if item['priority'] == priority) for priority in ('P1', 'P2', 'P3')}
    return (
        metric('P1 Actions', str(counts['P1']), 'Open' if counts['P1'] else 'None', 'critical' if counts['P1'] else 'normal'),
        metric('P2 Actions', str(counts['P2']), 'Open' if counts['P2'] else 'None', 'warning' if counts['P2'] else 'normal'),
        metric('P3 Actions', str(counts['P3']), 'Planned' if counts['P3'] else 'None', 'info' if counts['P3'] else 'normal'),
        metric('Validation Gates', str(len(items)), 'Required', 'info'),
    )


def assigned_owners(items: tuple[dict[str, str], ...]) -> str:
    owners: dict[str, int] = {}
    for item in items:
        owners[item['owner']] = owners.get(item['owner'], 0) + 1
    return '; '.join(f'{owner}: {count} action(s)' for owner, count in owners.items()) or 'No action owner assigned.'


def _owner_for_source(source: str) -> str:
    return 'Observability Owner' if any(token in source.lower() for token in ('metric', 'observability', 'coverage')) else 'Platform Operations'


def _finding(ref: str, priority: str, title: str, owner: str, status: str, tone: str, description: str) -> dict[str, str]:
    return {'ref': ref, 'priority': priority, 'title': title, 'owner': owner, 'status': status, 'tone': tone, 'description': description}


def _risk(ref: str, title: str, priority: str, impact: str, owner: str, status: str, tone: str, description: str) -> dict[str, str]:
    return {'ref': ref, 'title': title, 'priority': priority, 'impact': impact, 'owner': owner, 'status': status, 'tone': tone, 'description': description}


def _action(priority: str, title: str, owner: str, description: str, rank_priority: str, *, tone: str | None = None) -> dict[str, str]:
    return {
        'ref': '', 'priority': priority, 'title': title, 'owner': owner,
        'target': 'Next Week' if rank_priority in {'P1', 'P2'} else 'This Month',
        'status': 'Open' if rank_priority in {'P1', 'P2'} else 'Planned',
        'tone': tone or ('critical' if rank_priority == 'P1' else 'warning' if rank_priority == 'P2' else 'info'),
        'description': description,
    }


def _recommendation_title(risk_title: str) -> str:
    if risk_title.startswith('Local'):
        return f'Identify and Validate {risk_title}'
    if 'Coverage Gap' in risk_title:
        return f'Restore {risk_title.replace(" Gap", "")}'
    if 'Unknown' in risk_title:
        return f'Validate {risk_title.replace(" Unknown", "")}'
    return f'Review {risk_title}'
