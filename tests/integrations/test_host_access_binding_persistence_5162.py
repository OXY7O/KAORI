"""Real database reference recording, exact scope and mandatory audit (#5162)."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from flask import Flask

from app.extensions.db import db
from app.infrastructure_automation import host_access_binding as service
from app.infrastructure_automation.host_enrollment import host_revision
from app.infrastructure_automation.kubernetes.committed_host_access import committed_pilot_access_fingerprint
from app.infrastructure_automation.kubernetes.kubespray_preflight import KUBESPRAY_RELEASE
from app.infrastructure_automation.kubernetes.source_policy import (
    ANSIBLE_CORE_VERSION,
    ANSIBLE_RUNNER_VERSION,
    PROFILE_KEY,
    REPOSITORY,
    SOURCE_CANDIDATE_SHA,
)
from app.models.automation import AutomationHostAccessBinding, AutomationHostAsset, AutomationInventoryAssignment
from app.models.identity import ExternalIdentityLink, IdentityProvider
from app.models.integration import IntegrationInstance
from app.models.notification import Notification
from app.models.rbac import Permission, Role, RolePermission
from app.models.scope_access import ScopeAccessPolicy, ScopeAccessPolicyRevision
from app.models.secrets_pki import (
    SecretIdentity,
    SecretInventoryCollectionState,
    SecretProviderRepresentation,
    SecretVersionObservation,
)
from app.models.user import User
from app.models.vault import VaultInstance


def _source_metadata():
    return {
        'source_repository': REPOSITORY,
        'source_sha': SOURCE_CANDIDATE_SHA,
        'profile_key': PROFILE_KEY,
        'ansible_core_version': ANSIBLE_CORE_VERSION,
        'ansible_runner_version': ANSIBLE_RUNNER_VERSION,
        'kubespray_release': KUBESPRAY_RELEASE,
        'execution_environment_digest': 'sha256:' + 'b' * 64,
        'source_validation': {
            'status': 'source_checked',
            'repository': REPOSITORY,
            'revision': SOURCE_CANDIDATE_SHA,
            'profile_key': PROFILE_KEY,
            'checked_files': 5,
            'operation_authorized': False,
        },
    }


def _actor_records():
    role = Role(name='binding_operator', display_name='Binding Operator')
    permissions = [
        Permission(key='integrations.manage', module='integrations', action='manage'),
        Permission(key='inventory.view', module='inventory', action='view'),
        Permission(key='secrets_pki.view', module='secrets_pki', action='view'),
    ]
    db.session.add_all([role, *permissions])
    db.session.flush()
    db.session.add_all([RolePermission(role_id=role.id, permission_id=perm.id) for perm in permissions])
    actors = [
        User(username='binding-actor', email='actor@test.invalid', role_id=role.id),
        User(username='binding-checker', email='checker@test.invalid', role_id=role.id),
    ]
    db.session.add_all(actors)
    db.session.flush()
    return actors


def _source_records():
    connection = IntegrationInstance(
        integration_type='configuration_automation',
        provider_key='ansible',
        adapter_key='ansible',
        name='Fixture Ansible',
        environment='laboratory',
        enabled=True,
        lifecycle_status='active',
        metadata_json=_source_metadata(),
    )
    provider = IntegrationInstance(
        integration_type='secrets_pki',
        provider_key='vault',
        adapter_key='vault_http_v1',
        name='Fixture Vault',
        environment='laboratory',
        enabled=True,
        lifecycle_status='active',
        readiness_status='ready',
    )
    db.session.add_all([connection, provider])
    db.session.flush()
    db.session.add(
        VaultInstance(
            integration_instance_id=provider.id,
            endpoint='https://vault.invalid',
            auth_mount='approle',
            role_id='fixture',
            secret_id='test-only',
            kv2_mounts=['kv'],
            namespace='',
            verify_ssl=True,
        )
    )
    return connection, provider


def _secret_records(provider, now):
    identity = SecretIdentity()
    representation = SecretProviderRepresentation(
        secret_identity=identity,
        integration_instance_id=provider.id,
        provider_key='vault',
        provider_namespace='',
        mount='kv',
        path='fixture/private/path',
        path_sha256=sha256(b'fixture/private/path').hexdigest(),
        representation_role='material_authority',
        observation_status='observed',
        current_version=2,
        oldest_version=2,
        last_observed_at=now,
    )
    db.session.add(representation)
    db.session.flush()
    db.session.add_all(
        [
            SecretVersionObservation(
                representation_id=representation.id, version=2, destroyed=False, last_observed_at=now
            ),
            SecretInventoryCollectionState(
                integration_instance_id=provider.id,
                provider_namespace='',
                mount='kv',
                status='ready',
                observed_count=1,
                last_observed_at=now,
                last_committed_at=now,
            ),
        ]
    )
    return identity


@pytest.fixture
def binding_store():
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY='fixture-only',
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
        IdentityProvider.__table__,
        ExternalIdentityLink.__table__,
        IntegrationInstance.__table__,
        VaultInstance.__table__,
        ScopeAccessPolicy.__table__,
        ScopeAccessPolicyRevision.__table__,
        AutomationHostAsset.__table__,
        AutomationInventoryAssignment.__table__,
        SecretIdentity.__table__,
        SecretProviderRepresentation.__table__,
        SecretVersionObservation.__table__,
        SecretInventoryCollectionState.__table__,
        AutomationHostAccessBinding.__table__,
        Notification.__table__,
    ]
    with app.app_context():
        db.Model.metadata.create_all(bind=db.engine, tables=tables)
        now = datetime.now(UTC)
        actor, checker = _actor_records()
        connection, provider = _source_records()
        identity = _secret_records(provider, now)
        host = AutomationHostAsset(name='node-one', environment='laboratory', address='10.0.0.1')
        assignment = AutomationInventoryAssignment(
            integration_instance_id=connection.id, host=host, role='control_plane', enabled=True
        )
        policy = ScopeAccessPolicy(
            principal_user_id=actor.id,
            permission_key='secrets_pki.view',
            integration_instance_id=provider.id,
            scope_level='vault_mount',
            provider_namespace='',
            mount='kv',
            current_revision=1,
        )
        db.session.add_all([assignment, policy])
        db.session.flush()
        db.session.add(
            ScopeAccessPolicyRevision(
                policy_id=policy.id,
                revision_number=1,
                lifecycle_status='active',
                effective_from=now - timedelta(minutes=1),
                effective_until=now + timedelta(minutes=30),
                requested_by_user_id=actor.id,
                approved_by_user_id=checker.id,
                approved_at=now,
                change_reason='fixture-only',
            )
        )
        db.session.commit()
        intent = service.HostAccessBindingIntent(
            connection_id=connection.id,
            host_id=host.id,
            expected_host_revision=host_revision(assignment),
            scope_ref=policy.id,
            secret_identity_id=identity.id,
            expected_secret_version=2,
            host_key_digest='sha256:' + 'e' * 64,
        )
        actor_id, checker_id = actor.id, checker.id
        db.session.remove()
        try:
            yield actor_id, checker_id, intent
        finally:
            db.session.remove()
            db.Model.metadata.drop_all(bind=db.engine, tables=list(reversed(tables)))


def _assert_no_writes():
    assert AutomationHostAccessBinding.query.count() == 0
    assert Notification.query.count() == 0


def test_committed_binding_and_audit_with_real_exact_scope(binding_store):
    actor, _, intent = binding_store
    result = service.record_host_access_reference(actor_id=actor, intent=intent)
    db.session.remove()
    binding = AutomationHostAccessBinding.query.one()
    audit = Notification.query.one()
    assert binding.reference_fingerprint == result.fingerprint
    assert binding.host_revision == intent.expected_host_revision
    assert binding.recorded_by_user_id == actor
    assert binding.secret_version == 2
    assert audit.actor_key == f'user:{actor}'
    assert audit.event_type == 'automation_host_access_reference_recorded'
    assert 'fixture/private/path' not in str(audit.metadata_json)
    assert intent.secret_identity_id not in str(audit.metadata_json)
    assert intent.host_key_digest not in str(audit.metadata_json)
    assert result.execution_authorized is False
    with pytest.raises(service.HostAccessBindingDenied):
        service.record_host_access_reference(actor_id=actor, intent=intent)
    assert AutomationHostAccessBinding.query.count() == Notification.query.count() == 1


@pytest.mark.parametrize(
    'failure', ['foreign_actor', 'wrong_secret', 'version_drift', 'revoked', 'incomplete', 'host_drift']
)
def test_database_denials_leave_no_binding_or_audit(binding_store, failure):
    actor, checker, intent = binding_store
    if failure == 'foreign_actor':
        actor = checker
    elif failure == 'wrong_secret':
        intent = replace(intent, secret_identity_id=str(uuid4()))
    elif failure == 'version_drift':
        intent = replace(intent, expected_secret_version=1)
    elif failure == 'revoked':
        ScopeAccessPolicyRevision.query.one().lifecycle_status = 'revoked'
    elif failure == 'incomplete':
        SecretInventoryCollectionState.query.one().observed_count = 2
    elif failure == 'host_drift':
        AutomationHostAsset.query.one().address = '10.0.0.2'
    db.session.commit()
    db.session.remove()
    with pytest.raises(service.HostAccessBindingDenied):
        service.record_host_access_reference(actor_id=actor, intent=intent)
    _assert_no_writes()


def test_real_transaction_rolls_back_after_audit_was_staged(binding_store, monkeypatch):
    actor, _, intent = binding_store
    original = service.stage_operational_activity

    def fail_after_stage(**kwargs):
        original(**kwargs)
        db.session.flush()
        raise RuntimeError('injected audit boundary failure')

    monkeypatch.setattr(service, 'stage_operational_activity', fail_after_stage)
    with pytest.raises(service.HostAccessBindingDenied):
        service.record_host_access_reference(actor_id=actor, intent=intent)
    db.session.remove()
    _assert_no_writes()


def _record_pilot(binding_store):
    actor, _, intent = binding_store
    service.record_host_access_reference(actor_id=actor, intent=intent)
    for index in (2, 3):
        host = AutomationHostAsset(name=f'node-{index}', environment='laboratory', address=f'10.0.0.{index}')
        assignment = AutomationInventoryAssignment(
            integration_instance_id=intent.connection_id, host=host, role='worker', enabled=True
        )
        db.session.add(assignment)
        db.session.commit()
        service.record_host_access_reference(
            actor_id=actor,
            intent=replace(intent, host_id=host.id, expected_host_revision=host_revision(assignment)),
        )
    db.session.remove()
    connection = db.session.get(IntegrationInstance, intent.connection_id)
    assignments = AutomationInventoryAssignment.query.filter_by(integration_instance_id=intent.connection_id).all()
    return connection, assignments


@pytest.mark.parametrize('drift', ['host', 'version', 'destroyed', 'missing_binding', 'generation', 'disabled_source'])
def test_persisted_pilot_access_correlation_invalidates_on_drift(binding_store, drift):
    connection, assignments = _record_pilot(binding_store)
    now = datetime.now(UTC)
    original = committed_pilot_access_fingerprint(connection, assignments, now=now)
    assert original and len(original) == 64
    assert original == committed_pilot_access_fingerprint(connection, list(reversed(assignments)), now=now)
    if drift == 'host':
        assignments[0].host.address = '10.0.0.99'
    elif drift == 'version':
        SecretProviderRepresentation.query.one().current_version = 3
    elif drift == 'destroyed':
        SecretVersionObservation.query.one().destroyed = True
    elif drift == 'missing_binding':
        db.session.delete(AutomationHostAccessBinding.query.first())
    elif drift == 'generation':
        SecretInventoryCollectionState.query.one().last_committed_at = now + timedelta(seconds=1)
    elif drift == 'disabled_source':
        IntegrationInstance.query.filter_by(provider_key='vault').one().enabled = False
    db.session.commit()
    changed = committed_pilot_access_fingerprint(connection, assignments, now=now + timedelta(seconds=2))
    if drift == 'generation':
        assert changed and changed != original
    else:
        assert changed is None
    assert Notification.query.count() == 3
