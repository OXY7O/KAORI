"""Migration regression for the committed session lifecycle (#5284)."""

import importlib

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_upgrade_defaults_and_downgrade_revocation(monkeypatch) -> None:
    migration = importlib.import_module('migrations.versions.20261128_auth_session_expiry')
    engine = sa.create_engine('sqlite+pysqlite:///:memory:')
    with engine.begin() as connection:
        connection.execute(sa.text('CREATE TABLE users (id INTEGER PRIMARY KEY, auth_session_version INTEGER NOT NULL)'))
        connection.execute(sa.text('CREATE TABLE authentication_security_policies (id INTEGER PRIMARY KEY)'))
        connection.execute(sa.text('INSERT INTO users VALUES (1, 8)'))
        connection.execute(sa.text('INSERT INTO authentication_security_policies VALUES (1)'))
        monkeypatch.setattr(migration, 'op', Operations(MigrationContext.configure(connection)))

        migration.upgrade()
        timestamps = connection.execute(
            sa.text('SELECT auth_session_issued_at, auth_session_activity_at FROM users WHERE id = 1')
        ).one()
        assert tuple(timestamps) == (None, None)
        policy = connection.execute(sa.text('SELECT * FROM authentication_security_policies WHERE id = 1')).mappings().one()
        assert policy['session_privileged_idle_minutes'] == 15
        assert policy['session_privileged_absolute_hours'] == 4
        assert policy['session_regular_idle_minutes'] == 30
        assert policy['session_regular_absolute_hours'] == 8
        assert policy['session_warning_minutes'] == 2
        assert policy['session_regular_remember']

        migration.downgrade()
        assert connection.execute(sa.text('SELECT auth_session_version FROM users WHERE id = 1')).scalar_one() == 9
        columns = {column['name'] for column in sa.inspect(connection).get_columns('users')}
        assert 'auth_session_issued_at' not in columns
        assert 'auth_session_activity_at' not in columns
    engine.dispose()
