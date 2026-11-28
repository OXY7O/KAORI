"""Migration preserves enrolled factors and discards pending setup on downgrade (#5346)."""

import importlib

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_enrollment_owner_upgrade_and_safe_downgrade(monkeypatch) -> None:
    migration = importlib.import_module('migrations.versions.20261128_mfa_enrollment_owner')
    engine = sa.create_engine('sqlite+pysqlite:///:memory:')
    with engine.begin() as connection:
        connection.execute(
            sa.text('CREATE TABLE authentication_mfa_factors (id INTEGER PRIMARY KEY, enabled BOOLEAN NOT NULL)')
        )
        connection.execute(sa.text('INSERT INTO authentication_mfa_factors VALUES (1, true), (2, false)'))
        monkeypatch.setattr(migration, 'op', Operations(MigrationContext.configure(connection)))
        migration.upgrade()
        rows = connection.execute(
            sa.text('SELECT enrollment_generation, enrollment_authenticated FROM authentication_mfa_factors')
        ).all()
        assert [tuple(row) for row in rows] == [(None, None), (None, None)]
        migration.downgrade()
        assert connection.execute(sa.text('SELECT id FROM authentication_mfa_factors')).scalars().all() == [1]
        columns = {column['name'] for column in sa.inspect(connection).get_columns('authentication_mfa_factors')}
        assert columns == {'id', 'enabled'}
    engine.dispose()
