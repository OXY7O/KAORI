"""Explicit routing mode migration retains the previous no-policy behavior."""

import importlib

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_alert_delivery_mode_migration_seed_constraints_and_downgrade(monkeypatch):
    migration = importlib.import_module('migrations.versions.20261128_alert_delivery_mode')
    engine = sa.create_engine('sqlite+pysqlite:///:memory:')
    try:
        with engine.begin() as connection:
            monkeypatch.setattr(migration, 'op', Operations(MigrationContext.configure(connection)))
            migration.upgrade()
            row = connection.execute(sa.text('SELECT id, mode, revision FROM alert_delivery_modes')).one()
            assert tuple(row) == (1, 'channel_defaults', 1)
            for statement in (
                "UPDATE alert_delivery_modes SET mode = 'invalid'",
                "UPDATE alert_delivery_modes SET revision = 0",
                "INSERT INTO alert_delivery_modes VALUES (2, 'channel_defaults', 1, CURRENT_TIMESTAMP)",
            ):
                with pytest.raises(sa.exc.IntegrityError), connection.begin_nested():
                    connection.execute(sa.text(statement))
            migration.downgrade()
            assert not sa.inspect(connection).has_table('alert_delivery_modes')
    finally:
        engine.dispose()
