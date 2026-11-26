"""Disposable PostgreSQL migration and storage contention qualification (#5237)."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from importlib import import_module
from threading import Event
from time import monotonic, sleep
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import CheckConstraint, UniqueConstraint, create_engine, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.schema import CreateSchema, DropSchema

from app.models.integration import IntegrationInstance
from app.models.rbac import Role
from app.models.secrets_pki import SecretCredentialIssuerChallenge
from app.models.user import User

CI_DSN = 'postgresql://postgres:postgres@postgres:5432/kaori_test'
_TABLE = SecretCredentialIssuerChallenge.__table__
_MIGRATION = import_module('migrations.versions.20261126_secret_issuer_challenge')
_NOW = datetime(2026, 11, 26, 12, tzinfo=UTC)


def _migrate(connection, *, downgrade=False):
    with Operations.context(MigrationContext.configure(connection)):
        if downgrade:
            _MIGRATION.downgrade()
        else:
            _MIGRATION.upgrade()


@pytest.fixture
def challenge_db():
    # Match admitted #5218 disposable target guard; no fallback to a local DB.
    if (
        os.environ.get('APP_ENV') != 'testing'
        or os.environ.get('TEST_DATABASE_URL') != CI_DSN
        or os.environ.get('DATABASE_URL') != CI_DSN
    ):
        pytest.skip('Requires the exact isolated KAORI CI PostgreSQL fixture.')

    schema = f'challenge_5237_{uuid4().hex}'
    admin = create_engine(CI_DSN, connect_args={'connect_timeout': 5})
    try:
        with admin.begin() as connection:
            assert connection.dialect.name == 'postgresql'
            assert connection.scalar(text('SELECT current_database()')) == 'kaori_test'
            connection.execute(CreateSchema(schema))
        try:
            engine = create_engine(
                CI_DSN,
                isolation_level='READ COMMITTED',
                connect_args={
                    'connect_timeout': 5,
                    'options': f'-c search_path={schema} -c lock_timeout=8000 -c statement_timeout=10000',
                },
            )
            try:
                with engine.begin() as connection:
                    assert connection.scalar(text('SELECT current_schema()')) == schema
                    for table in (Role.__table__, User.__table__, IntegrationInstance.__table__):
                        table.create(connection)
                    connection.execute(
                        User.__table__.insert(),
                        [
                            {'id': 1, 'username': 'maker', 'email': 'maker@example.invalid'},
                            {'id': 2, 'username': 'checker', 'email': 'checker@example.invalid'},
                        ],
                    )
                    for instance_id, provider in ((1, 'openbao'), (2, 'vault')):
                        connection.execute(
                            IntegrationInstance.__table__.insert().values(
                                id=instance_id,
                                name=f'challenge fixture {provider}',
                                integration_type='secrets_pki',
                                provider_key=provider,
                                adapter_key=provider,
                                enabled=True,
                                lifecycle_status='active',
                                readiness_status='ready',
                            )
                        )
                    _migrate(connection)
                yield engine
            finally:
                engine.dispose()
        finally:
            # Only the unique test-owned schema is removed.
            with admin.begin() as connection:
                connection.execute(DropSchema(schema, cascade=True))
    finally:
        admin.dispose()


def _pending(**changes):
    return {
        'integration_instance_id': 1,
        'provider_key': 'openbao',
        'provider_namespace': '',
        'mount': 'kv',
        'revision_number': 2,
        'deployment_ref': 'a' * 64,
        'key_sha256': 'b' * 64,
        'challenge_sha256': 'c' * 64,
        'source_owner_id': 1,
        'issued_at': _NOW,
        'expires_at': _NOW + timedelta(minutes=10),
        'lifecycle_status': 'pending',
    } | changes


def _resolve(connection, expected, state, *, at=_NOW + timedelta(minutes=1)):
    # Test-only conditional update. No verification or authorization is implied.
    predicates = [_TABLE.c[name] == value for name, value in expected.items()]
    predicates.append(_TABLE.c.issued_at <= at)
    if state == 'consumed':
        predicates.append(_TABLE.c.expires_at > at)
    return connection.execute(
        _TABLE.update()
        .where(*predicates)
        .values(
            lifecycle_status=state,
            resolved_at=at,
            resolved_by_user_id=2,
            possession_evidence_ref='d' * 64 if state == 'consumed' else None,
        )
        .returning(_TABLE.c.id)
    ).scalar_one_or_none()


def _read(engine):
    with engine.connect() as connection:
        return connection.execute(select(_TABLE)).mappings().one_or_none()


def test_actual_migration_schema_parity_and_empty_downgrade(challenge_db):
    with challenge_db.begin() as connection:
        inspector = inspect(connection)
        assert inspector is not None
        columns = {column['name']: column for column in inspector.get_columns(_TABLE.name)}
        assert set(columns) == set(_TABLE.c.keys())
        for column in _TABLE.c:
            actual = columns[column.name]
            assert actual['nullable'] == column.nullable
            assert actual['type'].compile(dialect=connection.dialect) == column.type.compile(dialect=connection.dialect)
        assert inspector.get_pk_constraint(_TABLE.name)['constrained_columns'] == ['id']
        assert {item['name'] for item in inspector.get_check_constraints(_TABLE.name)} == {
            constraint.name for constraint in _TABLE.constraints if isinstance(constraint, CheckConstraint)
        }
        assert {
            (item['name'], tuple(item['column_names'])) for item in inspector.get_unique_constraints(_TABLE.name)
        } == {
            (constraint.name, tuple(constraint.columns.keys()))
            for constraint in _TABLE.constraints
            if isinstance(constraint, UniqueConstraint)
        }
        assert {
            (item['name'], tuple(item['column_names']))
            for item in inspector.get_indexes(_TABLE.name)
            if not item.get('duplicates_constraint')
        } == {(index.name, tuple(index.columns.keys())) for index in _TABLE.indexes}
        assert {
            (
                tuple(item['constrained_columns']),
                item['referred_table'],
                tuple(item['referred_columns']),
                item['options'].get('ondelete'),
            )
            for item in inspector.get_foreign_keys(_TABLE.name)
        } == {
            ((fk.parent.name,), fk.column.table.name, (fk.column.name,), fk.ondelete) for fk in _TABLE.foreign_keys
        }
        _migrate(connection, downgrade=True)
        assert not inspect(connection).has_table(_TABLE.name)
        _migrate(connection)
        assert inspect(connection).has_table(_TABLE.name)
        assert connection.execute(select(_TABLE)).first() is None


def test_nonempty_downgrade_refused_and_restrictive_foreign_keys(challenge_db):
    with challenge_db.begin() as connection:
        connection.execute(_TABLE.insert().values(**_pending()))
        with pytest.raises(RuntimeError, match='must be retained'):
            _migrate(connection, downgrade=True)
        for table in (IntegrationInstance.__table__, User.__table__):
            with pytest.raises(IntegrityError), connection.begin_nested():
                connection.execute(table.delete().where(table.c.id == 1))
    assert _read(challenge_db)['lifecycle_status'] == 'pending'


@pytest.mark.parametrize(
    'changes',
    [
        {'integration_instance_id': 999},
        {'source_owner_id': 999},
        {
            'lifecycle_status': 'consumed',
            'resolved_by_user_id': 999,
            'resolved_at': _NOW,
            'possession_evidence_ref': 'd' * 64,
        },
        {'lifecycle_status': 'consumed'},
    ],
)
def test_actual_migration_rejects_invalid_rows(challenge_db, changes):
    with pytest.raises(IntegrityError), challenge_db.begin() as connection:
        connection.execute(_TABLE.insert().values(**_pending(**changes)))
    assert _read(challenge_db) is None


def test_global_digest_uniqueness_across_provider_and_scope(challenge_db):
    with challenge_db.begin() as connection:
        connection.execute(_TABLE.insert().values(**_pending()))
    with pytest.raises(IntegrityError), challenge_db.begin() as connection:
        connection.execute(
            _TABLE.insert().values(**_pending(integration_instance_id=2, provider_key='vault', mount='other'))
        )
    assert _read(challenge_db)['provider_key'] == 'openbao'


@pytest.mark.parametrize('provider', ['openbao', 'vault'])
def test_committed_visibility_rollback_and_timezone(challenge_db, provider):
    expected = _pending(integration_instance_id=1 if provider == 'openbao' else 2, provider_key=provider)
    with challenge_db.connect() as writer:
        transaction = writer.begin()
        writer.execute(_TABLE.insert().values(**expected))
        assert _read(challenge_db) is None
        transaction.rollback()
        assert _read(challenge_db) is None
    with challenge_db.begin() as writer:
        writer.execute(_TABLE.insert().values(**expected))
    row = _read(challenge_db)
    assert row is not None
    assert row['issued_at'].utcoffset() is not None
    assert row['issued_at'] == expected['issued_at']
    assert row['expires_at'] == expected['expires_at']


@pytest.mark.parametrize(
    ('first_state', 'second_state', 'commit_first'),
    [
        ('consumed', 'consumed', True),
        ('consumed', 'revoked', True),
        ('revoked', 'consumed', True),
        ('consumed', 'consumed', False),
    ],
)
def test_pending_only_update_under_real_postgresql_contention(challenge_db, first_state, second_state, commit_first):
    expected = _pending()
    with challenge_db.begin() as connection:
        connection.execute(_TABLE.insert().values(**expected))
    started = Event()
    contender_pid = []

    def contend():
        with challenge_db.begin() as second:
            contender_pid.append(second.scalar(text('SELECT pg_backend_pid()')))
            started.set()
            return _resolve(second, expected, second_state)

    with ThreadPoolExecutor(max_workers=1) as executor, challenge_db.connect() as first:
        transaction = first.begin()
        try:
            first_pid = first.scalar(text('SELECT pg_backend_pid()'))
            first_id = _resolve(first, expected, first_state)
            assert first_id is not None
            future = executor.submit(contend)
            assert started.wait(timeout=3)
            # Observe a real row-lock dependency, not just two sequential updates.
            deadline = monotonic() + 4
            with challenge_db.connect() as observer:
                while monotonic() < deadline:
                    blockers = observer.scalar(text('SELECT pg_blocking_pids(:pid)'), {'pid': contender_pid[0]})
                    if first_pid in blockers:
                        break
                    sleep(0.02)
                else:
                    pytest.fail('Expected concurrent PostgreSQL lock contention.')
                assert not future.done()
            assert _read(challenge_db)['lifecycle_status'] == 'pending'
            if commit_first:
                transaction.commit()
            else:
                transaction.rollback()
            assert future.result(timeout=12) == (None if commit_first else first_id)
        finally:
            if transaction.is_active:
                transaction.rollback()
    row = _read(challenge_db)
    assert row is not None
    assert row['lifecycle_status'] == (first_state if commit_first else second_state)
    with challenge_db.begin() as connection:
        assert _resolve(connection, expected, 'consumed') is None
        assert _resolve(connection, expected, 'revoked') is None


def test_wrong_binding_and_expired_consumption_denied(challenge_db):
    expected = _pending()
    with challenge_db.begin() as connection:
        connection.execute(_TABLE.insert().values(**expected))
        assert _resolve(connection, expected | {'mount': 'other'}, 'consumed') is None
        assert _resolve(connection, expected | {'key_sha256': 'e' * 64}, 'consumed') is None
        assert _resolve(connection, expected, 'consumed', at=expected['expires_at']) is None
    assert _read(challenge_db)['lifecycle_status'] == 'pending'
