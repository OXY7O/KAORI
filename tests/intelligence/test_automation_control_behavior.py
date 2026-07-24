from __future__ import annotations

import pytest
from flask import Flask

from app.automation_control.presentation import build_automation_control_context, upsert_deployment_policy
from app.extensions import db
from app.integrations.resolver_bootstrap import ACTION_DEPLOYMENT_RESTART, init_resolver_registry
from app.models.audit import AuditEvent
from app.models.cluster import Cluster
from app.models.resolver import ResolverDeploymentPolicy
from app.resolver.production_readiness import ProductionReadinessError, assert_deployment_policy_allows


@pytest.fixture
def app() -> Flask:
    application = Flask(__name__)
    application.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI='sqlite:///:memory:',
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        RESOLVER_ENABLED_ACTIONS=ACTION_DEPLOYMENT_RESTART,
        RESOLVER_KUBERNETES_ALLOWED_NAMESPACES='payments,platform',
    )
    db.init_app(application)
    with application.app_context():
        import app.models  # noqa: F401

        db.create_all()
        init_resolver_registry(application)
        yield application
        db.session.remove()
        db.drop_all()


def _cluster() -> Cluster:
    record = Cluster()
    record.id = 'cluster-a'
    record.name = 'Cluster A'
    record.environment = 'production'
    db.session.add(record)
    db.session.commit()
    return record


def test_foundation_map_paginates_all_twenty_domains(app: Flask) -> None:
    with app.app_context():
        context = build_automation_control_context({'workspace': 'overview', 'page': 2, 'per_page': 5})

        assert [row['number'] for row in context['domain_rows']] == [6, 7, 8, 9, 10]
        assert context['pagination']['total_items'] == 20
        assert context['pagination']['total_pages'] == 4
        assert context['resource_label'] == 'domains'


def test_active_deployment_policy_is_registry_checked_and_audited(app: Flask) -> None:
    with app.app_context():
        _cluster()

        created = upsert_deployment_policy(
            cluster_id='cluster-a',
            action_key=ACTION_DEPLOYMENT_RESTART,
            lifecycle_status='active',
            allowed_namespaces=['payments', ' payments ', 'platform'],
            required_registry_fingerprint=None,
            actor_user_id=None,
        )
        fingerprint = app.config['RESOLVER_REGISTRY_FINGERPRINT']
        updated = upsert_deployment_policy(
            cluster_id='cluster-a',
            action_key=ACTION_DEPLOYMENT_RESTART,
            lifecycle_status='disabled',
            allowed_namespaces=[],
            required_registry_fingerprint=fingerprint,
            actor_user_id=None,
        )

        assert created.id == updated.id
        assert updated.lifecycle_status == 'disabled'
        assert updated.allowed_namespaces_json == []
        assert updated.required_registry_fingerprint == fingerprint
        assert ResolverDeploymentPolicy.query.count() == 1
        assert AuditEvent.query.filter_by(target_type='resolver_deployment_policy').count() == 2


def test_active_deployment_policy_requires_explicit_namespace_allowlist(app: Flask) -> None:
    with app.app_context():
        _cluster()

        with pytest.raises(ValueError, match='explicit namespace allowlist'):
            upsert_deployment_policy(
                cluster_id='cluster-a',
                action_key=ACTION_DEPLOYMENT_RESTART,
                lifecycle_status='active',
                allowed_namespaces=[],
                required_registry_fingerprint=None,
                actor_user_id=None,
            )

        assert ResolverDeploymentPolicy.query.count() == 0


def test_deployment_policy_rejects_stale_registry_fingerprint(app: Flask) -> None:
    with app.app_context():
        _cluster()

        with pytest.raises(ValueError, match='does not match'):
            upsert_deployment_policy(
                cluster_id='cluster-a',
                action_key=ACTION_DEPLOYMENT_RESTART,
                lifecycle_status='active',
                allowed_namespaces=['payments'],
                required_registry_fingerprint='stale-registry-fingerprint',
                actor_user_id=None,
            )

        assert ResolverDeploymentPolicy.query.count() == 0


def test_runtime_policy_gate_enforces_namespace_and_registry_parity(app: Flask) -> None:
    with app.app_context():
        _cluster()
        fingerprint = app.config['RESOLVER_REGISTRY_FINGERPRINT']
        upsert_deployment_policy(
            cluster_id='cluster-a',
            action_key=ACTION_DEPLOYMENT_RESTART,
            lifecycle_status='active',
            allowed_namespaces=['payments'],
            required_registry_fingerprint=fingerprint,
            actor_user_id=None,
        )

        policy = assert_deployment_policy_allows(
            cluster_id='cluster-a',
            namespace='payments',
            action_key=ACTION_DEPLOYMENT_RESTART,
            registry_fingerprint=fingerprint,
        )
        assert policy.lifecycle_status == 'active'

        with pytest.raises(ProductionReadinessError, match='namespace'):
            assert_deployment_policy_allows(
                cluster_id='cluster-a',
                namespace='platform',
                action_key=ACTION_DEPLOYMENT_RESTART,
                registry_fingerprint=fingerprint,
            )
        with pytest.raises(ProductionReadinessError, match='fingerprint'):
            assert_deployment_policy_allows(
                cluster_id='cluster-a',
                namespace='payments',
                action_key=ACTION_DEPLOYMENT_RESTART,
                registry_fingerprint='different-registry',
            )
