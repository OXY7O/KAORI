"""Committed issuer resolution on the exact disposable PostgreSQL CI fixture (#5218)."""

from __future__ import annotations

import os
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import uuid4

import pytest
from flask import Flask
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from app.extensions.db import db
from app.models.integration import IntegrationInstance
from app.models.rbac import Role
from app.models.secrets_pki import SecretCredentialIssuerRevision
from app.models.user import User
from app.secrets_pki.credential_issuer_resolution import IssuerResolutionTarget, resolve_issuer_candidate

CI_DSN = 'postgresql://postgres:postgres@postgres:5432/kaori_test'
_PUBLIC = bytes.fromhex('d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a')


@pytest.fixture
def issuer_db():
    # Same exact disposable-target guard as Secret Store database preparation (#5211).
    if (
        os.environ.get('APP_ENV') != 'testing'
        or os.environ.get('TEST_DATABASE_URL') != CI_DSN
        or os.environ.get('DATABASE_URL') != CI_DSN
    ):
        pytest.skip('Requires the exact isolated KAORI CI PostgreSQL fixture.')

    schema = f'issuer_5218_{uuid4().hex}'
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
                SQLALCHEMY_DATABASE_URI=CI_DSN,
                SQLALCHEMY_ENGINE_OPTIONS={
                    'connect_args': {'options': f'-c search_path={schema}', 'connect_timeout': 5}
                },
            )
            db.init_app(app)
            with app.app_context():
                engine = db.engine
                try:
                    with engine.begin() as connection:
                        assert connection.scalar(text('SELECT current_schema()')) == schema
                        for table in (
                            Role.__table__,
                            User.__table__,
                            IntegrationInstance.__table__,
                            SecretCredentialIssuerRevision.__table__,
                        ):
                            table.create(connection)
                        connection.execute(
                            User.__table__.insert(),
                            [
                                {'id': 1, 'username': 'maker', 'email': 'maker@example.invalid'},
                                {'id': 2, 'username': 'checker', 'email': 'checker@example.invalid'},
                            ],
                        )
                    yield engine
                finally:
                    db.session.remove()
                    engine.dispose()
        finally:
            # Only the fresh, uniquely named test-owned schema is removed.
            with admin.begin() as connection:
                connection.execute(DropSchema(schema, cascade=True))
    finally:
        admin.dispose()


def _source(engine, provider):
    with Session(engine) as session:
        source = IntegrationInstance(
            name='issuer fixture',
            integration_type='secrets_pki',
            provider_key=provider,
            adapter_key=provider,
            enabled=True,
            lifecycle_status='active',
            readiness_status='ready',
        )
        session.add(source)
        session.flush()
        target = IssuerResolutionTarget(source.id, provider, '', 'kv', 'a' * 64, 1)
        session.commit()
    return target


def _record(target, **changes):
    now = datetime.now(UTC)
    values = {
        'integration_instance_id': target.integration_instance_id,
        'provider_key': target.provider_key,
        'provider_namespace': target.provider_namespace,
        'mount': target.mount,
        'deployment_ref': target.deployment_ref,
        'revision_number': target.revision_number,
        'lifecycle_status': 'active',
        'algorithm': 'ed25519',
        'public_key_hex': _PUBLIC.hex(),
        'key_sha256': sha256(_PUBLIC).hexdigest(),
        'evidence_ref': 'b' * 64,
        'requested_by_user_id': 1,
        'approved_by_user_id': 2,
        'recorded_by_user_id': 2,
        'approved_at': now - timedelta(minutes=2),
        'recorded_at': now - timedelta(minutes=1),
        'effective_from': now - timedelta(minutes=1),
        'effective_until': now + timedelta(hours=1),
    }
    return SecretCredentialIssuerRevision(**(values | changes))


def _assert_key(target):
    key = resolve_issuer_candidate(target)
    assert key is not None
    assert key.public_bytes_raw() == _PUBLIC


@pytest.mark.parametrize('provider', ['openbao', 'vault'])
def test_committed_candidate_visibility_and_timezone(issuer_db, provider):
    target = _source(issuer_db, provider)
    assert resolve_issuer_candidate(target) is None
    with Session(issuer_db) as writer:
        writer.add(_record(target))
        writer.flush()
        assert resolve_issuer_candidate(target) is None
        writer.rollback()
        assert resolve_issuer_candidate(target) is None
        record = _record(target)
        expected = record.effective_from
        writer.add(record)
        writer.commit()
    _assert_key(target)
    with Session(issuer_db) as reader:
        row = reader.scalars(select(SecretCredentialIssuerRevision)).one()
        assert row.effective_from.utcoffset() is not None
        assert row.effective_from == expected
        assert row.lifecycle_status == 'active'
        assert reader.scalar(select(func.count()).select_from(SecretCredentialIssuerRevision)) == 1


@pytest.mark.parametrize(
    'changes',
    [
        {'lifecycle_status': 'draft', 'approved_at': None, 'approved_by_user_id': None},
        {'lifecycle_status': 'revoked'},
        {'deployment_ref': 'c' * 64},
        {'provider_key': 'vault'},
    ],
)
def test_latest_committed_revision_denies_older_key(issuer_db, changes):
    target = _source(issuer_db, 'openbao')
    with Session(issuer_db) as writer:
        writer.add(_record(target))
        writer.commit()
        _assert_key(target)
        writer.add(_record(replace(target, revision_number=2), **changes))
        writer.flush()
        _assert_key(target)
        writer.commit()
    assert resolve_issuer_candidate(target) is None
    assert resolve_issuer_candidate(replace(target, revision_number=2)) is None


def test_scope_isolation_and_postgresql_constraints(issuer_db):
    target = _source(issuer_db, 'openbao')
    other = replace(target, provider_namespace='other', mount='other', revision_number=2)
    with Session(issuer_db) as writer:
        writer.add_all([_record(target), _record(other, lifecycle_status='revoked')])
        writer.commit()
        _assert_key(target)
        assert resolve_issuer_candidate(other) is None
        assert resolve_issuer_candidate(replace(target, mount='missing')) is None
        writer.add(_record(target))
        with pytest.raises(IntegrityError):
            writer.flush()
        writer.rollback()
        writer.add(_record(replace(target, revision_number=3), approved_by_user_id=-1, recorded_by_user_id=-1))
        with pytest.raises(IntegrityError):
            writer.flush()
        writer.rollback()
    _assert_key(target)
