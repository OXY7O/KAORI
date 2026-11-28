"""Real database reference recording, exact scope and mandatory audit (#5162)."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from flask import Flask, current_app

from app.access import scoped_grants
from app.extensions.db import db
from app.infrastructure_automation import credential_grants, ssh_trust_lifecycle
from app.infrastructure_automation import host_access_binding as service
from app.infrastructure_automation.credential_evidence import resolve_current_credential_evidence
from app.infrastructure_automation.credential_scope_target import (
    CREDENTIAL_USE_PERMISSION,
    READ_ONLY_FACTS_OPERATION,
    exact_credential_target_current,
)
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
from app.models.automation import (
    AutomationHostAccessBinding,
    AutomationHostAsset,
    AutomationHostTrustRevision,
    AutomationInventoryAssignment,
)
from app.models.identity import ExternalIdentityLink, IdentityProvider
from app.models.integration import IntegrationInstance
from app.models.notification import Notification
from app.models.openbao import OpenBaoInstance
from app.models.rbac import Permission, Role, RolePermission
from app.models.scope_access import AutomationCredentialScopeTarget, ScopeAccessPolicy, ScopeAccessPolicyRevision
from app.models.secrets_pki import (
    SecretCredentialIssuerRevision,
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
        provider_key=provider.provider_key,
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
        OpenBaoInstance.__table__,
        ScopeAccessPolicy.__table__,
        ScopeAccessPolicyRevision.__table__,
        AutomationCredentialScopeTarget.__table__,
        AutomationHostAsset.__table__,
        AutomationInventoryAssignment.__table__,
        SecretIdentity.__table__,
        SecretProviderRepresentation.__table__,
        SecretVersionObservation.__table__,
        SecretCredentialIssuerRevision.__table__,
        SecretInventoryCollectionState.__table__,
        AutomationHostAccessBinding.__table__,
        AutomationHostTrustRevision.__table__,
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
    assert result.ssh_trust_verified is False
    assert result.privileged_identity_verified is False
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


@pytest.mark.parametrize(
    'drift', ['host', 'port', 'role', 'key', 'version', 'destroyed', 'missing_binding', 'generation', 'disabled_source']
)
def test_persisted_pilot_access_correlation_invalidates_on_drift(binding_store, drift):
    connection, assignments = _record_pilot(binding_store)
    now = datetime.now(UTC)
    original = committed_pilot_access_fingerprint(connection, assignments, now=now)
    assert original and len(original) == 64
    assert original == committed_pilot_access_fingerprint(connection, list(reversed(assignments)), now=now)
    if drift == 'host':
        assignments[0].host.address = '10.0.0.99'
    elif drift == 'port':
        assignments[0].host.ssh_port = 2222
    elif drift == 'role':
        assignments[0].role = 'worker' if assignments[0].role == 'control_plane' else 'control_plane'
    elif drift == 'key':
        AutomationHostAccessBinding.query.filter_by(assignment_id=assignments[0].id).one().host_key_digest = (
            'sha256:' + 'f' * 64
        )
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


@pytest.mark.parametrize(
    'drift',
    [
        None,
        'host',
        'role',
        'key',
        'version',
        'destroyed',
        'generation',
        'namespace',
        'wrong_policy',
        'wrong_identity',
        'wrong_operation',
        'wrong_source',
        'wrong_profile',
        'wrong_assignment',
        'metadata_permission',
    ],
)
def test_exact_credential_target_currentness_is_not_a_grant(binding_store, drift):
    actor, _, intent = binding_store
    service.record_host_access_reference(actor_id=actor, intent=intent)
    binding = AutomationHostAccessBinding.query.one()
    assignment = AutomationInventoryAssignment.query.one()
    representation = SecretProviderRepresentation.query.one()
    # A transient policy/selector is sufficient for this non-authorizing
    # predicate test; no grant writer or active credential grant is created.
    policy = ScopeAccessPolicy(
        id=str(uuid4()),
        principal_user_id=actor,
        permission_key=CREDENTIAL_USE_PERMISSION,
        integration_instance_id=representation.integration_instance_id,
        scope_level='automation_credential',
        provider_namespace=representation.provider_namespace,
        mount=representation.mount,
        current_revision=1,
    )
    target = AutomationCredentialScopeTarget(
        policy_id=policy.id,
        ansible_connection_id=intent.connection_id,
        assignment_id=assignment.id,
        host_id=assignment.host_id,
        host_revision=binding.host_revision,
        reference_fingerprint=binding.reference_fingerprint,
        secret_identity_id=representation.secret_identity_id,
        secret_representation_id=representation.id,
        secret_version=binding.secret_version,
        source_revision=SOURCE_CANDIDATE_SHA,
        profile_key=PROFILE_KEY,
        operation_key=READ_ONLY_FACTS_OPERATION,
    )
    now = datetime.now(UTC)
    assert exact_credential_target_current(policy, target, now=now)
    if drift == 'host':
        assignment.host.address = '10.0.0.99'
    elif drift == 'role':
        assignment.role = 'worker'
    elif drift == 'key':
        binding.host_key_digest = 'sha256:' + 'f' * 64
    elif drift == 'version':
        representation.current_version += 1
    elif drift == 'destroyed':
        SecretVersionObservation.query.one().destroyed = True
    elif drift == 'generation':
        SecretInventoryCollectionState.query.one().observed_count = 2
    elif drift == 'namespace':
        VaultInstance.query.one().namespace = 'other'
    elif drift == 'wrong_policy':
        target.policy_id = str(uuid4())
    elif drift == 'wrong_identity':
        target.secret_identity_id = str(uuid4())
    elif drift == 'wrong_operation':
        target.operation_key = 'arbitrary'
    elif drift == 'wrong_source':
        target.source_revision = '0' * 40
    elif drift == 'wrong_profile':
        target.profile_key = 'other'
    elif drift == 'wrong_assignment':
        target.assignment_id += 100
    elif drift == 'metadata_permission':
        policy.permission_key = 'secrets_pki.view'
    db.session.commit()
    assert exact_credential_target_current(policy, target, now=datetime.now(UTC)) is (drift is None)
    assert ScopeAccessPolicy.query.count() == 1
    assert Notification.query.count() == 1


def _credential_request(binding_store):
    actor, checker, intent = binding_store
    service.record_host_access_reference(actor_id=actor, intent=intent)
    role = db.session.get(User, actor).role_record
    for key in (CREDENTIAL_USE_PERMISSION, 'jobs.execute', 'roles.manage', 'users.manage'):
        permission = Permission(key=key, module=key.split('.')[0], action=key.split('.')[1])
        db.session.add(permission)
        db.session.flush()
        db.session.add(RolePermission(role_id=role.id, permission_id=permission.id))
    db.session.commit()
    binding = AutomationHostAccessBinding.query.one()
    request = credential_grants.CredentialGrantIntent(
        connection_id=intent.connection_id,
        host_id=intent.host_id,
        expected_host_revision=binding.host_revision,
        expected_reference_fingerprint=binding.reference_fingerprint,
    )
    now = datetime.now(UTC)
    validity = scoped_grants.ScopeGrantValidity(now, now + timedelta(minutes=10))
    return actor, checker, request, validity


def test_credential_request_commits_only_draft_and_exact_selector(binding_store):
    actor, checker, request, validity = _credential_request(binding_store)
    policy = credential_grants.request_automation_credential_grant(
        actor_user_id=checker,
        principal_user_id=actor,
        intent=request,
        validity=validity,
        reason_code='operational_access',
    )
    target = db.session.get(AutomationCredentialScopeTarget, policy.id)
    assert target is not None
    assert target.host_id == request.host_id
    assert target.reference_fingerprint == request.expected_reference_fingerprint
    assert policy.permission_key == CREDENTIAL_USE_PERMISSION
    assert policy.current_revision == 1
    assert policy.revisions[0].lifecycle_status == 'draft'
    assert policy.revisions[0].approved_by_user_id is None
    audit = Notification.query.filter_by(event_type='access_scope_grant_requested').one()
    assert audit.actor_key == f'user:{checker}'
    assert request.host_id not in str(audit.metadata_json)
    assert 'fixture/private/path' not in str(audit.metadata_json)
    # The existing metadata approval service must NOT activate this scope.
    with pytest.raises(scoped_grants.ScopedGrantRejected):
        scoped_grants.approve_scope_grant(policy_id=policy.id, approver_user_id=actor, expected_revision=1)
    assert policy.current_revision == 1
    assert policy.revisions[0].lifecycle_status == 'draft'


@pytest.mark.parametrize('failure', ['stale', 'permission', 'audit'])
def test_credential_request_denial_is_atomic(binding_store, monkeypatch, failure):
    actor, checker, request, validity = _credential_request(binding_store)
    if failure == 'stale':
        request = replace(request, expected_reference_fingerprint='0' * 64)
    elif failure == 'permission':
        permission = Permission.query.filter_by(key=CREDENTIAL_USE_PERMISSION).one()
        RolePermission.query.filter_by(permission_id=permission.id).delete()
        db.session.commit()
    else:
        original = scoped_grants.stage_operational_activity

        def fail_after_stage(**kwargs):
            original(**kwargs)
            db.session.flush()
            raise scoped_grants.ScopedGrantRejected('injected audit failure')

        monkeypatch.setattr(scoped_grants, 'stage_operational_activity', fail_after_stage)
    with pytest.raises(scoped_grants.ScopedGrantRejected):
        credential_grants.request_automation_credential_grant(
            actor_user_id=checker,
            principal_user_id=actor,
            intent=request,
            validity=validity,
            reason_code='operational_access',
        )
    assert AutomationCredentialScopeTarget.query.count() == 0
    assert ScopeAccessPolicy.query.count() == 1
    assert Notification.query.count() == 1


def _seed_revocable_trust(binding_store):
    actor, checker, intent = binding_store
    service.record_host_access_reference(actor_id=actor, intent=intent)
    role = db.session.get(User, actor).role_record
    for key in ('roles.manage', 'users.manage'):
        permission = Permission(key=key, module=key.split('.')[0], action=key.split('.')[1])
        db.session.add(permission)
        db.session.flush()
        db.session.add(RolePermission(role_id=role.id, permission_id=permission.id))
    binding = AutomationHostAccessBinding.query.one()
    assignment = AutomationInventoryAssignment.query.one()
    now = datetime.now(UTC)
    # Synthetic historical row, not an independently verified live host.
    record = AutomationHostTrustRevision(
        assignment_id=assignment.id,
        revision_number=1,
        lifecycle_status='active',
        host_revision=binding.host_revision,
        reference_fingerprint=binding.reference_fingerprint,
        address=assignment.host.address,
        ssh_port=assignment.host.ssh_port,
        algorithm='ssh-ed25519',
        public_key='fixture-public-key-not-operational',
        host_key_digest=binding.host_key_digest,
        source_kind='independent_console',
        evidence_ref='sha256:' + 'c' * 64,
        requested_by_user_id=actor,
        verified_by_user_id=checker,
        verified_at=now - timedelta(hours=3),
        effective_until=now - timedelta(hours=1),
        recorded_at=now - timedelta(hours=2),
        recorded_by_user_id=checker,
    )
    db.session.add(record)
    assignment.enabled = False
    db.session.commit()
    return actor, checker, assignment.id, intent.connection_id


def test_revoke_expired_disabled_trust_preserves_history_and_audit(binding_store):
    actor, checker, assignment_id, connection_id = _seed_revocable_trust(binding_store)
    result = ssh_trust_lifecycle.revoke_host_trust(
        actor_id=checker, connection_id=connection_id, assignment_id=assignment_id, expected_revision=1
    )
    db.session.remove()
    rows = AutomationHostTrustRevision.query.order_by(AutomationHostTrustRevision.revision_number).all()
    assert result == 2
    assert [row.lifecycle_status for row in rows] == ['active', 'revoked']
    assert rows[0].recorded_by_user_id == checker
    assert rows[1].requested_by_user_id == actor
    assert rows[1].evidence_ref == rows[0].evidence_ref
    assert rows[1].public_key == rows[0].public_key
    assert ssh_trust_lifecycle.latest_host_trust_revision(assignment_id).lifecycle_status == 'revoked'
    audit = Notification.query.filter_by(event_type='automation_host_trust_revoked').one()
    assert audit.actor_key == f'user:{checker}'
    for value in (rows[0].address, rows[0].public_key, rows[0].evidence_ref, rows[0].host_key_digest):
        assert value not in str(audit.metadata_json)
    with pytest.raises(ssh_trust_lifecycle.SSHTrustTransitionDenied):
        ssh_trust_lifecycle.revoke_host_trust(
            actor_id=checker, connection_id=connection_id, assignment_id=assignment_id, expected_revision=2
        )
    assert AutomationHostTrustRevision.query.count() == 2
    assert Notification.query.count() == 2


@pytest.mark.parametrize('failure', ['foreign_connection', 'stale', 'unauthorized', 'audit'])
def test_revoke_host_trust_denial_leaves_history_unchanged(binding_store, monkeypatch, failure):
    _, checker, assignment_id, connection_id = _seed_revocable_trust(binding_store)
    expected_revision = 1
    if failure == 'foreign_connection':
        connection_id = IntegrationInstance.query.filter_by(provider_key='vault').one().id
    elif failure == 'stale':
        expected_revision = 2
    elif failure == 'unauthorized':
        permission = Permission.query.filter_by(key='roles.manage').one()
        RolePermission.query.filter_by(permission_id=permission.id).delete()
        db.session.commit()
    else:
        original = ssh_trust_lifecycle.stage_operational_activity

        def fail_after_stage(**kwargs):
            original(**kwargs)
            db.session.flush()
            raise RuntimeError('fixture audit failure')

        monkeypatch.setattr(ssh_trust_lifecycle, 'stage_operational_activity', fail_after_stage)
    with pytest.raises((ssh_trust_lifecycle.SSHTrustTransitionDenied, scoped_grants.ScopedGrantRejected, RuntimeError)):
        ssh_trust_lifecycle.revoke_host_trust(
            actor_id=checker,
            connection_id=connection_id,
            assignment_id=assignment_id,
            expected_revision=expected_revision,
        )
    assert AutomationHostTrustRevision.query.one().lifecycle_status == 'active'
    assert Notification.query.count() == 1


def test_local_openbao_binding_uses_exact_scope_and_deployment(binding_store, monkeypatch):
    actor, checker, intent = binding_store
    monkeypatch.setenv('APP_ENV', 'development')
    monkeypatch.setitem(current_app.config, 'APP_ENV', 'development')
    monkeypatch.setenv('KAORI_LOCAL_OPENBAO_AUTOMATION_ENVIRONMENT', 'laboratory')
    monkeypatch.setenv('KAORI_LOCAL_OPENBAO_INVENTORY_MOUNT', 'kv')
    now = datetime.now(UTC)
    source = IntegrationInstance(
        integration_type='secrets_pki',
        provider_key='openbao',
        adapter_key='openbao_http_v1',
        name='Fixture OpenBao',
        enabled=True,
        lifecycle_status='active',
        health_status='connected',
        readiness_status='degraded',
    )
    db.session.add(source)
    db.session.flush()
    db.session.add(
        OpenBaoInstance(
            integration_instance_id=source.id,
            ownership='external',
            endpoint='https://bao.invalid',
            cluster_id='4f6db34e-2042-4f0c-a385-a0d39582acb8',
            auth_mount='approle',
            role_id='fixture',
            secret_id='test-only',
        )
    )
    monkeypatch.setenv('KAORI_LOCAL_OPENBAO_INVENTORY_PROVIDER_ID', str(source.id))
    identity = _secret_records(source, now)
    policy = ScopeAccessPolicy(
        principal_user_id=actor,
        permission_key='secrets_pki.view',
        integration_instance_id=source.id,
        scope_level='openbao_mount',
        provider_namespace='',
        mount='kv',
        current_revision=1,
    )
    db.session.add(policy)
    db.session.flush()
    db.session.add(
        ScopeAccessPolicyRevision(
            policy_id=policy.id,
            revision_number=1,
            lifecycle_status='active',
            effective_from=now - timedelta(minutes=1),
            effective_until=now + timedelta(minutes=30),
            requested_by_user_id=actor,
            approved_by_user_id=checker,
            approved_at=now,
            change_reason='fixture-only',
        )
    )
    db.session.commit()
    selected = replace(intent, scope_ref=policy.id, secret_identity_id=identity.id)
    with pytest.raises(service.HostAccessBindingDenied):
        service.record_host_access_reference(actor_id=actor, intent=replace(intent, scope_ref=policy.id))
    monkeypatch.setenv('KAORI_LOCAL_OPENBAO_AUTOMATION_ENVIRONMENT', 'testing')
    with pytest.raises(service.HostAccessBindingDenied):
        service.record_host_access_reference(actor_id=actor, intent=selected)
    _assert_no_writes()
    monkeypatch.setenv('KAORI_LOCAL_OPENBAO_AUTOMATION_ENVIRONMENT', 'laboratory')
    review = service.record_host_access_reference(actor_id=actor, intent=selected)
    binding = AutomationHostAccessBinding.query.one()
    representation = db.session.get(SecretProviderRepresentation, binding.secret_representation_id)
    assert representation.provider_key == 'openbao'
    assert review.execution_authorized is False
    assert review.ssh_trust_verified is False
    assert binding.reference_fingerprint == review.fingerprint
    assert Notification.query.count() == 1


def test_credential_evidence_requires_current_issuer_and_provider_created_time(binding_store):
    actor, checker, request, validity = _credential_request(binding_store)
    policy = credential_grants.request_automation_credential_grant(
        actor_user_id=checker,
        principal_user_id=actor,
        intent=request,
        validity=validity,
        reason_code='operational_access',
    )
    target = db.session.get(AutomationCredentialScopeTarget, policy.id)
    assert target is not None
    assert exact_credential_target_current(policy, target, now=datetime.now(UTC))
    assert resolve_current_credential_evidence(policy, target, now=datetime.now(UTC)) is None
    version = SecretVersionObservation.query.one()
    version.provider_created_time = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    db.session.commit()
    assert resolve_current_credential_evidence(policy, target, now=datetime.now(UTC)) is None
    assert policy.current_revision == 1
    assert policy.revisions[0].lifecycle_status == 'draft'
    assert SecretCredentialIssuerRevision.query.count() == 0
