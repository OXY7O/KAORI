"""#2724: scope grant transitions require independent approver and atomic audit."""

from datetime import UTC, datetime, timedelta

import pytest
from cryptography.fernet import Fernet
from flask import Flask

from app.access import scope_policy, scoped_grants
from app.extensions.db import db
from app.models.integration import IntegrationInstance
from app.models.notification import Notification
from app.models.rbac import Permission, Role, RolePermission
from app.models.scope_access import ScopeAccessPolicy, ScopeAccessPolicyRevision
from app.models.user import User
from app.models.vault import VaultInstance


@pytest.fixture
def scope_store():
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY='test-only',
        SQLALCHEMY_DATABASE_URI='sqlite://',
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        INTEGRATION_CREDENTIAL_KEY=Fernet.generate_key().decode('ascii'),
    )
    db.init_app(app)
    tables = [
        Role.__table__,
        Permission.__table__,
        RolePermission.__table__,
        User.__table__,
        IntegrationInstance.__table__,
        VaultInstance.__table__,
        ScopeAccessPolicy.__table__,
        ScopeAccessPolicyRevision.__table__,
        Notification.__table__,
    ]
    with app.app_context():
        db.Model.metadata.create_all(bind=db.engine, tables=tables)
        role = Role(name='scope_test_admin', display_name='Scope Test Administrator')
        viewer_role = Role(name='scope_test_viewer', display_name='Scope Test Viewer')
        permissions = [
            Permission(key='roles.manage', module='access', action='manage'),
            Permission(key='users.manage', module='access', action='manage'),
            Permission(key='secrets_pki.view', module='secrets_pki', action='view'),
        ]
        db.session.add_all([role, viewer_role, *permissions])
        db.session.flush()
        db.session.add_all(
            [
                RolePermission(role_id=role.id, permission_id=permissions[0].id),
                RolePermission(role_id=role.id, permission_id=permissions[1].id),
                RolePermission(role_id=viewer_role.id, permission_id=permissions[2].id),
            ]
        )
        actors = [
            User(username='scope-requester', email='requester@test.invalid', role_id=role.id),
            User(username='scope-approver', email='approver@test.invalid', role_id=role.id),
            User(username='scope-viewer', email='viewer@test.invalid', role_id=viewer_role.id),
        ]
        db.session.add_all(actors)
        source = IntegrationInstance(
            integration_type='secrets_pki',
            provider_key='vault',
            adapter_key='vault_http_v1',
            name='Scope Test Vault',
            enabled=True,
            lifecycle_status='active',
            readiness_status='ready',
        )
        db.session.add(source)
        db.session.flush()
        db.session.add(
            VaultInstance(
                integration_instance_id=source.id,
                endpoint='https://vault.invalid',
                auth_mount='approle',
                role_id='test',
                secret_id='test-only',
                kv2_mounts=['kv'],
                verify_ssl=True,
            )
        )
        db.session.commit()
        try:
            yield {'requester': actors[0].id, 'approver': actors[1].id, 'viewer': actors[2].id, 'source': source.id}
        finally:
            db.session.remove()
            db.Model.metadata.drop_all(bind=db.engine, tables=list(reversed(tables)))


def _request(ids, *, mount='kv', namespace=''):
    now = datetime.now(UTC)
    return scoped_grants.request_scope_grant(
        actor_user_id=ids['requester'],
        principal_user_id=ids['viewer'],
        integration_instance_id=ids['source'],
        scope_level='vault_mount',
        provider_namespace=namespace,
        mount=mount,
        effective_from=now - timedelta(minutes=1),
        effective_until=now + timedelta(days=1),
        reason_code='operational_access',
    )


def test_draft_approval_and_revocation_share_durable_activity(scope_store):
    ids = scope_store
    policy = _request(ids)
    assert policy.current_revision == 1
    assert ScopeAccessPolicyRevision.query.filter_by(policy_id=policy.id).one().lifecycle_status == 'draft'
    assert Notification.query.filter_by(event_type='access_scope_grant_requested').count() == 1

    scoped_grants.approve_scope_grant(
        policy_id=policy.id,
        approver_user_id=ids['approver'],
        expected_revision=1,
    )
    db.session.expire_all()
    policy = db.session.get(ScopeAccessPolicy, policy.id)
    assert policy.current_revision == 2
    latest = ScopeAccessPolicyRevision.query.filter_by(policy_id=policy.id, revision_number=2).one()
    assert latest.lifecycle_status == 'active'
    assert latest.approved_by_user_id != latest.requested_by_user_id
    assert Notification.query.filter_by(event_type='access_scope_grant_approved').count() == 1

    scoped_grants.revoke_scope_grant(
        policy_id=policy.id,
        actor_user_id=ids['requester'],
        expected_revision=2,
    )
    db.session.expire_all()
    policy = db.session.get(ScopeAccessPolicy, policy.id)
    assert policy.current_revision == 3
    assert (
        ScopeAccessPolicyRevision.query.filter_by(
            policy_id=policy.id,
            revision_number=3,
        )
        .one()
        .lifecycle_status
        == 'revoked'
    )
    assert Notification.query.filter_by(event_type='access_scope_grant_revoked').count() == 1
    assert ScopeAccessPolicyRevision.query.filter_by(policy_id=policy.id).count() == 3


def test_self_approval_and_stale_revision_denied(scope_store):
    ids = scope_store
    policy = _request(ids)
    with pytest.raises(scoped_grants.ScopedGrantRejected):
        scoped_grants.approve_scope_grant(
            policy_id=policy.id,
            approver_user_id=ids['requester'],
            expected_revision=1,
        )
    with pytest.raises(scoped_grants.ScopedGrantRejected):
        scoped_grants.approve_scope_grant(
            policy_id=policy.id,
            approver_user_id=ids['approver'],
            expected_revision=9,
        )
    assert ScopeAccessPolicyRevision.query.filter_by(policy_id=policy.id).count() == 1


def test_audit_write_failure_rolls_back_approval(scope_store, monkeypatch):
    ids = scope_store
    policy = _request(ids)

    def sink_failure(**_kwargs):
        raise RuntimeError('persistence unavailable')

    monkeypatch.setattr(scoped_grants, 'stage_operational_activity', sink_failure)
    with pytest.raises(RuntimeError, match='persistence unavailable'):
        scoped_grants.approve_scope_grant(
            policy_id=policy.id,
            approver_user_id=ids['approver'],
            expected_revision=1,
        )
    db.session.expire_all()
    assert db.session.get(ScopeAccessPolicy, policy.id).current_revision == 1
    assert ScopeAccessPolicyRevision.query.filter_by(policy_id=policy.id).count() == 1


def test_foreign_mount_and_unauthorized_actor_fail_closed(scope_store):
    ids = scope_store
    with pytest.raises(scoped_grants.ScopedGrantRejected):
        _request(ids, mount='elsewhere')
    with pytest.raises(scoped_grants.ScopedGrantRejected):
        _request(ids, namespace='foreign')
    with pytest.raises(scoped_grants.ScopedGrantRejected):
        scoped_grants.request_scope_grant(
            actor_user_id=ids['viewer'],
            principal_user_id=ids['viewer'],
            integration_instance_id=ids['source'],
            scope_level='instance',
            provider_namespace=None,
            mount=None,
            effective_from=datetime.now(UTC),
            effective_until=datetime.now(UTC) + timedelta(days=1),
            reason_code='operational_access',
        )
    assert ScopeAccessPolicy.query.count() == 0
    assert Notification.query.count() == 0


def test_audit_does_not_include_vault_mount_or_provider_secret(scope_store):
    ids = scope_store
    _request(ids)
    notification = Notification.query.one()
    rendered = repr(notification.metadata_json)
    assert 'kv' not in notification.metadata_json
    assert 'mount' not in notification.metadata_json
    assert 'vault.invalid' not in rendered
    assert 'test-only' not in rendered


def test_exact_evaluator_only_qualifies_current_approved_mount(scope_store):
    ids = scope_store
    before = scope_policy.evaluate_exact_vault_scope(
        actor_user_id=ids['viewer'],
        instance_id=ids['source'],
        provider_namespace='',
        mount='kv',
    )
    assert before.status == 'deny'
    policy = _request(ids)
    pending = scope_policy.evaluate_exact_vault_scope(
        actor_user_id=ids['viewer'],
        instance_id=ids['source'],
        provider_namespace='',
        mount='kv',
    )
    assert pending.status == 'deny'
    scoped_grants.approve_scope_grant(
        policy_id=policy.id,
        approver_user_id=ids['approver'],
        expected_revision=1,
    )
    admitted = scope_policy.evaluate_exact_vault_scope(
        actor_user_id=ids['viewer'],
        instance_id=ids['source'],
        provider_namespace='',
        mount='kv',
    )
    assert admitted.allowed
    assert admitted.policy_ref == policy.id and admitted.revision == 2
    assert not scope_policy.evaluate_exact_vault_scope(
        actor_user_id=ids['viewer'],
        instance_id=ids['source'],
        provider_namespace='foreign',
        mount='kv',
    ).allowed
    assert not scope_policy.evaluate_exact_vault_scope(
        actor_user_id=ids['viewer'],
        instance_id=ids['source'],
        provider_namespace='',
        mount='other',
    ).allowed
    scoped_grants.revoke_scope_grant(
        policy_id=policy.id,
        actor_user_id=ids['requester'],
        expected_revision=2,
    )
    assert (
        scope_policy.evaluate_exact_vault_scope(
            actor_user_id=ids['viewer'],
            instance_id=ids['source'],
            provider_namespace='',
            mount='kv',
        ).status
        == 'deny'
    )


def test_instance_only_grant_is_not_inherited_to_vault_mount(scope_store):
    ids = scope_store
    now = datetime.now(UTC)
    grant = scoped_grants.request_scope_grant(
        actor_user_id=ids['requester'],
        principal_user_id=ids['viewer'],
        integration_instance_id=ids['source'],
        scope_level='instance',
        provider_namespace=None,
        mount=None,
        effective_from=now - timedelta(minutes=1),
        effective_until=now + timedelta(days=1),
        reason_code='audit_review',
    )
    scoped_grants.approve_scope_grant(
        policy_id=grant.id,
        approver_user_id=ids['approver'],
        expected_revision=1,
    )
    result = scope_policy.evaluate_exact_vault_scope(
        actor_user_id=ids['viewer'],
        instance_id=ids['source'],
        provider_namespace='',
        mount='kv',
    )
    assert result.status == 'deny'


def test_scope_evaluator_rejects_unassigned_superadmin_role(scope_store):
    ids = scope_store
    admin = db.session.get(User, ids['requester'])
    admin.is_super_admin = True
    admin.role_id = None
    db.session.commit()
    result = scope_policy.evaluate_exact_vault_scope(
        actor_user_id=ids['requester'],
        instance_id=ids['source'],
        provider_namespace='',
        mount='kv',
    )
    assert not result.allowed


def test_sensitive_registry_uses_only_authoritative_evaluator_and_transaction():
    from pathlib import Path

    source = (Path(__file__).resolve().parents[2] / 'app/secrets_pki/scoped_registry.py').read_text(encoding='utf-8')
    assert 'def read_governed_scoped_secret_registry(' in source
    assert 'evaluate_exact_vault_scope(' in source
    assert 'lock_for_read=True' in source
    assert 'stage_operational_activity(' in source
    assert 'db.session.commit()' in source
    assert 'db.session.rollback()' in source
