"""Additive provider revision migration preserves configured providers (#5365)."""

import importlib

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_provider_revision_upgrade_and_downgrade(monkeypatch) -> None:
    migration = importlib.import_module('migrations.versions.20261128_provider_auth_revision')
    engine = sa.create_engine('sqlite+pysqlite:///:memory:')
    with engine.begin() as connection:
        connection.execute(sa.text('CREATE TABLE identity_providers (id INTEGER PRIMARY KEY, enabled BOOLEAN NOT NULL)'))
        connection.execute(sa.text('INSERT INTO identity_providers VALUES (1, true), (2, false)'))
        monkeypatch.setattr(migration, 'op', Operations(MigrationContext.configure(connection)))
        migration.upgrade()
        assert connection.execute(
            sa.text('SELECT id, enabled, authentication_revision FROM identity_providers ORDER BY id')
        ).all() == [(1, 1, 1), (2, 0, 1)]
        migration.downgrade()
        assert connection.execute(sa.text('SELECT id, enabled FROM identity_providers ORDER BY id')).all() == [
            (1, 1),
            (2, 0),
        ]
    engine.dispose()
