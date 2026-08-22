from __future__ import annotations

from typing import Any

from app.intelligence.alert_intelligence.lifecycle import active_delivery_silence
from app.intelligence.knowledge.candidate_review import VIEW_PERMISSION, persist_candidate
from app.intelligence.knowledge.matching import RunbookMatchError, match_alert_to_runbook
from app.models.alert_ops import AlertCase
from app.models.knowledge import KnowledgeRunbookAlertBinding


def materialize_active_alert_candidates() -> dict[str, int]:
    """Materialize non-executable Automation candidates from durable KAORI AlertCase records.

    Recommendation is the detection/advice layer. AlertCase is the operational source of
    truth consumed here, so raw Prometheus/Alertmanager evidence cannot bypass KAORI alert
    lifecycle, ownership, ACK, silence, routing, or incident evidence boundaries.
    """
    bindings = (
        KnowledgeRunbookAlertBinding.query.filter_by(lifecycle_status='active')
        .order_by(KnowledgeRunbookAlertBinding.priority.asc(), KnowledgeRunbookAlertBinding.id.asc())
        .all()
    )
    totals = {
        'events': 0,
        'kubernetes_events': 0,
        'matched': 0,
        'persisted': 0,
        'duplicate': 0,
        'unmatched': 0,
        'invalid': 0,
        'human_controlled': 0,
    }
    if not bindings:
        return totals

    cases = (
        AlertCase.query.filter(
            AlertCase.source_type == 'recommendation',
            AlertCase.source_state == 'firing',
            AlertCase.workflow_state != 'closed',
        )
        .order_by(AlertCase.first_seen_at.asc(), AlertCase.id.asc())
        .all()
    )
    for case in cases:
        totals['events'] += 1
        if case.domain != 'kubernetes':
            continue
        totals['kubernetes_events'] += 1
        alert = _candidate_alert(case)
        if bool(alert['evidence'].get('human_controlled')):
            totals['human_controlled'] += 1
        try:
            candidate = match_alert_to_runbook(alert, bindings)
        except RunbookMatchError as exc:
            if str(exc).startswith('No published runbook binding matches'):
                totals['unmatched'] += 1
            else:
                totals['invalid'] += 1
            continue

        totals['matched'] += 1
        existing_public_id = _candidate_public_id(candidate)
        record = persist_candidate(
            candidate,
            severity=case.severity,
            actor_user_id=None,
            actor_permissions={VIEW_PERMISSION},
        )
        if existing_public_id == record.public_id:
            totals['duplicate'] += 1
        else:
            totals['persisted'] += 1
    return totals


def _candidate_alert(case: AlertCase) -> dict[str, Any]:
    labels = dict(case.labels_json or {})
    alertname = str(labels.get('alertname') or case.alert_name or case.rule_key or '').strip()
    if alertname:
        labels.setdefault('alertname', alertname)
    labels.setdefault('source_type', 'recommendation')
    if case.rule_key:
        labels.setdefault('rule_key', case.rule_key)
    cluster_id = str(case.asset_key or '').strip()
    namespace = str(case.namespace or labels.get('namespace') or '').strip()
    fingerprint = str(case.fingerprint or case.case_key or '').strip()
    silenced = active_delivery_silence(case) is not None
    human_controlled = case.workflow_state in {'acknowledged', 'mitigating'} or silenced

    evidence = dict(case.evidence_json or {})
    evidence.update(
        {
            'alert_case_id': case.public_id,
            'alert_case_source': 'kaori_alert_case',
            'alert_case_source_state': case.source_state,
            'alert_case_workflow_state': case.workflow_state,
            'severity': case.severity,
            'cluster_id': cluster_id,
            'alert_fingerprint': fingerprint,
            'alertname': alertname,
            'human_controlled': human_controlled,
            # Future autonomous execution must honor this flag. Manual reviewed execution
            # remains possible through the existing governed Decision workflow.
            'autonomous_execution_allowed': not human_controlled,
        }
    )
    if namespace:
        evidence['namespace'] = namespace

    return {
        'name': case.alert_name,
        'alertname': alertname,
        'rule_key': case.rule_key,
        'severity': case.severity,
        'cluster_id': cluster_id,
        'namespace': namespace or None,
        'fingerprint': fingerprint or None,
        'labels': labels,
        'evidence': evidence,
    }


def _candidate_public_id(candidate: object) -> str | None:
    # Deduplication is enforced by persist_candidate. This helper intentionally
    # avoids duplicating its internal hash contract; it only detects whether the
    # returned record existed before this materialization iteration.
    from app.intelligence.decision import compute_evidence_hash
    from app.models.intelligence import IntelligenceDecisionCandidate

    evidence = dict(getattr(candidate, 'evidence'))
    evidence_hash = compute_evidence_hash(evidence)
    binding_key = str(getattr(candidate, 'binding_key'))
    revision_id = str(getattr(candidate, 'runbook_revision_id'))
    fingerprint = str(getattr(candidate, 'alert_fingerprint') or '')
    rows = IntelligenceDecisionCandidate.query.filter_by(
        evidence_hash=evidence_hash,
        alert_fingerprint=fingerprint or None,
    ).all()
    for row in rows:
        payload = row.candidate_json or {}
        if payload.get('binding_key') == binding_key and payload.get('runbook_revision_id') == revision_id:
            return row.public_id
    return None
