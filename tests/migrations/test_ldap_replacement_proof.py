"""Downgrade discards provider-bound pending material, never active factor (#5374)."""

import importlib

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_ldap_replacement_proof_migration(monkeypatch: pytest.MonkeyPatch) -> None:
    migration = importlib.import_module('migrations.versions.20261128_ldap_replacement_proof')
    engine = sa.create_engine('sqlite+pysqlite:///:memory:')
    with engine.begin() as connection:
        connection.execute(sa.text(
            'CREATE TABLE authentication_mfa_factors (id INTEGER PRIMARY KEY, totp_secret TEXT, '
            'replacement_totp_secret TEXT, replacement_generation BIGINT, replacement_expires_at DATETIME)'
        ))
        connection.execute(sa.text(
            "INSERT INTO authentication_mfa_factors VALUES (1, 'active', 'local-pending', 7, NULL), "
            "(2, 'active', 'ldap-pending', 7, NULL)"
        ))
        monkeypatch.setattr(migration, 'op', Operations(MigrationContext.configure(connection)))
        migration.upgrade()
        connection.execute(sa.text(
            "UPDATE authentication_mfa_factors SET replacement_provider_proof = '{}' WHERE id = 2"
        ))
        migration.downgrade()
        assert connection.execute(sa.text(
            'SELECT id, totp_secret, replacement_totp_secret FROM authentication_mfa_factors ORDER BY id'
        )).all() == [(1, 'active', 'local-pending'), (2, 'active', None)]
    engine.dispose()
