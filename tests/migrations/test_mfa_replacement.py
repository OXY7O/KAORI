"""Replacement migration never overwrites the active factor (#5357)."""

import importlib

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_replacement_upgrade_and_downgrade_preserve_active_factor(monkeypatch) -> None:
    migration = importlib.import_module('migrations.versions.20261128_mfa_replacement')
    engine = sa.create_engine('sqlite+pysqlite:///:memory:')
    with engine.begin() as connection:
        connection.execute(sa.text(
            'CREATE TABLE authentication_mfa_factors (id INTEGER PRIMARY KEY, enabled BOOLEAN, totp_secret TEXT)'
        ))
        connection.execute(sa.text("INSERT INTO authentication_mfa_factors VALUES (1, true, 'existing-test-ciphertext')"))
        monkeypatch.setattr(migration, 'op', Operations(MigrationContext.configure(connection)))
        migration.upgrade()
        assert connection.execute(
            sa.text('SELECT replacement_totp_secret, replacement_generation FROM authentication_mfa_factors')
        ).one() == (None, None)
        connection.execute(sa.text("UPDATE authentication_mfa_factors SET replacement_totp_secret = 'pending-test'"))
        migration.downgrade()
        assert connection.execute(
            sa.text('SELECT id, enabled, totp_secret FROM authentication_mfa_factors')
        ).one() == (1, 1, 'existing-test-ciphertext')
    engine.dispose()
