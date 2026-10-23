"""HV-12: exact approved instance access and read-only Vault provider cases."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from flask import Flask
from werkzeug.exceptions import NotFound

from app.access.scope_policy import evaluate_exact_vault_instance_case_scope
from app.extensions.db import db
from app.intelligence.alert_intelligence import vault_case_workspace as workspace
from app.intelligence.alert_intelligence.application import apply_case_mutation
from app.models.alert_ops import AlertCase
from app.models.integration import IntegrationBinding, IntegrationInstance
from app.models.rbac import Permission, Role, RolePermission
from app.models.scope_access import ScopeAccessPolicy, ScopeAccessPolicyRevision
from app.models.user import User

AT = datetime.now(UTC)


@pytest.fixture
def store():
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY='test-only',
        SQLALCHEMY_DATABASE_URI='sqlite://',
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )
    db.init_app(app)
    tables = [
        Role.__table__, Permission.__table__, RolePermission.__table__,
        User.__table__, IntegrationInstance.__table__, IntegrationBinding.__table__,
        ScopeAccessPolicy.__table__, ScopeAccessPolicyRevision.__table__, AlertCase.__table__,
    ]
    with app.app_context():
        db.Model.metadata.create_all(bind=db.engine, tables=tables)
        permissions = [
            Permission(key='secrets_pki.view', module='secrets_pki', action='view'),
            Permission(key='intelligence.view', module='intelligence', action='view'),
        ]
        role = Role(name='vault_case_viewer', display_name='Vault Case Viewer', is_active=True)
        db.session.add_all([role, *permissions])
        db.session.flush()
        db.session.add_all([
            RolePermission(role_id=role.id, permission_id=item.id) for item in permissions
        ])
        actor = User(username='viewer', email='viewer@example.invalid', role_id=role.id)
        requester = User(username='requester', email='requester@example.invalid')
        approver = User(username='approver', email='approver@example.invalid')
        vault = IntegrationInstance(
            integration_type='secrets_pki', provider_key='vault', adapter_key='test',
            name='Approved Vault', enabled=True, lifecycle_status='active',
        )
        other = IntegrationInstance(
            integration_type='secrets_pki', provider_key='vault', adapter_key='test',
            name='Other Vault', enabled=True, lifecycle_status='active',
        )
        source = IntegrationInstance(
            integration_type='alert_source', provider_key='alertmanager', adapter_key='test',
            name='Alert Source', enabled=True, lifecycle_status='active',
        )
        db.session.add_all([actor, requester, approver, vault, other, source])
        db.session.flush()
        binding = IntegrationBinding(
            integration_instance_id=source.id, asset_type='vault_instance',
            asset_key=str(vault.id), enabled=True,
        )
        db.session.add(binding)
        db.session.commit()
        ids = SimpleNamespace(
            actor=actor.id, requester=requester.id, approver=approver.id,
            vault=vault.id, other=other.id, source=source.id, binding=binding.id,
        )
        try:
            yield app, ids
        finally:
            db.session.remove()
            db.Model.metadata.drop_all(bind=db.engine, tables=list(reversed(tables)))


def _grant(ids, *, level='instance', at=AT, other=False, state='active'):
    policy = ScopeAccessPolicy(
        principal_user_id=ids.actor,
        permission_key='secrets_pki.view',
        integration_instance_id=ids.other if other else ids.vault,
        scope_level=level,
        provider_namespace='' if level == 'vault_mount' else None,
        mount='kv' if level == 'vault_mount' else None,
        current_revision=1,
    )
    db.session.add(policy)
    db.session.flush()
    db.session.add(ScopeAccessPolicyRevision(
        policy_id=policy.id, revision_number=1, lifecycle_status=state,
        effective_from=at - timedelta(hours=1),
        effective_until=at + timedelta(hours=1),
        requested_by_user_id=ids.requester,
        approved_by_user_id=ids.approver if state == 'active' else None,
        approved_at=at - timedelta(minutes=5) if state == 'active' else None,
        change_reason='operational_access',
    ))
    db.session.commit()
    return policy


def _case(ids, *, vault_id=None, key=None, foreign=False):
    case_key = key or 'vault-alert:' + 'a' * 64
    case = AlertCase(
        case_key=case_key,
        source_type='provider_alert', source_ref=case_key,
        domain='registry' if foreign else 'secrets_pki',
        asset_type='vault_instance',
        asset_key=str(ids.vault if vault_id is None else vault_id),
        asset_name='SHOULD-NOT-RENDER-PROVIDER-NAME',
        alert_name='SHOULD-NOT-RENDER-RAW-ALERT',
        severity='warning', source_state='firing', workflow_state='open',
        routing_state='suppressed',
        labels_json={},
        evidence_json={
            'correlation_profile': 'vault-alert-hmac-v1',
            'source_binding_id': ids.binding,
            'source_integration_id': ids.source,
        },
    )
    db.session.add(case)
    db.session.commit()
    return case


def test_explicit_active_instance_grant_admits_without_mount_inheritance(store):
    _app, ids = store
    assert evaluate_exact_vault_instance_case_scope(
        actor_user_id=ids.actor, instance_id=ids.vault, now=AT,
    ).status == 'deny'
    _grant(ids, level='vault_mount')
    assert evaluate_exact_vault_instance_case_scope(
        actor_user_id=ids.actor, instance_id=ids.vault, now=AT,
    ).status == 'deny'
    _grant(ids)
    decision = evaluate_exact_vault_instance_case_scope(
        actor_user_id=ids.actor, instance_id=ids.vault, now=AT,
    )
    assert decision.allowed
    assert decision.instance_id == ids.vault
    assert decision.actor_id == ids.actor
    assert evaluate_exact_vault_instance_case_scope(
        actor_user_id=ids.actor, instance_id=ids.other, now=AT,
    ).status == 'deny'


def test_revoked_expired_or_ambiguous_instance_policy_denies(store):
    _app, ids = store
    grant = _grant(ids)
    current = ScopeAccessPolicyRevision.query.filter_by(policy_id=grant.id).one()
    current.lifecycle_status = 'revoked'
    db.session.commit()
    assert not evaluate_exact_vault_instance_case_scope(
        actor_user_id=ids.actor, instance_id=ids.vault, now=AT,
    ).allowed
    current.lifecycle_status = 'active'
    current.effective_until = AT - timedelta(minutes=1)
    db.session.commit()
    assert not evaluate_exact_vault_instance_case_scope(
        actor_user_id=ids.actor, instance_id=ids.vault, now=AT,
    ).allowed
    current.effective_until = AT + timedelta(hours=1)
    _grant(ids)
    assert evaluate_exact_vault_instance_case_scope(
        actor_user_id=ids.actor, instance_id=ids.vault, now=AT,
    ).reason == 'ambiguous_scope'


def test_global_superuser_without_role_is_not_scoped_implicitly(store):
    _app, ids = store
    actor = db.session.get(User, ids.actor)
    actor.is_super_admin = True
    actor.role_id = None
    db.session.commit()
    _grant(ids)
    assert not evaluate_exact_vault_instance_case_scope(
        actor_user_id=ids.actor, instance_id=ids.vault, now=AT,
    ).allowed


def test_case_projection_is_strictly_safe_and_source_qualified(store):
    _app, ids = store
    case = _case(ids)
    result = workspace._read_cases(instance_id=ids.vault, page='1')
    assert result['status'] == 'ready'
    assert result['pagination']['per_page'] == 5
    assert len(result['rows']) == 1
    public = result['rows'][0]
    assert public['public_id'] == case.public_id
    assert public['title'] == 'Vault Alertmanager source condition'
    assert not any(value in repr(public) for value in (
        'SHOULD-NOT-RENDER', 'vault-alert:', 'source_binding_id',
        'a' * 64, 'labels', 'evidence_json',
    ))


def test_one_bad_case_blocks_entire_source_population(store):
    _app, ids = store
    _case(ids)
    another = _case(ids, key='vault-alert:' + 'b' * 64)
    another.labels_json = {'kv_path': 'SECRET/MOUNT/PATH'}
    db.session.commit()
    result = workspace._read_cases(instance_id=ids.vault, page='1')
    assert result['status'] == 'unavailable'
    assert result['rows'] == []


def test_scoped_case_query_never_returns_other_vault_or_domain(store):
    _app, ids = store
    good = _case(ids)
    _case(ids, vault_id=ids.other, key='vault-alert:' + 'b' * 64)
    _case(ids, foreign=True, key='vault-alert:' + 'c' * 64)
    page = workspace._read_cases(instance_id=ids.vault, page='1')
    assert page['status'] == 'ready'
    assert [row['public_id'] for row in page['rows']] == [good.public_id]


def test_existing_generic_mutation_api_denies_vault_case_by_public_id(store):
    _app, ids = store
    case = _case(ids)
    invoked = []
    output = apply_case_mutation(
        case.public_id, operation=lambda row: invoked.append(row.id),
    )
    assert output is None
    assert not invoked
    assert AlertCase.query.one().source_state == 'firing'


def test_read_route_fails_closed_without_exact_scope_and_hides_guessed_case(store, monkeypatch):
    app, ids = store
    case = _case(ids)
    monkeypatch.setattr(workspace, 'current_user', SimpleNamespace(id=ids.actor))
    with app.test_request_context(f'/vault-cases/{case.public_id}/details?instance_id={ids.vault}'):
        with pytest.raises(NotFound):
            workspace.vault_case_details_response(case.public_id)
    _grant(ids)
    audits = []
    monkeypatch.setattr(workspace, 'stage_operational_activity', lambda **kw: audits.append(kw))
    monkeypatch.setattr(workspace, 'render_template', lambda _template, **kw: kw)
    with app.test_request_context(f'/vault-cases/{case.public_id}/details?instance_id={ids.vault}'):
        output = workspace.vault_case_details_response(case.public_id)
    assert output['case']['public_id'] == case.public_id
    assert audits[0]['event_type'] == 'vault_provider_case_read'
    assert audits[0]['metadata']['integration_instance_id'] == ids.vault
    with app.test_request_context(f'/vault-cases/{case.public_id}/details?instance_id={ids.other}'):
        with pytest.raises(NotFound):
            workspace.vault_case_details_response(case.public_id)


def test_audit_failure_blocks_case_projection(store, monkeypatch):
    app, ids = store
    _grant(ids)
    monkeypatch.setattr(workspace, 'current_user', SimpleNamespace(id=ids.actor))
    monkeypatch.setattr(
        workspace, 'stage_operational_activity',
        lambda **_kw: (_ for _ in ()).throw(RuntimeError('audit-store-offline')),
    )
    with app.test_request_context(f'/vault-cases?instance_id={ids.vault}'):
        with pytest.raises(NotFound):
            workspace.vault_cases_response()


def test_bounded_case_pagination_uses_default_five(store):
    _app, ids = store
    for index in range(6):
        _case(ids, key=f'vault-alert:{index + 1:064x}')
    first = workspace._read_cases(instance_id=ids.vault, page='1')
    second = workspace._read_cases(instance_id=ids.vault, page='2')
    assert len(first['rows']) == 5
    assert len(second['rows']) == 1
    assert first['pagination']['total_pages'] == 2


def test_unscoped_list_renders_only_form_without_case_reads(store, monkeypatch):
    app, _ids = store
    monkeypatch.setattr(workspace, '_admit_read', lambda *_a: pytest.fail('No ID, no scope read'))
    monkeypatch.setattr(workspace, 'render_template', lambda _template, **kw: kw)
    with app.test_request_context('/vault-cases'):
        response = workspace.vault_cases_response()
    assert response['page_data'] is None


def test_reuse_violet_components_no_provider_case_mutations_in_templates():
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    list_html = (
        root / 'app/templates/intelligence/partials/_vault_provider_cases.html'
    ).read_text(encoding='utf-8')
    detail_html = (
        root / 'app/templates/intelligence/partials/_vault_provider_case_details.html'
    ).read_text(encoding='utf-8')
    assert 'components/page_hero.html' in list_html
    assert 'components/table_primitives.html' in list_html
    assert 'components/states/_blocked_state.html' in list_html
    assert 'vault_case_details' in list_html
    for forbidden in ('apply_case_mutation', 'resume_routing', 'source_ref',
                      'evidence_json', 'case.case_key', 'case.labels_json'):
        assert forbidden not in list_html + detail_html
