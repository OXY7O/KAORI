"""Disposable real PostgreSQL issuer-service qualification (#5245).

Only native provider IO and the independently managed filesystem are synthetic.
Actual signature verification, Access, lifecycle, SQL locks and audit execute.
"""

from __future__ import annotations

import base64
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from threading import Barrier
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from flask import Flask
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from app.access.scope_policy import CredentialIssuerScope
from app.access.scoped_grants import ScopeGrantValidity, ScopedGrantRejected
from app.extensions.db import db
from app.integrations.secrets_management.secrets_pki.providers.credential_version_proof import canonical_statement
from app.integrations.secrets_management.secrets_pki.providers.issuer_transit import (
    TransitIssuerBinding,
    TransitIssuerObservation,
)
from app.models.identity import ExternalIdentityLink, IdentityProvider
from app.models.integration import IntegrationInstance
from app.models.notification import Notification
from app.models.rbac import Permission, Role, RolePermission
from app.models.scope_access import ScopeAccessPolicy, ScopeAccessPolicyRevision
from app.models.secrets_pki import SecretCredentialIssuerChallenge, SecretCredentialIssuerRevision
from app.models.user import User
from app.secrets_pki import issuer_authority, issuer_grants, issuer_lifecycle

CI_DSN = 'postgresql://postgres:postgres@postgres:5432/kaori_test'
_ROOT = Ed25519PrivateKey.from_private_bytes(b'\x11' * 32)
_ISSUER = Ed25519PrivateKey.from_private_bytes(b'\x12' * 32)
_PUBLIC = _ISSUER.public_key().public_bytes_raw()
_KEY = sha256(_PUBLIC).hexdigest()
_REQUEST = 'secrets_pki.request_credential_issuer'
_APPROVE = 'secrets_pki.approve_credential_issuer'
_REVOKE = 'secrets_pki.revoke_credential_issuer'


def _envelope(payload):
    return canonical_statement({'payload': payload, 'signature': _ROOT.sign(canonical_statement(payload)).hex()})


def _setup(engine):
    tables = (
        Role.__table__,
        Permission.__table__,
        RolePermission.__table__,
        User.__table__,
        IdentityProvider.__table__,
        ExternalIdentityLink.__table__,
        IntegrationInstance.__table__,
        ScopeAccessPolicy.__table__,
        ScopeAccessPolicyRevision.__table__,
        SecretCredentialIssuerRevision.__table__,
        SecretCredentialIssuerChallenge.__table__,
        Notification.__table__,
    )
    with engine.begin() as connection:
        db.Model.metadata.create_all(bind=connection, tables=tables)
        connection.execute(Role.__table__.insert(), [
            {'id': 1, 'name': 'issuer_fixture', 'display_name': 'Issuer fixture'},
            {'id': 2, 'name': 'admin_fixture', 'display_name': 'Admin fixture'},
        ])
        permissions = ('secrets_pki.view', _REQUEST, _APPROVE, _REVOKE, 'roles.manage', 'users.manage')
        for index, key in enumerate(permissions, start=1):
            connection.execute(Permission.__table__.insert().values(
                id=index, key=key, module=key.split('.')[0], action=key.split('.')[1]
            ))
            connection.execute(RolePermission.__table__.insert().values(
                role_id=1 if index <= 4 else 2, permission_id=index
            ))
        connection.execute(User.__table__.insert(), [
            {'id': index, 'username': f'fixture-{index}', 'email': f'{index}@fixture.invalid',
             'role_id': 1 if index <= 2 else 2}
            for index in range(1, 5)
        ])
        connection.execute(IntegrationInstance.__table__.insert().values(
            id=1, integration_type='secrets_pki', provider_key='openbao', adapter_key='openbao',
            name='issuer fixture', enabled=True, lifecycle_status='active', readiness_status='ready'
        ))


@pytest.fixture
def issuer_store(monkeypatch):
    if (
        os.environ.get('APP_ENV') != 'testing'
        or os.environ.get('TEST_DATABASE_URL') != CI_DSN
        or os.environ.get('DATABASE_URL') != CI_DSN
    ):
        pytest.skip('Requires the exact isolated KAORI CI PostgreSQL fixture.')
    schema = f'issuer_5245_{uuid4().hex}'
    admin = create_engine(CI_DSN, connect_args={'connect_timeout': 5})
    try:
        with admin.begin() as connection:
            assert connection.dialect.name == 'postgresql'
            assert connection.scalar(text('SELECT current_database()')) == 'kaori_test'
            connection.execute(CreateSchema(schema))
        try:
            app = Flask(__name__)
            app.config.update(
                TESTING=True,
                SECRET_KEY='fixture-only',
                SQLALCHEMY_DATABASE_URI=CI_DSN,
                SQLALCHEMY_ENGINE_OPTIONS={
                    'isolation_level': 'READ COMMITTED',
                    'connect_args': {'options': f'-c search_path={schema}', 'connect_timeout': 5},
                },
            )
            db.init_app(app)
            with app.app_context():
                engine = db.engine
                try:
                    with engine.connect() as connection:
                        assert connection.scalar(text('SELECT current_schema()')) == schema
                    _setup(engine)
                    now = datetime.now(UTC)
                    transit = TransitIssuerBinding('openbao', 'https://fixture.invalid', 'fixture-cluster', '',
                                                   'transit', 'issuer', 1, _KEY)
                    scope = CredentialIssuerScope(1, 'openbao', '', 'kv', 'a' * 64)
                    scope = replace(scope, deployment_ref=issuer_authority.deployment_identity_ref(scope, transit))
                    deployment = {
                        'schema': 'kaori.secrets.issuer_deployment.v1',
                        'state': 'active',
                        'scope': asdict(scope),
                        'transit': asdict(transit),
                        'key_sha256': _KEY,
                        'source_owner_id': 1,
                        'checker_id': 2,
                        'issued_at': (now - timedelta(minutes=1)).isoformat(),
                        'expires_at': (now + timedelta(hours=1)).isoformat(),
                    }
                    deployment_file = f'deployment-{scope.deployment_ref}.json'
                    files = {
                        'root.pub': _ROOT.public_key().public_bytes_raw().hex().encode('ascii'),
                        deployment_file: _envelope(deployment),
                    }
                    monkeypatch.setattr(issuer_authority, '_read_authority_file', files.get)
                    monkeypatch.setattr(
                        issuer_lifecycle, 'observe_transit_issuer',
                        lambda binding, *, token: TransitIssuerObservation(binding, _PUBLIC.hex(), datetime.now(UTC)),
                    )
                    yield app, engine, scope, files
                finally:
                    db.session.remove()
                    engine.dispose()
        finally:
            with admin.begin() as connection:
                connection.execute(DropSchema(schema, cascade=True))
    finally:
        admin.dispose()


def _grant(store, actor, permission):
    now = datetime.now(UTC)
    intent = issuer_grants.IssuerGrantIntent(
        store[2], actor, permission,
        ScopeGrantValidity(now - timedelta(minutes=1), now + timedelta(minutes=30)), 'operational_access',
    )
    policy = issuer_grants.request_issuer_grant(actor_user_id=3, intent=intent)
    issuer_grants.approve_issuer_grant(actor_user_id=4, policy_id=policy, expected_revision=1)
    return policy


def _enroll(store):
    for actor, permission in ((1, _REQUEST), (2, _APPROVE), (2, _REVOKE)):
        _grant(store, actor, permission)
    scope, files = store[2], store[3]
    issued = issuer_lifecycle.request_issuer_enrollment(
        actor_id=1,
        intent=issuer_lifecycle.IssuerEnrollmentIntent(scope, 0, datetime.now(UTC) + timedelta(minutes=20)),
        inspection_token='fixture-only',
    )
    now = datetime.now(UTC)
    receipt = {
        'schema': 'kaori.secrets.issuer_custody.v1',
        'state': 'active',
        'deployment_evidence_ref': sha256(files[f'deployment-{scope.deployment_ref}.json']).hexdigest(),
        'key_sha256': _KEY,
        'revision_number': issued.draft_revision + 1,
        'challenge_sha256': issued.challenge_sha256,
        'source_owner_id': 1,
        'checker_id': 2,
        'issued_at': now.isoformat(),
        'expires_at': min(issued.expires_at, now + timedelta(minutes=2)).isoformat(),
    }
    files[f'custody-{issued.challenge_sha256}.json'] = _envelope(receipt)
    signature = 'vault:v1:' + base64.b64encode(_ISSUER.sign(issued.statement)).decode('ascii')
    return issuer_lifecycle.IssuerApprovalIntent(scope, issued.challenge_sha256, issued.draft_revision, signature)


def _approve(intent):
    return issuer_lifecycle.approve_issuer_enrollment(actor_id=2, intent=intent, inspection_token='fixture-only')


def _state(engine):
    with Session(engine) as session:
        revisions = session.scalars(
            select(SecretCredentialIssuerRevision.lifecycle_status).order_by(SecretCredentialIssuerRevision.revision_number)
        ).all()
        challenges = session.scalars(select(SecretCredentialIssuerChallenge.lifecycle_status)).all()
        events = session.scalars(select(Notification.event_type).order_by(Notification.id)).all()
        return list(revisions), list(challenges), list(events)


def test_governed_end_to_end_issuer_lifecycle_and_replay(issuer_store):
    intent = _enroll(issuer_store)
    engine = issuer_store[1]
    assert _state(engine)[:2] == (['draft'], ['pending'])
    assert _approve(intent) == 2
    assert _state(engine)[:2] == (['draft', 'active'], ['consumed'])
    with pytest.raises(issuer_lifecycle.IssuerLifecycleDenied):
        _approve(intent)
    assert issuer_lifecycle.revoke_issuer_enrollment(actor_id=2, scope=intent.scope, expected_revision=2) == 3
    revisions, challenges, events = _state(engine)
    assert revisions == ['draft', 'active', 'revoked']
    assert challenges == ['consumed']
    assert events[-3:] == [
        'secrets_pki_issuer_draft', 'secrets_pki_issuer_active', 'secrets_pki_issuer_revoked'
    ]


def test_independent_grant_approval_and_withdrawal(issuer_store):
    now = datetime.now(UTC)
    intent = issuer_grants.IssuerGrantIntent(
        issuer_store[2], 1, _REQUEST,
        ScopeGrantValidity(now - timedelta(minutes=1), now + timedelta(minutes=30)), 'operational_access',
    )
    policy_id = issuer_grants.request_issuer_grant(actor_user_id=3, intent=intent)
    with pytest.raises(ScopedGrantRejected):
        issuer_grants.approve_issuer_grant(actor_user_id=3, policy_id=policy_id, expected_revision=1)
    issuer_grants.approve_issuer_grant(actor_user_id=4, policy_id=policy_id, expected_revision=1)
    issuer_grants.revoke_issuer_grant(actor_user_id=3, policy_id=policy_id, expected_revision=2)
    with Session(issuer_store[1]) as session:
        policy = session.get(ScopeAccessPolicy, policy_id)
        assert policy.current_revision == 3
        assert session.scalars(select(ScopeAccessPolicyRevision.lifecycle_status).order_by(
            ScopeAccessPolicyRevision.revision_number
        )).all() == ['draft', 'active', 'revoked']


@pytest.mark.parametrize('failure', ['signature', 'custody_removed', 'owner_grant_revoked'])
def test_approval_denial_leaves_draft_and_challenge_unchanged(issuer_store, failure):
    intent = _enroll(issuer_store)
    engine = issuer_store[1]
    if failure == 'signature':
        intent = replace(intent, signature='vault:v2:invalid')
    elif failure == 'custody_removed':
        del issuer_store[3][f'custody-{intent.challenge_sha256}.json']
    else:
        policy = ScopeAccessPolicy.query.filter_by(permission_key=_REQUEST).one()
        issuer_grants.revoke_issuer_grant(actor_user_id=3, policy_id=policy.id, expected_revision=2)
    before = _state(engine)
    with pytest.raises(issuer_lifecycle.IssuerLifecycleDenied):
        _approve(intent)
    assert _state(engine) == before


def test_approval_rolls_back_after_actual_audit_flush(issuer_store, monkeypatch):
    intent = _enroll(issuer_store)
    engine = issuer_store[1]
    before = _state(engine)
    original = issuer_lifecycle.stage_operational_activity

    def fail_after_stage(**kwargs):
        original(**kwargs)
        db.session.flush()
        raise RuntimeError('fixture audit failure')

    monkeypatch.setattr(issuer_lifecycle, 'stage_operational_activity', fail_after_stage)
    with pytest.raises(issuer_lifecycle.IssuerLifecycleDenied):
        _approve(intent)
    assert _state(engine) == before
    monkeypatch.setattr(issuer_lifecycle, 'stage_operational_activity', original)
    assert _approve(intent) == 2


def test_revoke_draft_when_source_disabled_revokes_pending_challenge(issuer_store):
    intent = _enroll(issuer_store)
    source = db.session.get(IntegrationInstance, 1)
    source.enabled = False
    db.session.commit()
    assert issuer_lifecycle.revoke_issuer_enrollment(actor_id=2, scope=intent.scope, expected_revision=1) == 2
    assert _state(issuer_store[1])[:2] == (['draft', 'revoked'], ['revoked'])
    with pytest.raises(issuer_lifecycle.IssuerLifecycleDenied):
        _approve(intent)


def test_competing_real_service_approvals_have_one_winner(issuer_store, monkeypatch):
    intent = _enroll(issuer_store)
    app, engine = issuer_store[:2]
    barrier = Barrier(2)

    def observe(binding, *, token):
        barrier.wait(timeout=5)
        return TransitIssuerObservation(binding, _PUBLIC.hex(), datetime.now(UTC))

    monkeypatch.setattr(issuer_lifecycle, 'observe_transit_issuer', observe)

    def compete():
        with app.app_context():
            try:
                return _approve(intent)
            except issuer_lifecycle.IssuerLifecycleDenied:
                return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(compete)
        second = pool.submit(compete)
        results = [first.result(timeout=25), second.result(timeout=25)]
    assert results.count(2) == results.count(None) == 1
    revisions, challenges, events = _state(engine)
    assert revisions == ['draft', 'active']
    assert challenges == ['consumed']
    assert events.count('secrets_pki_issuer_active') == 1
