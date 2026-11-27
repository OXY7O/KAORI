"""HV-12: exact approved instance access and read-only Vault provider cases."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from flask import Flask
from werkzeug.datastructures import MultiDict
from werkzeug.exceptions import NotFound

from app.access.scope_policy import evaluate_exact_vault_instance_case_scope
from app.extensions.db import db
from app.intelligence.alert_intelligence import lifecycle, notifications, provider_case_scope
from app.intelligence.alert_intelligence import vault_case_workspace as workspace
from app.intelligence.alert_intelligence.application import apply_case_mutation
from app.intelligence.alert_signals.vault_source import commit_vault_alert_observations
from app.models.alert_ops import AlertCase, AlertCaseEvent, AlertSilence
from app.models.alert_signal import AlertSignalSnapshot
from app.models.audit import AuditEvent
from app.models.identity import ExternalIdentityLink, IdentityProvider
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
        Role.__table__,
        Permission.__table__,
        RolePermission.__table__,
        User.__table__,
        IdentityProvider.__table__,
        ExternalIdentityLink.__table__,
        IntegrationInstance.__table__,
        IntegrationBinding.__table__,
        ScopeAccessPolicy.__table__,
        ScopeAccessPolicyRevision.__table__,
        AlertCase.__table__,
        AlertCaseEvent.__table__,
        AuditEvent.__table__,
        AlertSilence.__table__,
        AlertSignalSnapshot.__table__,
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
        db.session.add_all([RolePermission(role_id=role.id, permission_id=item.id) for item in permissions])
        actor = User(username='viewer', email='viewer@example.invalid', role_id=role.id)
        requester = User(username='requester', email='requester@example.invalid')
        approver = User(username='approver', email='approver@example.invalid')
        vault = IntegrationInstance(
            integration_type='secrets_pki',
            provider_key='vault',
            adapter_key='test',
            name='Approved Vault',
            enabled=True,
            lifecycle_status='active',
        )
        other = IntegrationInstance(
            integration_type='secrets_pki',
            provider_key='vault',
            adapter_key='test',
            name='Other Vault',
            enabled=True,
            lifecycle_status='active',
        )
        source = IntegrationInstance(
            integration_type='alert_source',
            provider_key='alertmanager',
            adapter_key='test',
            name='Alert Source',
            enabled=True,
            lifecycle_status='active',
        )
        db.session.add_all([actor, requester, approver, vault, other, source])
        db.session.flush()
        binding = IntegrationBinding(
            integration_instance_id=source.id,
            asset_type='vault_instance',
            asset_key=str(vault.id),
            enabled=True,
            validation_profile='vault-alerts-v1',
            selector_json={
                'matchers': [
                    {'label': 'vault_instance', 'operator': '=', 'value': str(vault.id)},
                ],
            },
        )
        db.session.add(binding)
        db.session.commit()
        ids = SimpleNamespace(
            actor=actor.id,
            requester=requester.id,
            approver=approver.id,
            vault=vault.id,
            other=other.id,
            source=source.id,
            binding=binding.id,
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
    db.session.add(
        ScopeAccessPolicyRevision(
            policy_id=policy.id,
            revision_number=1,
            lifecycle_status=state,
            effective_from=at - timedelta(hours=1),
            effective_until=at + timedelta(hours=1),
            requested_by_user_id=ids.requester,
            approved_by_user_id=ids.approver if state == 'active' else None,
            approved_at=at - timedelta(minutes=5) if state == 'active' else None,
            change_reason='operational_access',
        )
    )
    db.session.commit()
    return policy


def _case(ids, *, vault_id=None, key=None, foreign=False):
    case_key = key or 'vault-alert:' + 'a' * 64
    case = AlertCase(
        case_key=case_key,
        source_type='provider_alert',
        source_ref=case_key,
        domain='registry' if foreign else 'secrets_pki',
        asset_type='vault_instance',
        asset_key=str(ids.vault if vault_id is None else vault_id),
        asset_name='SHOULD-NOT-RENDER-PROVIDER-NAME',
        alert_name='SHOULD-NOT-RENDER-RAW-ALERT',
        severity='warning',
        source_state='firing',
        workflow_state='open',
        routing_state='suppressed',
        routing_override_reason='policy_ineligible',
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
    assert (
        evaluate_exact_vault_instance_case_scope(
            actor_user_id=ids.actor,
            instance_id=ids.vault,
            now=AT,
        ).status
        == 'deny'
    )
    _grant(ids, level='vault_mount')
    assert (
        evaluate_exact_vault_instance_case_scope(
            actor_user_id=ids.actor,
            instance_id=ids.vault,
            now=AT,
        ).status
        == 'deny'
    )
    _grant(ids)
    decision = evaluate_exact_vault_instance_case_scope(
        actor_user_id=ids.actor,
        instance_id=ids.vault,
        now=AT,
    )
    assert decision.allowed
    assert decision.instance_id == ids.vault
    assert decision.actor_id == ids.actor
    assert (
        evaluate_exact_vault_instance_case_scope(
            actor_user_id=ids.actor,
            instance_id=ids.other,
            now=AT,
        ).status
        == 'deny'
    )


def test_revoked_expired_or_ambiguous_instance_policy_denies(store):
    _app, ids = store
    grant = _grant(ids)
    current = ScopeAccessPolicyRevision.query.filter_by(policy_id=grant.id).one()
    current.lifecycle_status = 'revoked'
    db.session.commit()
    assert not evaluate_exact_vault_instance_case_scope(
        actor_user_id=ids.actor,
        instance_id=ids.vault,
        now=AT,
    ).allowed
    current.lifecycle_status = 'active'
    current.effective_until = AT - timedelta(minutes=1)
    db.session.commit()
    assert not evaluate_exact_vault_instance_case_scope(
        actor_user_id=ids.actor,
        instance_id=ids.vault,
        now=AT,
    ).allowed
    current.effective_until = AT + timedelta(hours=1)
    _grant(ids)
    assert (
        evaluate_exact_vault_instance_case_scope(
            actor_user_id=ids.actor,
            instance_id=ids.vault,
            now=AT,
        ).reason
        == 'ambiguous_scope'
    )


def test_global_superuser_without_role_is_not_scoped_implicitly(store):
    _app, ids = store
    actor = db.session.get(User, ids.actor)
    actor.is_super_admin = True
    actor.role_id = None
    db.session.commit()
    _grant(ids)
    assert not evaluate_exact_vault_instance_case_scope(
        actor_user_id=ids.actor,
        instance_id=ids.vault,
        now=AT,
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
    assert not any(
        value in repr(public)
        for value in (
            'SHOULD-NOT-RENDER',
            'vault-alert:',
            'source_binding_id',
            'a' * 64,
            'labels',
            'evidence_json',
        )
    )


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
        case.public_id,
        operation=lambda row: invoked.append(row.id),
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
        workspace,
        'stage_operational_activity',
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
    list_html = (root / 'app/templates/intelligence/partials/_vault_provider_cases.html').read_text(encoding='utf-8')
    detail_html = (root / 'app/templates/intelligence/partials/_vault_provider_case_details.html').read_text(
        encoding='utf-8'
    )
    assert 'components/page_hero.html' in list_html
    assert 'components/table_primitives.html' in list_html
    assert 'components/states/_blocked_state.html' in list_html
    assert 'vault_case_details' in list_html
    for forbidden in (
        'apply_case_mutation',
        'resume_routing',
        'source_ref',
        'evidence_json',
        'case.case_key',
        'case.labels_json',
    ):
        assert forbidden not in list_html + detail_html


def test_foreign_alertmanager_binding_profile_and_routing_fail_closed(store):
    _app, ids = store
    case = _case(ids)
    binding = db.session.get(IntegrationBinding, ids.binding)
    binding.validation_profile = 'unsafe-profile'
    db.session.commit()
    assert workspace._read_cases(instance_id=ids.vault, page='1')['status'] == 'unavailable'
    binding.validation_profile = 'vault-alerts-v1'
    case.routing_override_reason = None
    db.session.commit()
    assert workspace._read_cases(instance_id=ids.vault, page='1')['status'] == 'unavailable'


def test_full_pages_use_existing_kaori_app_layout():
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    for name in ('vault_provider_cases.html', 'vault_provider_case_details.html'):
        code = (root / 'app/templates/intelligence' / name).read_text(encoding='utf-8')
        assert '{% extends "layouts/app.html" %}' in code
        assert "{% include 'intelligence/partials/" in code


def test_case_audit_must_commit_after_case_query_not_before():
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    code = (root / 'app/intelligence/alert_intelligence/vault_case_workspace.py').read_text(encoding='utf-8')
    section = code.split('def _admit_read(', 1)[1].split('def _safe_case(', 1)[0]
    assert 'stage_operational_activity(' in section
    assert 'db.session.commit()' not in section
    page = code.split('def vault_cases_response(', 1)[1].split('def vault_case_details_response(', 1)[0]
    assert page.index('_read_cases(') < page.index('db.session.commit()')


def test_unverified_resolved_vault_case_blocks_list_and_direct_detail(store, monkeypatch):
    app, ids = store
    case = _case(ids)
    case.source_state = 'resolved'
    db.session.commit()
    assert workspace._read_cases(instance_id=ids.vault, page='1')['status'] == 'unavailable'
    _grant(ids)
    monkeypatch.setattr(workspace, 'current_user', SimpleNamespace(id=ids.actor))
    monkeypatch.setattr(workspace, 'stage_operational_activity', lambda **_kw: None)
    with app.test_request_context(f'/vault-cases/{case.public_id}/details?instance_id={ids.vault}'):
        with pytest.raises(NotFound):
            workspace.vault_case_details_response(case.public_id)


_DOMAIN_OPTIONS = [{'value': 'secrets_pki', 'label': 'Secrets & PKI'}]


def _central_args(ids, **extra):
    return MultiDict({'domain': 'secrets_pki', 'provider': 'vault', 'asset': str(ids.vault), 'tab': 'active', **extra})


def test_central_scope_lists_only_exact_authorized_instances(store, monkeypatch):
    _app, ids = store
    monkeypatch.setattr(provider_case_scope, 'current_user', SimpleNamespace(id=ids.actor))
    _grant(ids, level='vault_mount')
    assert provider_case_scope.provider_scope_context(_central_args(ids))['selected_asset_key'] == ''
    _grant(ids)
    scope = provider_case_scope.provider_scope_context(_central_args(ids))
    assert scope['selected_asset_key'] == str(ids.vault)
    assert scope['selected_provider'] == 'vault'
    assert [item['value'] for item in scope['assets']] == ['', str(ids.vault)]
    wrong = provider_case_scope.provider_scope_context(_central_args(ids, provider='openbao'))
    assert wrong['selected_asset_key'] == ''
    foreign = provider_case_scope.provider_scope_context(_central_args(ids, asset=str(ids.other)))
    assert foreign['selected_asset_key'] == ''


def test_central_registry_reuses_safe_projection_and_audited_read(store, monkeypatch):
    _app, ids = store
    _grant(ids)
    case = _case(ids)
    _case(ids, vault_id=ids.other, key='vault-alert:' + 'b' * 64)
    actor = SimpleNamespace(id=ids.actor)
    monkeypatch.setattr(provider_case_scope, 'current_user', actor)
    monkeypatch.setattr(workspace, 'current_user', actor)
    audits = []
    monkeypatch.setattr(workspace, 'stage_operational_activity', lambda **kw: audits.append(kw))
    payload = provider_case_scope.build_provider_case_payload(_central_args(ids), domain_options=_DOMAIN_OPTIONS)
    assert payload['provider_case_status'] == 'ready'
    assert payload['summary'] == {'active': 1, 'critical': 0, 'source_unknown': 1}
    assert payload['snapshot']['available'] is False
    assert payload['selected_case'] is None
    assert payload['active_pagination']['per_page'] == 5
    assert [row['public_id'] for row in payload['active_cases']] == [case.public_id]
    assert payload['active_cases'][0]['source_state_label'] == 'Source unknown'
    assert 'SHOULD-NOT-RENDER' not in repr(payload)
    assert 'source_binding_id' not in repr(payload)
    assert audits[0]['metadata']['integration_instance_id'] == ids.vault
    filtered = provider_case_scope.build_provider_case_payload(
        _central_args(ids, severity='critical'), domain_options=_DOMAIN_OPTIONS
    )
    assert filtered['active_cases'] == []
    assert filtered['summary']['active'] == 1


def test_central_scope_and_audit_failure_never_project_case_or_healthy_zero(store, monkeypatch):
    _app, ids = store
    _grant(ids)
    _case(ids)
    actor = SimpleNamespace(id=ids.actor)
    monkeypatch.setattr(provider_case_scope, 'current_user', actor)
    monkeypatch.setattr(workspace, 'current_user', actor)
    monkeypatch.setattr(
        workspace,
        'stage_operational_activity',
        lambda **_kw: (_ for _ in ()).throw(RuntimeError('audit-store-offline')),
    )
    payload = provider_case_scope.build_provider_case_payload(_central_args(ids), domain_options=_DOMAIN_OPTIONS)
    assert payload['provider_case_status'] != 'ready'
    assert payload['active_cases'] == []
    assert payload['summary']['active'] is None
    foreign = provider_case_scope.build_provider_case_payload(
        _central_args(ids, asset=str(ids.other)), domain_options=_DOMAIN_OPTIONS
    )
    assert foreign['active_cases'] == []
    assert foreign['summary']['active'] is None


def test_central_case_detail_checks_instance_and_uses_read_only_projection(store, monkeypatch):
    _app, ids = store
    _grant(ids)
    case = _case(ids)
    actor = SimpleNamespace(id=ids.actor)
    monkeypatch.setattr(provider_case_scope, 'current_user', actor)
    monkeypatch.setattr(workspace, 'current_user', actor)
    monkeypatch.setattr(workspace, 'stage_operational_activity', lambda **_kw: None)
    monkeypatch.setattr(workspace, 'render_template', lambda _template, **kw: kw)
    result = provider_case_scope.provider_case_detail_response(_central_args(ids), case.public_id)
    assert result['central_provider_scope'] is True
    assert result['case']['public_id'] == case.public_id
    assert 'SHOULD-NOT-RENDER' not in repr(result)
    with pytest.raises(NotFound):
        provider_case_scope.provider_case_detail_response(_central_args(ids, asset=str(ids.other)), case.public_id)
    with pytest.raises(NotFound):
        provider_case_scope.provider_case_detail_response(_central_args(ids, provider='openbao'), case.public_id)


def test_generic_mutation_denies_provider_origin_outside_vault(store):
    _app, ids = store
    case = _case(ids, foreign=True)
    invoked = []
    assert apply_case_mutation(case.public_id, operation=lambda row: invoked.append(row.id)) is None
    assert not invoked


def _commit_current_observation(ids, *, state='active', offset=0, empty=False):
    binding = db.session.get(IntegrationBinding, ids.binding)
    binding.validation_status = 'ready'
    binding.last_validated_at = AT
    binding.validation_evidence = {'profile_key': 'vault-alerts-v1', 'vault_alert_sample': {'status': 'qualified'}}
    db.session.commit()
    raw = {
        'labels': {'vault_instance': str(ids.vault), 'severity': 'warning'},
        'status': {'state': state},
        'fingerprint': 'aabbccddeeff1234',
        'startsAt': (AT - timedelta(hours=1)).isoformat(),
    }
    result = commit_vault_alert_observations(
        binding_id=ids.binding,
        alerts=[] if empty else [raw],
        hmac_key=bytes.fromhex('ab' * 32),
        now=AT + timedelta(seconds=offset),
    )
    assert result['state'] == ('unobserved' if empty else 'qualified')
    row = AlertSignalSnapshot.query.one()
    return None if empty else 'vault-alert:' + row.payload_json['entries'][0]['handle']


def test_current_observation_matches_only_exact_admitted_occurrence(store):
    _app, ids = store
    key = _commit_current_observation(ids)
    matched = _case(ids, key=key)
    other = _case(ids, key='vault-alert:' + 'f' * 64)
    result = workspace._read_cases(instance_id=ids.vault, page='1', filters={})
    by_id = {row['public_id']: row for row in result['rows']}
    assert by_id[matched.public_id]['source_state'] == 'firing'
    assert by_id[other.public_id]['source_state'] == 'unknown'
    assert by_id[other.public_id]['last_admitted_source_state'] == 'firing'
    assert result['summary']['source_unknown'] == 1
    filtered = workspace._read_cases(instance_id=ids.vault, page='1', filters={'source_state': 'unknown'})
    assert [row['public_id'] for row in filtered['rows']] == [other.public_id]
    assert matched.source_state == other.source_state == 'firing'


@pytest.mark.parametrize('condition', ['empty', 'suppressed', 'unprocessed', 'stale', 'failed', 'disabled'])
def test_unverified_current_source_does_not_resolve_admitted_case(store, condition):
    _app, ids = store
    key = _commit_current_observation(ids, state=condition if condition in {'suppressed', 'unprocessed'} else 'active')
    case = _case(ids, key=key)
    snapshot = AlertSignalSnapshot.query.one()
    if condition == 'empty':
        _commit_current_observation(ids, offset=1, empty=True)
    elif condition == 'stale':
        snapshot.generated_at = AT - timedelta(minutes=6)
        snapshot.expires_at = AT - timedelta(minutes=1)
    elif condition == 'failed':
        snapshot.status = 'failed'
        snapshot.payload_json = None
    elif condition == 'disabled':
        db.session.get(IntegrationInstance, ids.source).enabled = False
    db.session.commit()
    result = workspace._read_cases(instance_id=ids.vault, page='1', filters={})
    assert result['status'] == 'ready'
    assert result['rows'][0]['source_state'] == 'unknown'
    assert result['rows'][0]['last_admitted_source_state'] == 'firing'
    assert result['summary']['source_unknown'] == 1
    assert case.source_state == 'firing'
    assert case.workflow_state == 'open'


def test_admitted_unknown_requires_qualified_state_reason_and_order(store):
    _app, ids = store
    case = _case(ids)
    case.source_state = 'unknown'
    case.source_state_reason = 'provider_observation_unverified'
    case.source_state_changed_at = case.last_seen_at + timedelta(seconds=1)
    db.session.commit()
    result = workspace._read_cases(instance_id=ids.vault, page='1', filters={})
    assert result['status'] == 'ready'
    assert result['rows'][0]['last_admitted_source_state'] == 'unknown'
    case.source_state_reason = 'unqualified'
    db.session.commit()
    assert workspace._read_cases(instance_id=ids.vault, page='1')['status'] == 'unavailable'


@pytest.mark.parametrize(
    'operation',
    [
        lambda case: lifecycle.acknowledge_case(case, actor_user_id=1),
        lambda case: lifecycle.assign_case(case, owner_user_id=1, actor_user_id=1),
        lambda case: lifecycle.mark_mitigating(case, actor_user_id=1),
        lambda case: lifecycle.create_delivery_silence(case, duration_minutes=60, reason='test', actor_user_id=1),
        lambda case: lifecycle.revoke_delivery_silence(case, actor_user_id=1),
        lambda case: lifecycle.close_case(
            case,
            resolution_summary='test',
            remediation_steps=['test'],
            verification_evidence='test',
            change_reference=None,
            ticket_reference=None,
            actor_user_id=1,
        ),
        lambda case: lifecycle.save_postmortem(case, payload={}, complete=False, actor_user_id=1),
        lambda case: lifecycle.mark_case_source_resolved(case, source_summary='unqualified'),
    ],
)
def test_generic_lifecycle_helpers_cannot_bypass_provider_action_qualification(store, operation):
    _app, ids = store
    _grant(ids)
    case = _case(ids)
    with pytest.raises(ValueError, match='Provider case lifecycle action is not qualified'):
        operation(case)
    assert case.workflow_state == 'open'
    assert case.source_state == 'firing'
    assert case.routing_state == 'suppressed'
    assert not db.session.new
    assert not db.session.dirty


def test_provider_delivery_transport_and_dispatch_helpers_fail_closed(store, monkeypatch):
    _app, ids = store
    case = _case(ids)
    monkeypatch.setattr(notifications, 'render_case_message', lambda *a, **kw: pytest.fail('Unexpected render'))
    monkeypatch.setattr(notifications, 'dispatch_notification_event', lambda **kw: pytest.fail('Unexpected delivery'))
    expected = {'firing': 0, 'resolved': 0, 'failed': 0, 'skipped': 1}
    assert notifications._dispatch_firing(case) == expected
    assert notifications._dispatch_resolved(case) == expected
    for state in ('firing', 'resolved'):
        assert notifications._deliver_case_event(
            case, channel_id=1, event_state=state, sequence='test'
        ) == {'successful': 0, 'failed': 0, 'skipped': 1}
    assert case.last_firing_notified_at is None
    assert case.last_resolved_notified_at is None


def test_expired_provider_silence_cannot_generate_notification(store, monkeypatch):
    _app, ids = store
    case = _case(ids)
    db.session.add(
        AlertSilence(
            case_id=case.id,
            starts_at=AT - timedelta(hours=2),
            ends_at=AT - timedelta(hours=1),
            reason='historical unqualified silence',
            created_by_user_id=ids.actor,
        )
    )
    db.session.commit()
    monkeypatch.setattr(lifecycle, 'create_notification', lambda **kw: pytest.fail('Unexpected notification'))
    assert lifecycle.expire_silences_and_notify() == 0
    assert AlertCaseEvent.query.count() == 0


@pytest.mark.parametrize('state', ['acknowledged', 'mitigating', 'verification_pending', 'closed'])
def test_unqualified_workflow_is_not_projected(store, state):
    _app, ids = store
    case = _case(ids)
    case.workflow_state = state
    if state in {'acknowledged', 'mitigating'}:
        case.acknowledged_at = AT
        case.acknowledged_by_user_id = ids.actor
    if state == 'mitigating':
        case.mitigating_at = AT
    db.session.commit()
    for filters in (None, {}):
        result = workspace._read_cases(instance_id=ids.vault, page='1', filters=filters)
        assert result['status'] == 'unavailable'
        assert result['rows'] == []
