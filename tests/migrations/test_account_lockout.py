"""Lockout migration is additive and does not activate protection (#5324)."""

import importlib

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_lockout_upgrade_and_downgrade(monkeypatch: pytest.MonkeyPatch) -> None:
    migration = importlib.import_module('migrations.versions.20261128_account_lockout')
    engine = sa.create_engine('sqlite+pysqlite:///:memory:')
    with engine.begin() as connection:
        connection.execute(sa.text('CREATE TABLE users (id INTEGER PRIMARY KEY)'))
        connection.execute(sa.text(
            'CREATE TABLE authentication_security_policies (id INTEGER PRIMARY KEY, mfa_mode TEXT NOT NULL)'
        ))
        connection.execute(sa.text("INSERT INTO authentication_security_policies VALUES (1, 'required_all')"))
        connection.execute(sa.text('INSERT INTO users VALUES (1)'))
        monkeypatch.setattr(migration, 'op', Operations(MigrationContext.configure(connection)))
        migration.upgrade()
        assert connection.execute(sa.text(
            'SELECT mfa_mode, lockout_mode, lockout_revision FROM authentication_security_policies'
        )).one() == ('required_all', 'disabled', 1)
        assert connection.execute(sa.text('SELECT count(*) FROM authentication_account_lockouts')).scalar_one() == 0
        with pytest.raises(sa.exc.IntegrityError):
            connection.execute(sa.text(
                "UPDATE authentication_security_policies SET lockout_mode='invalid'"
            ))
        connection.execute(sa.text(
            "INSERT INTO authentication_account_lockouts (user_id, policy_revision, failure_times, updated_at) "
            "VALUES (1, 1, '[]', CURRENT_TIMESTAMP)"
        ))
        migration.downgrade()
        assert not sa.inspect(connection).has_table('authentication_account_lockouts')
        assert connection.execute(sa.text('SELECT * FROM authentication_security_policies')).one() == (1, 'required_all')
        assert connection.execute(sa.text('SELECT * FROM users')).one() == (1,)
    engine.dispose()
