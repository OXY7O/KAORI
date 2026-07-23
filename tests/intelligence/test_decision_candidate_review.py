from datetime import UTC, datetime, timedelta

import pytest

from app.extensions import db
from app.knowledge.candidate_review import CandidateWorkflowError, dismiss_candidate, persist_candidate, promote_candidate
from app.knowledge.matching import DecisionCandidate
from app.models.intelligence import IntelligenceDecisionCandidate
from app.models.knowledge import KnowledgeRunbook, KnowledgeRunbookAlertBinding, KnowledgeRunbookRevision


def _seed():
    runbook = KnowledgeRunbook(runbook_key='pod.restart', title='Restart pod')
    db.session.add(runbook); db.session.flush()
    revision = KnowledgeRunbookRevision(
        runbook_id=runbook.id, version='1.0.0', publication_status='published',
        action_key='kubernetes.pod.restart', resolver_key='kubernetes.pod.restart',
        approval_policy='needs_approval', required_evidence_json=['cluster_id', 'namespace', 'pod_name'],
        required_capabilities_json=[], compatibility_profiles_json=[], change_level='major',
        parameter_schema_json={'type': 'object', 'properties': {}, 'additionalProperties': False},
        steps_json=[], content_hash='a' * 64,
    )
    db.session.add(revision); db.session.flush()
    binding = KnowledgeRunbookAlertBinding(binding_key='pod-not-ready', runbook_revision_id=revision.id, alertname='KubePodNotReady')
    db.session.add(binding); db.session.commit()
    candidate = DecisionCandidate(
        binding_key=binding.binding_key, runbook_key=runbook.runbook_key,
        runbook_revision_id=revision.public_id, runbook_version=revision.version,
        runbook_content_hash=revision.content_hash, action_key=revision.action_key,
        resolver_key=revision.resolver_key, approval_policy=revision.approval_policy,
        rule_key='kubernetes.pod.unhealthy', alert_fingerprint='fp-1', cluster_id='cluster-1',
        namespace='payments', evidence={'cluster_id': 'cluster-1', 'namespace': 'payments', 'pod_name': 'api-1'},
    )
    return candidate, revision


def test_duplicate_candidate_is_suppressed(app):
    with app.app_context():
        candidate, _ = _seed()
        first = persist_candidate(candidate, severity='critical', actor_user_id=None, actor_permissions={'intelligence.decisions.view'})
        second = persist_candidate(candidate, severity='critical', actor_user_id=None, actor_permissions={'intelligence.decisions.view'})
        assert first.id == second.id
        assert IntelligenceDecisionCandidate.query.count() == 1


def test_candidate_requires_explicit_promotion(app):
    with app.app_context():
        candidate, _ = _seed()
        record = persist_candidate(candidate, severity='critical', actor_user_id=None, actor_permissions={'intelligence.decisions.view'})
        decision = promote_candidate(
            record, rule_version='1.0.0', actor_user_id=None,
            actor_permissions={'intelligence.decisions.create'}, now=datetime.now(UTC),
        )
        assert record.review_status == 'promoted'
        assert record.promoted_decision_id == decision.id
        assert decision.workflow_status == 'pending_approval'


def test_withdrawn_revision_blocks_promotion(app):
    with app.app_context():
        candidate, revision = _seed()
        record = persist_candidate(candidate, severity='critical', actor_user_id=None, actor_permissions={'intelligence.decisions.view'})
        revision.publication_status = 'withdrawn'; db.session.commit()
        with pytest.raises(CandidateWorkflowError):
            promote_candidate(record, rule_version='1.0.0', actor_user_id=None, actor_permissions={'intelligence.decisions.create'})


def test_expired_candidate_cannot_be_promoted(app):
    with app.app_context():
        candidate, _ = _seed()
        now = datetime.now(UTC)
        record = persist_candidate(candidate, severity='critical', actor_user_id=None, actor_permissions={'intelligence.decisions.view'}, ttl=timedelta(seconds=1), now=now)
        with pytest.raises(CandidateWorkflowError):
            promote_candidate(record, rule_version='1.0.0', actor_user_id=None, actor_permissions={'intelligence.decisions.create'}, now=now + timedelta(seconds=2))
        assert record.review_status == 'expired'
