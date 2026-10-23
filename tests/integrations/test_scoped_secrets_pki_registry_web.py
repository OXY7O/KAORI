"""HV-07 audited Secret Registry: HTTP surface never accepts Vault paths or implicit scope."""

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from flask import Flask
from werkzeug.exceptions import NotFound

from app.extensions.db import db
from app.models.identity import ExternalIdentityLink, IdentityProvider
from app.models.integration import IntegrationInstance
from app.models.rbac import Permission, Role, RolePermission
from app.models.scope_access import ScopeAccessPolicy, ScopeAccessPolicyRevision
from app.models.user import User
from app.secrets_pki import scoped_registry_web as web
from app.secrets_pki.scoped_registry import ScopedSecretPage, ScopedSecretRow


@pytest.fixture
def scope_db():
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY='test-only',
        SQLALCHEMY_DATABASE_URI='sqlite://',
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )
    db.init_app(app)
    with app.app_context():
        tables = [
            Role.__table__,
            Permission.__table__,
            RolePermission.__table__,
            User.__table__,
            IdentityProvider.__table__,
            ExternalIdentityLink.__table__,
            IntegrationInstance.__table__,
            ScopeAccessPolicy.__table__,
            ScopeAccessPolicyRevision.__table__,
        ]
        db.Model.metadata.create_all(bind=db.engine, tables=tables)
        role = Role(name='test_viewer', display_name='Registry Viewer', is_active=True)
        perm = Permission(key='secrets_pki.view', module='secrets_pki', action='view')
        db.session.add_all([role, perm])
        db.session.flush()
        actor = User(username='reader', email='reader@example.invalid', role_id=role.id)
        foreign = User(username='foreign', email='foreign@example.invalid', role_id=role.id)
        source = IntegrationInstance(
            integration_type='secrets_pki',
            provider_key='vault', adapter_key='test',
            name='Vault Secret Source', enabled=True, lifecycle_status='active',
        )
        other = IntegrationInstance(
            integration_type='secrets_pki',
            provider_key='vault', adapter_key='test',
            name='Foreign Vault Source', enabled=True, lifecycle_status='active',
        )
        db.session.add_all([actor, foreign, source, other])
        db.session.flush()
        policy = ScopeAccessPolicy(
            id=str(uuid4()),
            principal_user_id=actor.id,
            permission_key='secrets_pki.view',
            integration_instance_id=source.id,
            scope_level='vault_mount',
            provider_namespace='private-namespace',
            mount='sensitive/kv',
            current_revision=1,
        )
        db.session.add(policy)
        db.session.commit()
        ids = SimpleNamespace(
            actor=actor.id, foreign=foreign.id,
            instance=source.id, other=other.id,
            policy=policy.id,
        )
        try:
            yield app, ids
        finally:
            db.session.remove()
            db.Model.metadata.drop_all(bind=db.engine, tables=list(reversed(tables)))


def test_policy_ref_is_canonical_and_instance_numeric():
    assert web._canonical_positive('1') == 1
    assert web._canonical_positive('001') is None
    assert web._canonical_positive('0') is None
    assert web._canonical_positive('1/secret') is None
    assert web._canonical_positive('1' * 11) is None
    identity = str(uuid4())
    assert web._canonical_uuid(identity) == identity
    assert web._canonical_uuid(identity.upper()) is None
    assert web._canonical_uuid('secret/kv/mount') is None


def test_resolve_only_exact_actor_instance_mount_policy(scope_db):
    _app, ids = scope_db
    assert web._resolve_scope(
        actor_id=ids.actor, instance_id=ids.instance, policy_ref=ids.policy,
    ) == ('private-namespace', 'sensitive/kv')
    assert web._resolve_scope(
        actor_id=ids.foreign, instance_id=ids.instance, policy_ref=ids.policy,
    ) is None
    assert web._resolve_scope(
        actor_id=ids.actor, instance_id=ids.other, policy_ref=ids.policy,
    ) is None
    assert web._resolve_scope(
        actor_id=ids.actor, instance_id=ids.instance, policy_ref=str(uuid4()),
    ) is None


def test_unselected_route_never_queries_scope_or_secret_rows(scope_db, monkeypatch):
    app, ids = scope_db
    monkeypatch.setattr(web, 'current_user', SimpleNamespace(id=ids.actor))
    monkeypatch.setattr(
        web, '_resolve_scope',
        lambda **_kw: pytest.fail('Unselected route must not inspect private grants'),
    )
    monkeypatch.setattr(
        web, 'read_governed_scoped_secret_registry',
        lambda **_kw: pytest.fail('Unselected route must not inspect Secret metadata'),
    )
    monkeypatch.setattr(web, 'render_template', lambda _name, **kw: kw)
    with app.test_request_context('/secrets-pki/registry'):
        answer = web.scoped_registry_response()
    assert answer['registry'] is None
    assert answer['scope_ref'] is None


@pytest.mark.parametrize('params', [
    'instance_id=1&scope_ref=secret/kv',
    'instance_id=1',
    'scope_ref=missing',
    'instance_id=0&scope_ref=example',
    'instance_id=01&scope_ref=example',
    'instance_id=2&scope_ref=example&page=0',
    'instance_id=2&scope_ref=example&page=41',
])
def test_invalid_target_never_calls_source_reader(scope_db, monkeypatch, params):
    app, ids = scope_db
    monkeypatch.setattr(web, 'current_user', SimpleNamespace(id=ids.actor))
    monkeypatch.setattr(
        web, 'read_governed_scoped_secret_registry',
        lambda **_kw: pytest.fail('Invalid target must not read source'),
    )
    with app.test_request_context('/secrets-pki/registry?' + params):
        with pytest.raises(NotFound):
            web.scoped_registry_response()


def test_granted_route_passes_server_only_mount_into_governed_reader(scope_db, monkeypatch):
    app, ids = scope_db
    called = []
    observed = datetime(2026, 10, 23, 10, tzinfo=UTC)
    safe_id = str(uuid4())
    approved = ScopedSecretPage(
        status='ready', total_items=1, page=1, per_page=5,
        rows=(ScopedSecretRow(
            secret_identity_id=safe_id,
            current_version=3,
            observed_version_count=2,
            logical_lifecycle='discovered',
            cas_required=True,
            last_observed_at=observed,
        ),),
    )
    monkeypatch.setattr(web, 'current_user', SimpleNamespace(id=ids.actor))
    monkeypatch.setattr(
        web, 'read_governed_scoped_secret_registry',
        lambda **kw: (called.append(kw) or approved),
    )
    monkeypatch.setattr(web, 'render_template', lambda _name, **kw: kw)
    with app.test_request_context(
        f'/secrets-pki/registry?instance_id={ids.instance}&scope_ref={ids.policy}'
    ):
        result = web.scoped_registry_response()
    assert result['registry'] == approved
    assert called[0]['actor_id'] == ids.actor
    assert called[0]['instance_id'] == ids.instance
    assert called[0]['provider_namespace'] == 'private-namespace'
    assert called[0]['mount'] == 'sensitive/kv'
    assert called[0]['per_page'] == 5
    assert result.keys() == {'instance_id', 'scope_ref', 'registry'}
    assert 'sensitive/kv' not in repr(result)
    assert 'private-namespace' not in repr(result)


def test_denied_governed_read_never_renders_secret_data(scope_db, monkeypatch):
    app, ids = scope_db
    monkeypatch.setattr(web, 'current_user', SimpleNamespace(id=ids.actor))
    monkeypatch.setattr(
        web, 'read_governed_scoped_secret_registry',
        lambda **_kw: ScopedSecretPage(
            status='scope_required', total_items=None, page=1, per_page=5, rows=(),
        ),
    )
    monkeypatch.setattr(
        web, 'render_template',
        lambda _name, **_kw: pytest.fail('Denied source must not render rows'),
    )
    with app.test_request_context(
        f'/secrets-pki/registry?instance_id={ids.instance}&scope_ref={ids.policy}'
    ):
        with pytest.raises(NotFound):
            web.scoped_registry_response()


def test_policy_ownership_is_a_precondition_not_a_grant(scope_db, monkeypatch):
    app, ids = scope_db
    monkeypatch.setattr(web, 'current_user', SimpleNamespace(id=ids.foreign))
    monkeypatch.setattr(
        web, 'read_governed_scoped_secret_registry',
        lambda **_kw: pytest.fail('Wrong actor must never reach governed reader'),
    )
    with app.test_request_context(
        f'/secrets-pki/registry?instance_id={ids.instance}&scope_ref={ids.policy}'
    ):
        with pytest.raises(NotFound):
            web.scoped_registry_response()


def test_template_hides_namespace_path_and_uses_reusable_violet_table():
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    html = (root / 'app/templates/secrets_pki/scoped_registry.html').read_text('utf-8')
    assert 'layouts/app.html' in html
    assert 'components/table_primitives.html' in html
    assert 'components/states/_blocked_state.html' in html
    assert 'item.secret_identity_id' in html
    assert 'item.logical_lifecycle' in html
    assert 'registry.total_pages' in html
    for unsafe in (
        'item.path', 'item.mount', 'item.namespace', 'item.name',
        'item.value', 'item.token', 'item.path_sha256', 'item.secret_id }}',
    ):
        assert unsafe not in html
    assert 'name="mount"' not in html
    assert 'name="provider_namespace"' not in html
