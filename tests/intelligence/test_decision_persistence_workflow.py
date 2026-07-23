from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from flask import Flask

from app.extensions import db
from app.intelligence.decision import create_decision_snapshot
from app.intelligence.workflow import (
    APPROVE_PERMISSION,
    CREATE_PERMISSION,
    EXECUTE_PERMISSION,
    DecisionWorkflowError,
    approve_decision,
    consume_execution_token,
    issue_persisted_execution_token,
    persist_decision,
)
from app.models.audit import AuditEvent
from app.models.intelligence import IntelligenceExecutionJournal


@pytest.fixture
def app() -> Flask:
    application = Flask(__name__)
    application.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI='sqlite:///:memory:',
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )
    db.init_app(application)
    with application.app_context():
        # Import all model metadata before create_all so foreign keys resolve.
        import app.models  # noqa: F401

        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


def _snapshot(now: datetime):
    return create_decision_snapshot(
        {
            'rule_key': 'kubernetes.pod.high_restart_count:cluster-a:default:api-0',
            'severity': 'warning',
            'evidence': {
                'cluster_id': 'cluster-a',
                'namespace': 'default',
                'inventory_generation': '2026-07-23T08:00:00+00:00',
                'restart_count': 19,
            },
        },
        action_key='kubernetes.pod.restart',
        rule_version='1.0.0',
        knowledge_version='runbook-7',
        actor_can_execute=True,
        ttl=timedelta(minutes=15),
        now=now,
    )


def test_approval_and_one_time_token_consumption(app) -> None:
    now = datetime(2026, 7, 23, 8, 5, tzinfo=UTC)
    with app.app_context():
        record = persist_decision(
            _snapshot(now),
            actor_user_id=None,
            actor_permissions={CREATE_PERMISSION},
        )
        assert record.workflow_status == 'pending_approval'

        approve_decision(
            record,
            actor_user_id=None,
            actor_permissions={APPROVE_PERMISSION},
            reason='Approved for controlled remediation.',
            now=now + timedelta(seconds=1),
        )
        assert record.workflow_status == 'approved'

        token, journal = issue_persisted_execution_token(
            record,
            secret_key='test-secret',
            actor_user_id=None,
            actor_permissions={EXECUTE_PERMISSION},
            now=now + timedelta(seconds=2),
        )
        assert journal.status == 'authorized'

        consumed = consume_execution_token(
            record,
            token,
            secret_key='test-secret',
            actor_user_id=None,
            actor_permissions={EXECUTE_PERMISSION},
            current_evidence=dict(record.evidence_json),
            now=now + timedelta(seconds=3),
        )
        assert consumed.status == 'dispatched'
        assert consumed.consumed_at is not None
        assert IntelligenceExecutionJournal.query.count() == 1

        with pytest.raises(DecisionWorkflowError, match='already been consumed'):
            consume_execution_token(
                record,
                token,
                secret_key='test-secret',
                actor_user_id=None,
                actor_permissions={EXECUTE_PERMISSION},
                current_evidence=dict(record.evidence_json),
                now=now + timedelta(seconds=4),
            )

        actions = {event.action for event in AuditEvent.query.all()}
        assert {
            'intelligence.decision.created',
            'intelligence.decision.approved',
            'intelligence.execution.authorized',
            'intelligence.execution.dispatched',
        }.issubset(actions)


def test_token_rejects_changed_evidence(app) -> None:
    now = datetime(2026, 7, 23, 8, 5, tzinfo=UTC)
    with app.app_context():
        record = persist_decision(
            _snapshot(now),
            actor_user_id=None,
            actor_permissions={CREATE_PERMISSION},
        )
        approve_decision(
            record,
            actor_user_id=None,
            actor_permissions={APPROVE_PERMISSION},
            now=now + timedelta(seconds=1),
        )
        token, _ = issue_persisted_execution_token(
            record,
            secret_key='test-secret',
            actor_user_id=None,
            actor_permissions={EXECUTE_PERMISSION},
            now=now + timedelta(seconds=2),
        )
        changed = dict(record.evidence_json)
        changed['restart_count'] = 0
        with pytest.raises(DecisionWorkflowError, match='Current evidence differs'):
            consume_execution_token(
                record,
                token,
                secret_key='test-secret',
                actor_user_id=None,
                actor_permissions={EXECUTE_PERMISSION},
                current_evidence=changed,
                now=now + timedelta(seconds=3),
            )
