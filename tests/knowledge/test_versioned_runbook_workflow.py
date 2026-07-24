from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from flask import Flask

from app.extensions import db
from app.intelligence.decision import create_decision_snapshot
from app.intelligence.workflow import CREATE_PERMISSION, persist_decision, snapshot_from_record
from app.knowledge.service import (
    MANAGE_PERMISSION,
    PUBLISH_PERMISSION,
    KnowledgeError,
    assert_required_evidence,
    create_revision,
    create_runbook,
    publish_revision,
    resolve_published_revision,
)
from app.resolver.contracts import DryRunResult, ResolverResult, ResolverResultStatus
from app.resolver.registry import ResolverRegistry


class CompatibleAdapter:
    action_key = 'kubernetes.pod.restart'
    capability_keys: tuple[str, ...] = ()
    compatibility_profiles: tuple[str, ...] = ()
    rollback_required = True

    def dry_run(self, context):
        return DryRunResult(True, 'safe')

    def execute(self, context, dry_run):
        return ResolverResult(ResolverResultStatus.SUCCEEDED, 'done')


def _resolver_registry() -> ResolverRegistry:
    registry = ResolverRegistry()
    registry.register(CompatibleAdapter())
    return registry


@pytest.fixture
def app() -> Flask:
    application = Flask(__name__)
    application.config.update(
        TESTING=True, SQLALCHEMY_DATABASE_URI='sqlite:///:memory:', SQLALCHEMY_TRACK_MODIFICATIONS=False
    )
    db.init_app(application)
    with application.app_context():
        import app.models  # noqa: F401

        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


def test_published_revision_is_resolved_and_locked_into_decision(app) -> None:
    with app.app_context():
        runbook = create_runbook(
            runbook_key='kubernetes.pod.restart',
            title='Restart unhealthy pod',
            description=None,
            actor_user_id=None,
            actor_permissions={MANAGE_PERMISSION},
        )
        revision = create_revision(
            runbook,
            version='1.0.0',
            action_key='kubernetes.pod.restart',
            resolver_key='kubernetes.pod.restart',
            approval_policy='needs_approval',
            required_evidence=['cluster_id', 'namespace', 'pod_name'],
            parameter_schema={
                'type': 'object',
                'properties': {'pod_name': {'type': 'string'}},
                'required': ['pod_name'],
                'additionalProperties': False,
            },
            steps=[{'order': 1, 'operation': 'delete_pod'}],
            rollback={'strategy': 'controller_recreate'},
            actor_user_id=None,
            actor_permissions={MANAGE_PERMISSION},
        )
        publish_revision(
            revision,
            actor_user_id=None,
            actor_permissions={PUBLISH_PERMISSION},
            resolver_registry=_resolver_registry(),
            now=datetime(2026, 7, 23, tzinfo=UTC),
        )
        resolved = resolve_published_revision(runbook_key=runbook.runbook_key, version='1.0.0')
        evidence = {'cluster_id': 'cluster-a', 'namespace': 'default', 'pod_name': 'api-0'}
        assert_required_evidence(resolved, evidence)

        snapshot = create_decision_snapshot(
            {'rule_key': 'kubernetes.pod.unhealthy_phase:api-0', 'severity': 'warning', 'evidence': evidence},
            action_key=resolved.action_key,
            rule_version='1.0.0',
            knowledge_version=resolved.version,
            runbook_key=runbook.runbook_key,
            runbook_revision_id=resolved.public_id,
            runbook_version=resolved.version,
            runbook_content_hash=resolved.content_hash,
            actor_can_execute=True,
            ttl=timedelta(minutes=15),
            now=datetime(2026, 7, 23, tzinfo=UTC),
        )
        record = persist_decision(snapshot, actor_user_id=None, actor_permissions={CREATE_PERMISSION})
        restored = snapshot_from_record(record)
        assert restored.runbook_revision_id == revision.public_id
        assert restored.runbook_content_hash == revision.content_hash
        assert record.runbook_revision_id == revision.id

        with pytest.raises(KnowledgeError, match='Only draft'):
            publish_revision(
                revision,
                actor_user_id=None,
                actor_permissions={PUBLISH_PERMISSION},
                resolver_registry=_resolver_registry(),
            )


def test_required_evidence_is_fail_closed(app) -> None:
    with app.app_context():
        runbook = create_runbook(
            runbook_key='kubernetes.node.uncordon',
            title='Uncordon node',
            description=None,
            actor_user_id=None,
            actor_permissions={MANAGE_PERMISSION},
        )
        revision = create_revision(
            runbook,
            version='1.0.0',
            action_key='kubernetes.node.uncordon',
            resolver_key='kubernetes.node.uncordon',
            approval_policy='needs_approval',
            required_evidence=['cluster_id', 'node_name'],
            parameter_schema={},
            steps=[{'order': 1, 'operation': 'uncordon'}],
            rollback=None,
            actor_user_id=None,
            actor_permissions={MANAGE_PERMISSION},
        )
        with pytest.raises(KnowledgeError, match='node_name'):
            assert_required_evidence(revision, {'cluster_id': 'cluster-a'})
