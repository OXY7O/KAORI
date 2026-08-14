from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from app.extensions.db import db
from app.models.audit import AuditEvent
from app.models.knowledge import KnowledgeRunbookAlertBinding, KnowledgeRunbookRevision

MANAGE_PERMISSION = 'knowledge.runbooks.manage'


class RunbookMatchError(ValueError):
    """Raised when alert-to-runbook resolution is invalid or ambiguous."""


@dataclass(frozen=True, slots=True)
class DecisionCandidate:
    """Non-executable preview produced from alert evidence and a published revision."""

    binding_key: str
    runbook_key: str
    runbook_revision_id: str
    runbook_version: str
    runbook_content_hash: str
    action_key: str
    resolver_key: str
    approval_policy: str
    rule_key: str | None
    alert_fingerprint: str | None
    cluster_id: str | None
    namespace: str | None
    evidence: Mapping[str, Any]
    executable: bool = False


def create_alert_binding(
    revision: KnowledgeRunbookRevision,
    *,
    binding_key: str,
    rule_key: str | None = None,
    alertname: str | None = None,
    cluster_id: str | None = None,
    namespace: str | None = None,
    required_labels: Mapping[str, str] | None = None,
    evidence_mapping: Mapping[str, str] | None = None,
    priority: int = 100,
    actor_user_id: int | None,
    actor_permissions: Collection[str],
) -> KnowledgeRunbookAlertBinding:
    if MANAGE_PERMISSION not in actor_permissions:
        raise RunbookMatchError(f'Missing required permission: {MANAGE_PERMISSION}.')
    if revision.publication_status != 'published':
        raise RunbookMatchError('Alert bindings require a published runbook revision.')
    key = binding_key.strip()
    if not key or (not _text(rule_key) and not _text(alertname)):
        raise RunbookMatchError('Binding key and at least one rule or alert selector are required.')
    record = KnowledgeRunbookAlertBinding()
    record.binding_key = key
    record.runbook_revision_id = revision.id
    record.rule_key = _text(rule_key)
    record.alertname = _text(alertname)
    record.cluster_id = _text(cluster_id)
    record.namespace = _text(namespace)
    record.required_labels_json = dict(required_labels or {})
    record.evidence_mapping_json = dict(evidence_mapping or {})
    record.priority = int(priority)
    record.created_by_user_id = actor_user_id
    db.session.add(record)
    _audit(actor_user_id, key, 'knowledge.runbook_binding.created', 'KAORI alert-to-runbook binding created.')
    db.session.commit()
    return record


def set_alert_binding_status(
    binding: KnowledgeRunbookAlertBinding,
    *,
    lifecycle_status: str,
    actor_user_id: int | None,
    actor_permissions: Collection[str],
) -> KnowledgeRunbookAlertBinding:
    if MANAGE_PERMISSION not in actor_permissions:
        raise RunbookMatchError(f'Missing required permission: {MANAGE_PERMISSION}.')
    if lifecycle_status not in {'active', 'disabled'}:
        raise RunbookMatchError('Binding status must be active or disabled.')
    if binding.lifecycle_status == lifecycle_status:
        return binding
    binding.lifecycle_status = lifecycle_status
    action = 'knowledge.runbook_binding.enabled' if lifecycle_status == 'active' else 'knowledge.runbook_binding.disabled'
    _audit(
        actor_user_id,
        binding.binding_key,
        action,
        f'KAORI runbook binding {lifecycle_status}.',
    )
    db.session.commit()
    return binding


def match_alert_to_runbook(
    alert: Mapping[str, Any],
    bindings: Sequence[KnowledgeRunbookAlertBinding],
) -> DecisionCandidate:
    labels = alert.get('labels')
    if not isinstance(labels, Mapping):
        raise RunbookMatchError('Alert labels must be a mapping.')
    active = [
        binding for binding in bindings if binding.lifecycle_status == 'active' and _matches(binding, alert, labels)
    ]
    if not active:
        raise RunbookMatchError('No published runbook binding matches this alert.')
    active.sort(key=lambda item: (item.priority, item.binding_key))
    best_priority = active[0].priority
    winners = [item for item in active if item.priority == best_priority]
    if len(winners) != 1:
        keys = ', '.join(item.binding_key for item in winners)
        raise RunbookMatchError(f'Ambiguous runbook bindings at priority {best_priority}: {keys}.')
    binding = winners[0]
    revision = binding.revision
    if revision.publication_status != 'published':
        raise RunbookMatchError('Matched runbook revision is no longer published.')
    evidence = _extract_evidence(alert, labels, binding.evidence_mapping_json)
    missing = [key for key in revision.required_evidence_json if key not in evidence or evidence[key] in (None, '')]
    if missing:
        raise RunbookMatchError(f'Matched alert evidence is incomplete: {", ".join(sorted(missing))}.')
    return DecisionCandidate(
        binding_key=binding.binding_key,
        runbook_key=revision.runbook.runbook_key,
        runbook_revision_id=revision.public_id,
        runbook_version=revision.version,
        runbook_content_hash=revision.content_hash,
        action_key=revision.action_key,
        resolver_key=revision.resolver_key,
        approval_policy=revision.approval_policy,
        rule_key=_text(alert.get('rule_key') or labels.get('alertname') or binding.rule_key or binding.alertname),
        alert_fingerprint=_text(alert.get('fingerprint') or labels.get('fingerprint')),
        cluster_id=_text(evidence.get('cluster_id')),
        namespace=_text(evidence.get('namespace')),
        evidence=MappingProxyType(evidence),
        executable=False,
    )


def _matches(binding: KnowledgeRunbookAlertBinding, alert: Mapping[str, Any], labels: Mapping[str, Any]) -> bool:
    rule_key = _text(alert.get('rule_key'))
    alertname = _text(labels.get('alertname') or alert.get('alertname'))
    cluster_id = _text(alert.get('cluster_id') or labels.get('cluster_id') or labels.get('cluster'))
    namespace = _text(alert.get('namespace') or labels.get('namespace'))
    if binding.rule_key and binding.rule_key != rule_key:
        return False
    if binding.alertname and binding.alertname != alertname:
        return False
    if binding.cluster_id and binding.cluster_id != cluster_id:
        return False
    if binding.namespace and binding.namespace != namespace:
        return False
    return all(_text(labels.get(key)) == expected for key, expected in binding.required_labels_json.items())


def _extract_evidence(
    alert: Mapping[str, Any], labels: Mapping[str, Any], mapping: Mapping[str, str]
) -> dict[str, Any]:
    evidence = dict(alert.get('evidence') or {})
    defaults = {
        'cluster_id': alert.get('cluster_id') or labels.get('cluster_id') or labels.get('cluster'),
        'namespace': alert.get('namespace') or labels.get('namespace'),
        'alert_fingerprint': alert.get('fingerprint') or labels.get('fingerprint'),
        'alertname': labels.get('alertname') or alert.get('alertname'),
    }
    for key, value in defaults.items():
        if value not in (None, ''):
            evidence.setdefault(key, value)
    for evidence_key, label_key in mapping.items():
        if label_key in labels:
            evidence[evidence_key] = labels[label_key]
    return evidence


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _audit(actor_user_id: int | None, target_id: str, action: str, summary: str) -> None:
    event = AuditEvent()
    event.actor_user_id = actor_user_id
    event.action = action
    event.target_type = 'knowledge_runbook_binding'
    event.target_id = target_id
    event.summary = summary
    event.metadata_json = {}
    db.session.add(event)
