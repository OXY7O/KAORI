"""HV-12 internal provider-origin Vault AlertCase opt-in and no-recovery contract."""

from datetime import UTC, datetime, timedelta

import pytest
from flask import Flask
from sqlalchemy.exc import SQLAlchemyError

from app.extensions.db import db
from app.intelligence.alert_intelligence import vault_provider_admission as admission
from app.intelligence.alert_signals.vault_source import commit_vault_alert_observations
from app.models.alert_ops import AlertCase, AlertCaseEvent
from app.models.alert_signal import AlertSignalSnapshot
from app.models.audit import AuditEvent
from app.models.identity import ExternalIdentityLink, IdentityProvider
from app.models.integration import IntegrationBinding, IntegrationInstance
from app.models.rbac import Permission, Role, RolePermission
from app.models.scope_access import ScopeAccessPolicy, ScopeAccessPolicyRevision
from app.models.user import User

AT = datetime(2026, 10, 23, 5, tzinfo=UTC)
KEY = b'fixture-only-provider-case-HMAC-32byte-minimum'


@pytest.fixture
def store():
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
            IntegrationBinding.__table__,
            AlertSignalSnapshot.__table__,
            AlertCase.__table__,
            AlertCaseEvent.__table__,
            AuditEvent.__table__,
        ]
        db.Model.metadata.create_all(bind=db.engine, tables=tables)
        role = Role(name='vault_alert_admission_operator', display_name='Vault Case Operator')
        keys = (
            'intelligence.decisions.create', 'intelligence.view',
            'secrets_pki.sync', 'secrets_pki.view',
        )
        permissions = [
            Permission(key=key, module=key.split('.')[0], action=key.split('.')[-1])
            for key in keys
        ]
        db.session.add_all([role, *permissions])
        db.session.flush()
        db.session.add_all([
            RolePermission(role_id=role.id, permission_id=permission.id)
            for permission in permissions
        ])
        db.session.commit()
        try:
            yield
        finally:
            db.session.remove()
            db.Model.metadata.drop_all(bind=db.engine, tables=list(reversed(tables)))


def _actor(*, approved=True):
    actor = User(
        username=f'actor-{User.query.count()}',
        email=f'actor-{User.query.count()}@example.invalid',
        auth_source='database',
        is_super_admin=False,
        role_id=(
            Role.query.filter_by(name='vault_alert_admission_operator').one().id
            if approved else None
        ),
        account_is_active=True,
    )
    db.session.add(actor)
    db.session.flush()
    return actor


def _source():
    vault = IntegrationInstance(
        integration_type='secrets_pki', provider_key='vault', adapter_key='test',
        name='Vault source', enabled=True, lifecycle_status='active',
    )
    source = IntegrationInstance(
        integration_type='alert_source', provider_key='alertmanager', adapter_key='test',
        name='Alertmanager source', enabled=True, lifecycle_status='active',
    )
    db.session.add_all([vault, source])
    db.session.flush()
    binding = IntegrationBinding(
        integration_instance_id=source.id, asset_type='vault_instance',
        asset_key=str(vault.id), enabled=True,
        validation_profile='vault-alerts-v1', validation_status='ready',
        selector_json={
            'matchers': [{'label': 'vault_instance', 'operator': '=', 'value': str(vault.id)}],
        },
        validation_evidence={
            'profile_key': 'vault-alerts-v1',
            'vault_alert_sample': {'status': 'qualified'},
        },
        last_validated_at=AT,
    )
    db.session.add(binding)
    db.session.commit()
    return vault, source, binding


def _alert(vault_id, *, severity='warning', fingerprint='aabbccddeeff1234'):
    return {
        'labels': {
            'vault_instance': str(vault_id), 'severity': severity,
            'alertname': 'SECRET/RAW/PATH',
        },
        'annotations': {'summary': 'private Vault paths'},
        'status': {'state': 'active'},
        'fingerprint': fingerprint,
        'startsAt': '2026-10-23T03:00:00Z',
        'generatorURL': 'https://private.example/vault-token',
    }


def _commit(binding, alerts, *, observed=AT):
    return commit_vault_alert_observations(
        binding_id=binding.id, alerts=alerts, hmac_key=KEY,
        observed_at=observed, now=observed,
    )


def _admit(binding, actor, *, at=AT):
    return admission.admit_vault_provider_cases(
        binding_id=binding.id, actor_user_id=actor.id, now=at,
    )




def _grant(vault, actor, *, level='instance', state='active', target_id=None, until=None):
    requester = _actor(approved=False)
    approver = _actor(approved=False)
    policy = ScopeAccessPolicy(
        principal_user_id=actor.id,
        permission_key='secrets_pki.view',
        integration_instance_id=target_id or vault.id,
        scope_level=level,
        provider_namespace='' if level == 'vault_mount' else None,
        mount='kv' if level == 'vault_mount' else None,
        current_revision=1,
    )
    db.session.add(policy)
    db.session.flush()
    db.session.add(ScopeAccessPolicyRevision(
        policy_id=policy.id,
        revision_number=1,
        lifecycle_status=state,
        effective_from=AT - timedelta(minutes=30),
        effective_until=until or (AT + timedelta(hours=1)),
        requested_by_user_id=requester.id,
        approved_by_user_id=approver.id if state == 'active' else None,
        approved_at=AT - timedelta(minutes=10) if state == 'active' else None,
        change_reason='operational_access',
    ))
    db.session.commit()
    return policy


@pytest.fixture
def scope(store, monkeypatch):
    vault, source, binding = _source()
    actor = _actor()
    db.session.commit()
    _grant(vault, actor)
    monkeypatch.setenv('KAORI_VAULT_PROVIDER_CASE_ADMISSION_ENABLED', 'true')
    return vault, source, binding, actor


def test_default_disabled_has_no_query_or_mutation(scope, monkeypatch):
    vault, _source, binding, actor = scope
    _commit(binding, [_alert(vault.id)])
    monkeypatch.delenv('KAORI_VAULT_PROVIDER_CASE_ADMISSION_ENABLED', raising=False)
    assert _admit(binding, actor)['status'] == 'disabled'
    assert AlertCase.query.count() == 0
    assert AuditEvent.query.count() == 0


def test_actor_needs_active_account_and_existing_permissions(scope):
    vault, _source, binding, _admin = scope
    _commit(binding, [_alert(vault.id)])
    denied = _actor(approved=False)
    db.session.commit()
    assert _admit(binding, denied)['status'] == 'forbidden'
    assert AlertCase.query.count() == 0
    denied.is_super_admin = True
    denied.account_is_active = False
    db.session.commit()
    assert _admit(binding, denied)['status'] == 'forbidden'


def test_first_firing_source_admits_suppressed_case_with_generic_evidence(scope):
    vault, source, binding, actor = scope
    _commit(binding, [_alert(vault.id)])
    out = _admit(binding, actor)
    assert out == {'status': 'committed', 'created': 1, 'refreshed': 0}
    case = AlertCase.query.one()
    assert case.source_type == 'provider_alert'
    assert case.domain == 'secrets_pki'
    assert case.asset_key == str(vault.id)
    assert case.case_key.startswith('vault-alert:')
    assert case.source_ref == case.case_key
    assert case.routing_state == 'suppressed'
    assert case.routing_override_reason == 'policy_ineligible'
    assert case.source_state == 'firing'
    assert case.workflow_state == 'open'
    assert case.labels_json == {}
    assert case.evidence_json == {
        'correlation_profile': 'vault-alert-hmac-v1',
        'source_binding_id': binding.id,
        'source_integration_id': source.id,
    }
    assert AlertCaseEvent.query.count() == 1
    assert AuditEvent.query.count() == 1
    for value in ('SECRET/RAW/PATH', 'aabbccddeeff1234', 'private Vault', 'vault-token'):
        assert value not in repr(case.__dict__) + repr(AuditEvent.query.one().metadata_json)


def test_same_source_generation_is_idempotent(scope):
    vault, _source, binding, actor = scope
    _commit(binding, [_alert(vault.id)])
    assert _admit(binding, actor)['created'] == 1
    assert _admit(binding, actor) == {'status': 'unchanged', 'created': 0, 'refreshed': 0}
    assert AlertCase.query.count() == 1
    assert AlertCaseEvent.query.count() == 1
    assert AuditEvent.query.count() == 1


def test_next_fresh_generation_refreshes_only_safe_case_fields(scope):
    vault, _source, binding, actor = scope
    _commit(binding, [_alert(vault.id)])
    _admit(binding, actor)
    initial = AlertCase.query.one()
    previous_id = initial.id
    later = AT + timedelta(minutes=1)
    _commit(binding, [_alert(vault.id, severity='critical')], observed=later)
    out = _admit(binding, actor, at=later)
    assert out == {'status': 'committed', 'created': 0, 'refreshed': 1}
    case = AlertCase.query.one()
    assert case.id == previous_id
    assert case.severity == 'critical'
    assert case.previous_severity == 'warning'
    assert case.workflow_state == 'open'
    assert case.routing_state == 'suppressed'
    assert AlertCaseEvent.query.count() == 2
    assert AuditEvent.query.count() == 2


@pytest.mark.parametrize('status', ['unobserved', 'disabled', 'expired', 'blocked'])
def test_invalid_observation_never_resolves_case(scope, status):
    vault, _source, binding, actor = scope
    _commit(binding, [_alert(vault.id)])
    _admit(binding, actor)
    at = AT + timedelta(minutes=1)
    if status == 'unobserved':
        _commit(binding, [], observed=at)
    elif status == 'disabled':
        binding.enabled = False
        db.session.commit()
    elif status == 'expired':
        at = AT + timedelta(minutes=6)
    else:
        AlertSignalSnapshot.query.one().status = 'failed'
        db.session.commit()
    out = _admit(binding, actor, at=at)
    assert out['created'] == 0 and out['refreshed'] == 0
    case = AlertCase.query.one()
    assert case.source_state == 'firing'
    assert case.workflow_state == 'open'
    assert AlertCaseEvent.query.count() == 1


def test_bounded_max_ten_new_cases_is_all_or_nothing(scope):
    vault, _source, binding, actor = scope
    alerts = [_alert(vault.id, fingerprint=f'{value:016x}') for value in range(11)]
    _commit(binding, alerts)
    assert _admit(binding, actor)['status'] == 'capacity_blocked'
    assert AlertCase.query.count() == 0
    assert AlertCaseEvent.query.count() == 0
    assert AuditEvent.query.count() == 0


def test_foreign_case_collision_blocks_atomic_admission(scope):
    vault, _source, binding, actor = scope
    _commit(binding, [_alert(vault.id)])
    from app.intelligence.alert_intelligence.vault_provider_plan import build_vault_provider_case_plan

    key = build_vault_provider_case_plan(binding_id=binding.id, now=AT)['candidates'][0]['case_key']
    foreign = AlertCase(
        case_key=key, source_type='provider_alert',
        source_ref=key, domain='object_storage', asset_type='storage',
        asset_key='foreign', asset_name='Foreign',
        alert_name='Other source', routing_state='suppressed',
    )
    db.session.add(foreign)
    db.session.commit()
    assert _admit(binding, actor)['status'] == 'unavailable'
    assert AlertCase.query.count() == 1
    assert AuditEvent.query.count() == 0


def test_db_error_rolls_back_full_case_batch(scope, monkeypatch):
    vault, _source, binding, actor = scope
    _commit(binding, [_alert(vault.id, fingerprint='0000000000000001'),
                      _alert(vault.id, fingerprint='0000000000000002')])
    original = admission._new_case
    attempts = []

    def interrupted(**kwargs):
        attempts.append(kwargs['case_key'])
        if len(attempts) == 2:
            raise SQLAlchemyError('simulation-only')
        return original(**kwargs)

    monkeypatch.setattr(admission, '_new_case', interrupted)
    assert _admit(binding, actor)['status'] == 'unavailable'
    assert AlertCase.query.count() == 0
    assert AlertCaseEvent.query.count() == 0
    assert AuditEvent.query.count() == 0


def test_wrong_key_source_suppress_or_closed_record_never_promotes(scope):
    vault, source, binding, actor = scope
    _commit(binding, [_alert(vault.id)])
    assert _admit(binding, actor)['created'] == 1
    case = AlertCase.query.one()
    case.workflow_state = 'closed'
    db.session.commit()
    assert _admit(binding, actor)['created'] == 0
    assert AlertCase.query.one().workflow_state == 'closed'
    assert AuditEvent.query.count() == 1


def test_no_http_celery_provider_io_or_delivery_activation():
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    code = (root / 'app/intelligence/alert_intelligence/vault_provider_admission.py').read_text(
        encoding='utf-8',
    )
    assert 'with_for_update()' in code
    assert "KAORI_VAULT_PROVIDER_CASE_ADMISSION_ENABLED" in code
    assert 'get_alerts(' not in code
    assert 'create_notification(' not in code
    assert 'mark_case_source_resolved(' not in code
    assert 'firing_routes(' not in code
    assert '@bp.' not in code


def test_operator_with_global_role_but_no_instance_grant_cannot_admit(scope):
    vault, _source, binding, _approved = scope
    _commit(binding, [_alert(vault.id)])
    other_actor = _actor()
    db.session.commit()
    assert _admit(binding, other_actor)['status'] == 'forbidden'
    assert AlertCase.query.count() == 0
    assert AlertCaseEvent.query.count() == 0
    assert AuditEvent.query.count() == 0


def test_superadmin_shortcut_cannot_bypass_role_or_grant(scope):
    vault, _source, binding, _approved = scope
    _commit(binding, [_alert(vault.id)])
    superadmin = _actor(approved=False)
    superadmin.is_super_admin = True
    db.session.commit()
    _grant(vault, superadmin)
    assert _admit(binding, superadmin)['status'] == 'forbidden'
    assert AlertCase.query.count() == 0


@pytest.mark.parametrize('scenario', ['mount_only', 'revoked', 'expired', 'foreign_source'])
def test_invalid_or_foreign_instance_grant_denies_all_case_writes(scope, scenario):
    vault, _source, binding, actor = scope
    _commit(binding, [_alert(vault.id)])
    policy = ScopeAccessPolicy.query.filter_by(principal_user_id=actor.id).one()
    current = ScopeAccessPolicyRevision.query.filter_by(policy_id=policy.id).one()
    if scenario == 'mount_only':
        policy.scope_level = 'vault_mount'
        policy.provider_namespace = ''
        policy.mount = 'kv'
    elif scenario == 'revoked':
        current.lifecycle_status = 'revoked'
    elif scenario == 'expired':
        current.effective_until = AT - timedelta(minutes=1)
    else:
        foreign = IntegrationInstance(
            integration_type='secrets_pki', provider_key='vault', adapter_key='test',
            name='Foreign Vault', enabled=True, lifecycle_status='active',
        )
        db.session.add(foreign)
        db.session.flush()
        policy.integration_instance_id = foreign.id
    db.session.commit()
    assert _admit(binding, actor)['status'] == 'forbidden'
    assert AlertCase.query.count() == 0
    assert AlertCaseEvent.query.count() == 0
    assert AuditEvent.query.count() == 0


def test_missing_normalized_mutation_permission_blocks_write_even_with_grant(scope):
    vault, _source, binding, actor = scope
    _commit(binding, [_alert(vault.id)])
    role = actor.role_record
    removed = next(
        edge for edge in RolePermission.query.filter_by(role_id=role.id).all()
        if edge.permission.key == 'secrets_pki.sync'
    )
    db.session.delete(removed)
    db.session.commit()
    db.session.expire_all()
    assert _admit(binding, actor)['status'] == 'forbidden'
    assert AlertCase.query.count() == 0


def test_ambiguous_parallel_instance_grants_block_case_creation(scope):
    vault, _source, binding, actor = scope
    _commit(binding, [_alert(vault.id)])
    _grant(vault, actor)
    assert _admit(binding, actor)['status'] == 'forbidden'
    assert AlertCase.query.count() == 0


def test_unapproved_source_denial_never_creates_case_even_if_snapshot_fresh(scope):
    vault, _source, binding, actor = scope
    _commit(binding, [_alert(vault.id)])
    binding.enabled = False
    db.session.commit()
    assert _admit(binding, actor)['created'] == 0
    assert AlertCase.query.count() == 0
