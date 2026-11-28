"""Singleton initialization preserves other authentication settings (#5326)."""

import importlib

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


@pytest.mark.parametrize('existing', (False, True))
def test_singleton_initialization_is_non_destructive(monkeypatch: pytest.MonkeyPatch, existing: bool) -> None:
    migration = importlib.import_module('migrations.versions.20261128_lockout_governance')
    engine = sa.create_engine('sqlite+pysqlite:///:memory:')
    with engine.begin() as connection:
        connection.execute(sa.text(
            "CREATE TABLE authentication_security_policies (id INTEGER PRIMARY KEY, "
            "mfa_mode TEXT NOT NULL DEFAULT 'disabled', bot_mode TEXT NOT NULL DEFAULT 'disabled', "
            "lockout_mode TEXT NOT NULL DEFAULT 'disabled', lockout_revision BIGINT NOT NULL DEFAULT 1, "
            "updated_at DATETIME NOT NULL)"
        ))
        if existing:
            connection.execute(sa.text(
                "INSERT INTO authentication_security_policies VALUES "
                "(1, 'required_all', 'always', 'monitor_only', 3, CURRENT_TIMESTAMP)"
            ))
        monkeypatch.setattr(migration, 'op', Operations(MigrationContext.configure(connection)))
        migration.upgrade()
        migration.upgrade()
        expected = (1, 'required_all', 'always', 'monitor_only', 3) if existing else (1, 'disabled', 'disabled', 'disabled', 1)
        statement = sa.text(
            'SELECT id, mfa_mode, bot_mode, lockout_mode, lockout_revision FROM authentication_security_policies'
        )
        assert tuple(connection.execute(statement).one()) == expected
        migration.downgrade()
        assert tuple(connection.execute(statement).one()) == expected
    engine.dispose()
