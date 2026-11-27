"""HV-12 internal provider-origin Vault AlertCase opt-in and no-recovery contract."""

from datetime import UTC, datetime, timedelta

import pytest
from flask import Flask
from sqlalchemy.exc import SQLAlchemyError

from app.extensions.db import db
from app.intelligence.alert_intelligence import vault_provider_admission as admission
from app.intelligence.alert_intelligence import vault_provider_operator as operator
from app.intelligence.alert_signals.vault_source import commit_vault_alert_observations
from app.models.alert_ops import AlertCase, AlertCaseEvent, AlertRoutingPolicy
from app.models.alert_signal import AlertSignalSnapshot
from app.models.audit import AuditEvent
from app.models.identity import ExternalIdentityLink, IdentityProvider
from app.models.integration import IntegrationBinding, IntegrationInstance
from app.models.notification import Notification
from app.models.notification_channel import NotificationChannel, NotificationDelivery
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
        INTEGRATION_CREDENTIAL_KEY='fixture-only-delivery-encryption-key',
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
            AlertRoutingPolicy.__table__,
            Notification.__table__,
            NotificationChannel.__table__,
            NotificationDelivery.__table__,
        ]
        db.Model.metadata.create_all(bind=db.engine, tables=tables)
        role = Role(name='vault_alert_admission_operator', display_name='Vault Case Operator')
        keys = (
            'integrations.manage',
            'intelligence.decisions.create',
            'intelligence.view',
            'secrets_pki.sync',
            'secrets_pki.view',
        )
        permissions = [Permission(key=key, module=key.split('.')[0], action=key.split('.')[-1]) for key in keys]
        db.session.add_all([role, *permissions])
        db.session.flush()
        db.session.add_all([RolePermission(role_id=role.id, permission_id=permission.id) for permission in permissions])
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
        role_id=(Role.query.filter_by(name='vault_alert_admission_operator').one().id if approved else None),
        account_is_active=True,
    )
    db.session.add(actor)
    db.session.flush()
    return actor


def _source():
    vault = IntegrationInstance(
        integration_type='secrets_pki',
        provider_key='vault',
        adapter_key='test',
        name='Vault source',
        enabled=True,
        lifecycle_status='active',
    )
    source = IntegrationInstance(
        integration_type='alert_source',
        provider_key='alertmanager',
        adapter_key='test',
        name='Alertmanager source',
        enabled=True,
        lifecycle_status='active',
    )
    db.session.add_all([vault, source])
    db.session.flush()
    binding = IntegrationBinding(
        integration_instance_id=source.id,
        asset_type='vault_instance',
        asset_key=str(vault.id),
        enabled=True,
        validation_profile='vault-alerts-v1',
        validation_status='ready',
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
            'vault_instance': str(vault_id),
            'severity': severity,
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
        binding_id=binding.id,
        alerts=alerts,
        hmac_key=KEY,
        observed_at=observed,
        now=observed,
    )


def _admit(binding, actor, *, at=AT):
    return admission.admit_vault_provider_cases(
        binding_id=binding.id,
        actor_user_id=actor.id,
        now=at,
    )


def _grant(
    vault, actor, *, level='instance', state='active', target_id=None, until=None, permission='secrets_pki.view'
):
    requester = _actor(approved=False)
    approver = _actor(approved=False)
    policy = ScopeAccessPolicy(
        principal_user_id=actor.id,
        permission_key=permission,
        integration_instance_id=target_id or vault.id,
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
            effective_from=AT - timedelta(minutes=30),
            effective_until=until or (AT + timedelta(hours=1)),
            requested_by_user_id=requester.id,
            approved_by_user_id=approver.id if state == 'active' else None,
            approved_at=AT - timedelta(minutes=10) if state == 'active' else None,
            change_reason='operational_access',
        )
    )
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


@pytest.mark.parametrize('status', ['disabled', 'expired', 'blocked'])
def test_invalid_observation_never_resolves_case(scope, status):
    vault, _source, binding, actor = scope
    _commit(binding, [_alert(vault.id)])
    _admit(binding, actor)
    at = AT + timedelta(minutes=1)
    if status == 'disabled':
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
        case_key=key,
        source_type='provider_alert',
        source_ref=key,
        domain='object_storage',
        asset_type='storage',
        asset_key='foreign',
        asset_name='Foreign',
        alert_name='Other source',
        routing_state='suppressed',
    )
    db.session.add(foreign)
    db.session.commit()
    assert _admit(binding, actor)['status'] == 'unavailable'
    assert AlertCase.query.count() == 1
    assert AuditEvent.query.count() == 0


def test_db_error_rolls_back_full_case_batch(scope, monkeypatch):
    vault, _source, binding, actor = scope
    _commit(
        binding, [_alert(vault.id, fingerprint='0000000000000001'), _alert(vault.id, fingerprint='0000000000000002')]
    )
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
    assert 'KAORI_VAULT_PROVIDER_CASE_ADMISSION_ENABLED' in code
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
            integration_type='secrets_pki',
            provider_key='vault',
            adapter_key='test',
            name='Foreign Vault',
            enabled=True,
            lifecycle_status='active',
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
        edge
        for edge in RolePermission.query.filter_by(role_id=role.id).all()
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


@pytest.mark.parametrize('condition', ['missing', 'suppressed', 'unprocessed'])
def test_fresh_unverified_occurrence_is_unknown_not_resolved(scope, condition):
    vault, _source, binding, actor = scope
    alert = _alert(vault.id)
    _commit(binding, [alert])
    _admit(binding, actor)
    case = AlertCase.query.one()
    first_seen = case.last_seen_at
    later = AT + timedelta(minutes=1)
    if condition == 'missing':
        rows = [_alert(vault.id, fingerprint='1111111111111111')]
    else:
        rows = [{**alert, 'status': {'state': condition}}]
    _commit(binding, rows, observed=later)
    outcome = _admit(binding, actor, at=later)
    assert outcome['status'] == 'committed'
    assert outcome['refreshed'] == 1
    assert case.source_state == 'unknown'
    assert case.source_state_reason == 'provider_observation_unverified'
    assert case.last_seen_at == first_seen
    assert case.source_resolved_at is None
    assert case.workflow_state == 'open'
    assert case.routing_state == 'suppressed'
    assert case.closed_at is None
    assert AlertCaseEvent.query.filter_by(event_type='provider_alert_source_unknown').count() == 1
    assert AuditEvent.query.filter_by(action='vault_provider_alert_source_unknown').count() == 1
    assert _admit(binding, actor, at=later)['status'] == 'unchanged'

    latest = AT + timedelta(minutes=2)
    _commit(binding, [alert], observed=latest)
    assert _admit(binding, actor, at=latest)['refreshed'] >= 1
    assert case.source_state == 'firing'
    assert case.source_state_reason is None
    assert case.source_resolved_at is None
    assert case.workflow_state == 'open'
    assert case.routing_state == 'suppressed'
    assert AlertCaseEvent.query.filter_by(case_id=case.id, event_type='provider_alert_observed').count() == 1


def test_unverified_state_change_is_not_admitted_without_scope(scope):
    vault, _source, binding, actor = scope
    alert = _alert(vault.id)
    _commit(binding, [alert])
    _admit(binding, actor)
    denied = _actor()
    db.session.commit()
    later = AT + timedelta(minutes=1)
    _commit(binding, [{**alert, 'status': {'state': 'suppressed'}}], observed=later)
    assert _admit(binding, denied, at=later)['status'] == 'forbidden'
    assert AlertCase.query.one().source_state == 'firing'
    assert AlertCaseEvent.query.count() == 1


def _operator_case(scope):
    vault, _source, binding, actor = scope
    _commit(binding, [_alert(vault.id)])
    assert _admit(binding, actor)['created'] == 1
    return AlertCase.query.one()


def _operate(scope, action, *, expected=None, owner=None, at=AT):
    vault, _source, binding, actor = scope
    case = AlertCase.query.one()
    return operator.apply_vault_provider_operator_action(
        binding_id=binding.id,
        instance_id=vault.id,
        public_id=case.public_id,
        actor_user_id=actor.id,
        action=action,
        expected_event_id=expected
        if expected is not None
        else AlertCaseEvent.query.order_by(AlertCaseEvent.id.desc()).first().id,
        owner_user_id=owner,
        now=at,
    )


def test_operator_action_requires_independent_decision_scope(scope):
    case = _operator_case(scope)
    assert _operate(scope, 'acknowledge') == 'forbidden'
    assert case.workflow_state == 'open'
    assert AlertCaseEvent.query.count() == AuditEvent.query.count() == 1


def test_operator_acknowledgement_and_mitigation_preserve_source_and_suppression(scope):
    vault, _source, _binding, actor = scope
    _operator_case(scope)
    _grant(vault, actor, permission='intelligence.decisions.create')
    previous = AlertCaseEvent.query.one().id
    assert _operate(scope, 'acknowledge', expected=previous) == 'committed'
    assert _operate(scope, 'acknowledge', expected=previous) == 'stale'
    assert _operate(scope, 'mitigating') == 'committed'
    case = AlertCase.query.one()
    assert case.workflow_state == 'mitigating'
    assert case.owner_user_id == actor.id
    assert case.acknowledgement_expires_at is None
    assert case.source_state == 'firing'
    assert case.source_resolved_at is None
    assert case.routing_state == 'suppressed'
    assert case.last_firing_notified_at is None
    assert AlertCaseEvent.query.count() == AuditEvent.query.count() == 3


def test_operator_assignment_requires_eligible_recipient(scope):
    vault, _source, _binding, actor = scope
    _operator_case(scope)
    _grant(vault, actor, permission='intelligence.decisions.create')
    recipient = _actor()
    db.session.commit()
    assert _operate(scope, 'assign', owner=recipient.id) == 'forbidden'
    _grant(vault, recipient)
    assert _operate(scope, 'assign', owner=recipient.id) == 'forbidden'
    _grant(vault, recipient, permission='intelligence.decisions.create')
    assert _operate(scope, 'assign', owner=recipient.id) == 'committed'
    assert _operate(scope, 'assign', owner=recipient.id) == 'unchanged'
    assert AlertCase.query.one().owner_user_id == recipient.id
    assert AlertCaseEvent.query.count() == AuditEvent.query.count() == 2


@pytest.mark.parametrize('condition', ['stale', 'empty', 'disabled', 'new_generation'])
def test_operator_does_not_mutate_unqualified_current_source(scope, condition):
    vault, _source, binding, actor = scope
    _operator_case(scope)
    _grant(vault, actor, permission='intelligence.decisions.create')
    at = AT + timedelta(minutes=1)
    if condition == 'stale':
        at = AT + timedelta(minutes=6)
    elif condition == 'empty':
        _commit(binding, [], observed=at)
    elif condition == 'disabled':
        binding.enabled = False
        db.session.commit()
    else:
        _commit(binding, [_alert(vault.id)], observed=at)
    assert _operate(scope, 'acknowledge', at=at) == 'unavailable'
    assert AlertCase.query.one().workflow_state == 'open'
    assert AlertCaseEvent.query.count() == AuditEvent.query.count() == 1


def test_operator_audit_failure_rolls_back_workflow(scope, monkeypatch):
    vault, _source, _binding, actor = scope
    _operator_case(scope)
    _grant(vault, actor, permission='intelligence.decisions.create')

    def fail(*_args, **_kwargs):
        raise SQLAlchemyError('audit failure')

    monkeypatch.setattr(operator, '_stage_evidence', fail)
    assert _operate(scope, 'acknowledge') == 'unavailable'
    assert AlertCase.query.one().workflow_state == 'open'
    assert AlertCaseEvent.query.count() == AuditEvent.query.count() == 1


def test_operator_command_default_disabled_and_unsupported_action(scope, monkeypatch):
    vault, _source, _binding, actor = scope
    _operator_case(scope)
    _grant(vault, actor, permission='intelligence.decisions.create')
    assert _operate(scope, 'resolve') == 'blocked'
    monkeypatch.delenv('KAORI_VAULT_PROVIDER_CASE_ADMISSION_ENABLED', raising=False)
    assert _operate(scope, 'acknowledge') == 'disabled'
    assert AlertCase.query.one().workflow_state == 'open'


def test_committed_operator_workflow_projection_survives_source_unknown(scope):
    from app.intelligence.alert_intelligence import vault_case_workspace as workspace

    vault, _source, binding, actor = scope
    _operator_case(scope)
    _grant(vault, actor, permission='intelligence.decisions.create')
    assert _operate(scope, 'acknowledge') == 'committed'
    assert _operate(scope, 'mitigating') == 'committed'
    _commit(binding, [], observed=AT + timedelta(minutes=1))
    case = AlertCase.query.one()
    assert workspace._case_qualified(case, instance_id=vault.id)
    row = workspace._safe_case(case, {binding.id: {'state': 'unobserved', 'entries': None}})
    assert row['workflow_state'] == 'mitigating'
    assert row['owner_label'] == 'Assigned'
    assert row['source_state'] == 'unknown'
    assert row['routing'] == 'Suppressed'
    assert 'owner_user_id' not in row


def test_operator_projection_rejects_missing_audit_and_unqualified_mutation(scope):
    vault, _source, _binding, actor = scope
    _operator_case(scope)
    _grant(vault, actor, permission='intelligence.decisions.create')
    assert _operate(scope, 'acknowledge') == 'committed'
    audit = AuditEvent.query.filter_by(action='vault_provider_case_acknowledge').one()
    db.session.delete(audit)
    db.session.commit()
    assert not operator.admitted_operator_workflow_qualified(AlertCase.query.one())
    assert _operate(scope, 'mitigating') == 'unavailable'


def test_web_operator_controls_disabled_independently(scope, monkeypatch):
    from app.intelligence.alert_intelligence import vault_operator_web as web

    vault, _source, _binding, actor = scope
    case = _operator_case(scope)
    _grant(vault, actor, permission='intelligence.decisions.create')
    monkeypatch.delenv(web._WEB_ENABLE_ENV, raising=False)
    assert not web._enabled()
    assert (
        web.operator_controls(
            instance_id=vault.id, public_id=case.public_id, expected_event_id=AlertCaseEvent.query.one().id
        )
        is None
    )


def test_web_mutation_rejects_missing_csrf_and_extra_fields(scope, monkeypatch):
    from flask import current_app
    from flask_wtf.csrf import generate_csrf
    from werkzeug.exceptions import BadRequest

    from app.intelligence.alert_intelligence import vault_operator_web as web

    vault, _source, _binding, actor = scope
    case = _operator_case(scope)
    _grant(vault, actor, permission='intelligence.decisions.create')
    monkeypatch.setenv(web._WEB_ENABLE_ENV, 'true')
    monkeypatch.setattr(web, 'current_user', actor)
    case_id = case.public_id
    with current_app.test_request_context(method='POST'):
        with pytest.raises(BadRequest):
            web.operator_action_response(case_id)
    with current_app.test_request_context(method='POST', data={'actor_user_id': actor.id}):
        from flask import request

        form = request.form.copy()
        form.update(
            {
                'csrf_token': generate_csrf(),
                'instance_id': str(vault.id),
                'expected_event_id': str(AlertCaseEvent.query.one().id),
                'action': 'acknowledge',
            }
        )
        monkeypatch.setattr(request._get_current_object(), 'form', form)
        with pytest.raises(BadRequest):
            web.operator_action_response(case_id)
    assert AlertCase.query.one().workflow_state == 'open'


def test_recipient_selector_uses_only_exact_operator_grants(scope):
    from app.intelligence.alert_intelligence import vault_operator_service as service

    vault, _source, _binding, actor = scope
    _grant(vault, actor, permission='intelligence.decisions.create')
    other = _actor()
    db.session.commit()
    _grant(vault, other, permission='intelligence.decisions.create')
    assert service._recipient_options(vault.id, now=AT) == [{'id': actor.id, 'label': actor.username}]
    db.session.rollback()


def test_operator_service_controls_require_current_event_and_committed_audit(scope, monkeypatch):
    from app.intelligence.alert_intelligence import vault_operator_service as service

    vault, _source, _binding, actor = scope
    case = _operator_case(scope)
    _grant(vault, actor, permission='intelligence.decisions.create')
    event_id = AlertCaseEvent.query.one().id
    params = {
        'instance_id': vault.id,
        'public_id': case.public_id,
        'actor_id': actor.id,
        'now': AT,
    }
    assert service.load_operator_controls(expected_event_id=event_id + 1, **params) is None
    assert Notification.query.count() == 0
    stage = service.stage_operational_activity

    def reject_audit(**kwargs):
        stage(**kwargs)
        db.session.flush()
        raise SQLAlchemyError('fixture audit failure')

    with monkeypatch.context() as patch:
        patch.setattr(service, 'stage_operational_activity', reject_audit)
        assert service.load_operator_controls(expected_event_id=event_id, **params) is None
    assert Notification.query.count() == 0
    controls = service.load_operator_controls(expected_event_id=event_id, **params)
    assert controls is not None
    assert controls['expected_event_id'] == event_id
    assert controls['acknowledge']
    assert controls['recipients'] == [{'id': actor.id, 'label': actor.username}]
    audit = Notification.query.one()
    assert audit.event_type == 'vault_provider_case_operator_controls_read'
    assert audit.user_id == actor.id
    assert AlertCase.query.one().workflow_state == 'open'
    monkeypatch.delenv(admission._ENABLE_ENV, raising=False)
    assert service.load_operator_controls(expected_event_id=event_id, **params) is None
    assert Notification.query.count() == 1


def test_operator_service_binding_selector_rejects_ambiguous_active_sources(scope):
    from app.intelligence.alert_intelligence import vault_operator_service as service

    vault, source, binding, _actor_user = scope
    instance_id, binding_id = vault.id, binding.id
    unrelated = IntegrationBinding(
        integration_instance_id=vault.id,
        asset_type='vault_instance',
        asset_key=str(instance_id),
        enabled=True,
    )
    db.session.add(unrelated)
    db.session.commit()
    assert service.resolve_operator_binding(instance_id) == binding_id
    second = IntegrationBinding(
        integration_instance_id=source.id,
        asset_type='vault_instance',
        asset_key=str(instance_id),
        binding_role='secondary',
        enabled=True,
    )
    db.session.add(second)
    db.session.commit()
    assert service.resolve_operator_binding(instance_id) is None


def test_web_adapter_passes_authenticated_actor_and_refreshes_only_after_commit(scope, monkeypatch):
    from flask import current_app, request
    from flask_wtf.csrf import generate_csrf

    from app.intelligence.alert_intelligence import vault_operator_web as web

    vault, _source, _binding, actor = scope
    case = _operator_case(scope)
    _grant(vault, actor, permission='intelligence.decisions.create')
    monkeypatch.setenv(web._WEB_ENABLE_ENV, 'true')
    monkeypatch.setattr(web, 'current_user', actor)
    monkeypatch.setattr(web, 'url_for', lambda *_args, **_kwargs: '/case-detail')
    feedback = []
    monkeypatch.setattr(web, 'create_transient_feedback', lambda **kwargs: feedback.append(kwargs))
    command = web.apply_vault_provider_operator_action
    monkeypatch.setattr(web, 'apply_vault_provider_operator_action', lambda **kwargs: command(**kwargs, now=AT))
    with current_app.test_request_context(method='POST', headers={'HX-Request': 'true'}):
        form = request.form.copy()
        form.update(
            {
                'csrf_token': generate_csrf(),
                'instance_id': str(vault.id),
                'expected_event_id': str(AlertCaseEvent.query.one().id),
                'action': 'acknowledge',
            }
        )
        monkeypatch.setattr(request._get_current_object(), 'form', form)
        response = web.operator_action_response(case.public_id)
        assert response.headers['HX-Redirect'] == '/case-detail'
    assert AlertCase.query.one().workflow_state == 'acknowledged'
    assert AlertCaseEvent.query.count() == AuditEvent.query.count() == 2
    assert feedback[0]['status'] == 'success'


def test_fresh_empty_generation_commits_unknown_without_resolving_or_erasing_workflow(scope):
    vault, _source, binding, actor = scope
    case = _operator_case(scope)
    _grant(vault, actor, permission='intelligence.decisions.create')
    assert _operate(scope, 'acknowledge') == 'committed'
    assert _operate(scope, 'mitigating') == 'committed'
    original_seen = case.last_seen_at
    later = AT + timedelta(minutes=1)
    _commit(binding, [], observed=later)
    assert _admit(binding, actor, at=later) == {'status': 'committed', 'created': 0, 'refreshed': 1}
    assert case.source_state == 'unknown'
    assert case.last_seen_at == original_seen
    assert case.source_resolved_at is None
    assert case.closed_at is None
    assert case.workflow_state == 'mitigating'
    assert case.owner_user_id == actor.id
    assert case.routing_state == 'suppressed'
    assert _admit(binding, actor, at=later)['status'] == 'unchanged'
    assert AlertCaseEvent.query.filter_by(event_type='provider_alert_source_unknown').count() == 1
    assert AuditEvent.query.filter_by(action='vault_provider_alert_source_unknown').count() == 1
    latest = AT + timedelta(minutes=2)
    _commit(binding, [_alert(vault.id)], observed=latest)
    assert _admit(binding, actor, at=latest)['refreshed'] == 1
    assert case.source_state == 'firing'
    assert case.workflow_state == 'mitigating'
    assert case.source_resolved_at is None


def test_empty_observation_cannot_create_case_or_mutate_without_scope(scope):
    vault, _source, binding, actor = scope
    _commit(binding, [])
    assert _admit(binding, actor)['created'] == 0
    assert AlertCase.query.count() == 0
    later = AT + timedelta(minutes=1)
    _commit(binding, [_alert(vault.id)], observed=later)
    assert _admit(binding, actor, at=later)['created'] == 1
    denied = _actor()
    db.session.commit()
    latest = AT + timedelta(minutes=2)
    _commit(binding, [], observed=latest)
    assert _admit(binding, denied, at=latest)['status'] == 'forbidden'
    assert AlertCase.query.one().source_state == 'firing'
    assert AlertCaseEvent.query.count() == AuditEvent.query.count() == 1


def _delivery_candidate(scope):
    vault, _source, binding, actor = scope
    case = _operator_case(scope)
    _grant(vault, actor, permission='intelligence.decisions.create')
    channel = NotificationChannel(
        name='Fixture Only',
        provider_key='email',
        enabled=True,
        lifecycle_state='active',
        credential_payload='fixture-only-credential',
        destination='fixture@example.invalid',
        test_status='success',
        last_tested_at=AT,
        domains=['secrets_pki'],
        event_types=['alert_ops.firing'],
        minimum_severity='warning',
    )
    db.session.add(channel)
    db.session.flush()
    policy = AlertRoutingPolicy(
        name='Fixture Only',
        enabled=True,
        domains_json=['secrets_pki'],
        source_types_json=['provider_alert'],
        matchers_json={'vault_instance': str(vault.id), 'source_binding_id': str(binding.id)},
        severities_json=['warning'],
        channel_ids_json=[channel.id],
        send_resolved=False,
    )
    db.session.add(policy)
    db.session.commit()
    return case, policy, channel


def _delivery_preflight(scope, case, policy, channel, *, at=AT, actor_id=None):
    from app.intelligence.alert_intelligence.vault_provider_delivery import preflight_vault_provider_firing

    vault, _source, binding, actor = scope
    return preflight_vault_provider_firing(
        binding_id=binding.id,
        instance_id=vault.id,
        public_id=case.public_id,
        actor_user_id=actor.id if actor_id is None else actor_id,
        policy_id=policy.id,
        channel_id=channel.id,
        now=at,
    )


def test_delivery_preflight_never_admits_transport_even_with_matching_policy(scope, monkeypatch):
    from app.intelligence.alert_intelligence import vault_provider_delivery as delivery

    case, policy, channel = _delivery_candidate(scope)
    monkeypatch.setattr('app.intelligence.alert_intelligence.vault_provider_delivery.domain_event_allowed', lambda *_: False)
    assert _delivery_preflight(scope, case, policy, channel) == 'catalog_unqualified'
    monkeypatch.setattr(delivery, 'domain_event_allowed', lambda *_: True)
    assert _delivery_preflight(scope, case, policy, channel) == 'target_authority_unqualified'
    assert NotificationDelivery.query.count() == 0
    assert case.routing_state == 'suppressed'
    audits = AuditEvent.query.filter_by(action='vault_provider_delivery_preflight').all()
    assert len(audits) == 2
    assert 'fixture@example.invalid' not in repr([audit.metadata_json for audit in audits])
    assert 'fixture-only-credential' not in repr([audit.metadata_json for audit in audits])


@pytest.mark.parametrize('condition', ['foreign', 'broad', 'resolved', 'disabled', 'mixed'])
def test_delivery_preflight_requires_dedicated_exact_policy(scope, condition):
    case, policy, channel = _delivery_candidate(scope)
    if condition == 'foreign':
        policy.matchers_json = {'vault_instance': '9999', 'source_binding_id': '9999'}
    elif condition == 'broad':
        policy.matchers_json = {}
    elif condition == 'resolved':
        policy.send_resolved = True
    elif condition == 'disabled':
        policy.enabled = False
    else:
        policy.domains_json = ['secrets_pki', 'kubernetes']
    db.session.commit()
    assert _delivery_preflight(scope, case, policy, channel) == 'policy_unqualified'
    assert NotificationDelivery.query.count() == 0


@pytest.mark.parametrize('condition', ['retired', 'unvalidated', 'foreign', 'wrong_event', 'severity'])
def test_delivery_preflight_requires_dedicated_validated_channel(scope, condition):
    case, policy, channel = _delivery_candidate(scope)
    if condition == 'retired':
        channel.lifecycle_state = 'retired'
    elif condition == 'unvalidated':
        channel.test_status = 'not_tested'
    elif condition == 'foreign':
        channel.domains = ['registry']
    elif condition == 'wrong_event':
        channel.event_types = ['alert_ops.resolved']
    else:
        channel.minimum_severity = 'critical'
    db.session.commit()
    assert _delivery_preflight(scope, case, policy, channel) == 'channel_unqualified'
    assert NotificationDelivery.query.count() == 0


def test_delivery_preflight_checks_scope_freshness_and_acknowledgement(scope):
    case, policy, channel = _delivery_candidate(scope)
    denied = _actor()
    db.session.commit()
    assert _delivery_preflight(scope, case, policy, channel, actor_id=denied.id) == 'forbidden'
    assert _delivery_preflight(scope, case, policy, channel, at=AT + timedelta(minutes=6)) == 'source_unavailable'
    assert _operate(scope, 'acknowledge') == 'committed'
    assert _delivery_preflight(scope, case, policy, channel) == 'workflow_suppressed'
    assert NotificationDelivery.query.count() == 0


@pytest.mark.parametrize('status', ['sent', 'queued', 'failed', 'skipped'])
def test_delivery_preflight_detects_prior_attempt_across_routing_policy(scope, status):
    case, policy, channel = _delivery_candidate(scope)
    db.session.add(
        NotificationDelivery(
            channel_id=channel.id,
            event_key=f'alert-case:{case.public_id}:firing:route-policy-999:1',
            event_type='alert_ops.firing',
            domain='secrets_pki',
            asset_type='vault_instance',
            asset_key=case.asset_key,
            severity=case.severity,
            status=status,
            payload_json={},
        )
    )
    db.session.commit()
    assert _delivery_preflight(scope, case, policy, channel) == 'prior_delivery_review_required'
    assert NotificationDelivery.query.count() == 1


def test_observation_admission_rejects_unqualified_operator_workflow(scope):
    vault, _source, binding, actor = scope
    case = _operator_case(scope)
    case.workflow_state = 'mitigating'
    db.session.commit()
    later = AT + timedelta(minutes=1)
    _commit(binding, [], observed=later)
    assert _admit(binding, actor, at=later)['status'] == 'blocked'
    assert case.source_state == 'firing'
    assert AlertCaseEvent.query.count() == AuditEvent.query.count() == 1


def test_operator_workflow_audit_must_match_owner_and_state(scope):
    vault, _source, _binding, actor = scope
    _operator_case(scope)
    _grant(vault, actor, permission='intelligence.decisions.create')
    assert _operate(scope, 'acknowledge') == 'committed'
    audit = AuditEvent.query.filter_by(action='vault_provider_case_acknowledge').one()
    audit.metadata_json = {**audit.metadata_json, 'owner_user_id': None}
    db.session.commit()
    assert not operator.admitted_operator_workflow_qualified(AlertCase.query.one())
    assert _operate(scope, 'mitigating') == 'unavailable'
