from __future__ import annotations

from typing import Any

from app.intelligence.alert_intelligence.service import list_active_alert_events
from app.intelligence.knowledge.candidate_review import VIEW_PERMISSION, persist_candidate
from app.intelligence.knowledge.matching import RunbookMatchError, match_alert_to_runbook
from app.models.knowledge import KnowledgeRunbookAlertBinding


def materialize_active_alert_candidates() -> dict[str, int]:
    """Materialize non-executable candidates from active Kubernetes alert evidence.

    Notification delivery is intentionally not part of this pipeline. Both features
    may read the same normalized alert source, but Automation Control owns matching
    and candidate persistence independently.
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
    }
    if not bindings:
        return totals

    for event in list_active_alert_events():
        totals['events'] += 1
        if event.get('domain') != 'kubernetes':
            continue
        totals['kubernetes_events'] += 1
        alert = _candidate_alert(event)
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
            severity=str(alert.get('severity') or 'info'),
            actor_user_id=None,
            actor_permissions={VIEW_PERMISSION},
        )
        if existing_public_id == record.public_id:
            totals['duplicate'] += 1
        else:
            totals['persisted'] += 1
    return totals


def _candidate_alert(event: dict[str, Any]) -> dict[str, Any]:
    source = dict(event.get('alert') or {})
    labels = dict(source.get('labels') or {})
    alertname = str(labels.get('alertname') or source.get('name') or '').strip()
    if alertname:
        labels.setdefault('alertname', alertname)
    cluster_id = str(event.get('asset_key') or '').strip()
    namespace = str(source.get('namespace') or labels.get('namespace') or '').strip()
    if namespace == '-':
        namespace = ''
    fingerprint = str(source.get('fingerprint') or labels.get('fingerprint') or '').strip()
    evidence = dict(source.get('evidence') or {})
    evidence.setdefault('cluster_id', cluster_id)
    if namespace:
        evidence.setdefault('namespace', namespace)
    if fingerprint:
        evidence.setdefault('alert_fingerprint', fingerprint)
    evidence.setdefault('alertname', alertname)

    return {
        **source,
        'alertname': alertname,
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
