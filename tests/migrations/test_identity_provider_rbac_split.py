from __future__ import annotations

import importlib.util
from datetime import UTC, datetime
from pathlib import Path

import pytest
import sqlalchemy as sa

ROOT = Path(__file__).resolve().parents[2]
MIGRATION_PATH = ROOT / 'migrations/versions/20260817_identity_provider_rbac_split.py'


def _load_migration():
    spec = importlib.util.spec_from_file_location('kaori_identity_provider_rbac_split_migration', MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _schema(engine: sa.Engine) -> tuple[sa.Table, sa.Table, sa.Table]:
    metadata = sa.MetaData()
    permissions = sa.Table(
        'permissions',
        metadata,
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('key', sa.String(120), unique=True, nullable=False),
        sa.Column('module', sa.String(80), nullable=False),
        sa.Column('action', sa.String(80), nullable=False),
        sa.Column('description', sa.Text),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    roles = sa.Table(
        'roles',
        metadata,
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('name', sa.String(80), unique=True, nullable=False),
    )
    role_permissions = sa.Table(
        'role_permissions',
        metadata,
        sa.Column('role_id', sa.Integer, nullable=False),
        sa.Column('permission_id', sa.Integer, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('role_id', 'permission_id'),
    )
    metadata.create_all(engine)
    return permissions, roles, role_permissions


def test_upgrade_allows_fresh_unseeded_rbac(monkeypatch: pytest.MonkeyPatch) -> None:
    migration = _load_migration()
    engine = sa.create_engine('sqlite+pysqlite:///:memory:')
    permissions, _, role_permissions = _schema(engine)
    now = datetime.now(UTC)

    with engine.begin() as connection:
        # A fresh migration chain may already contain migration-owned permission
        # rows even though seed-rbac has not created any roles yet.
        connection.execute(
            permissions.insert().values(
                id=1,
                key='users.reset_password',
                module='users',
                action='reset_password',
                description='migration-owned prerequisite',
                created_at=now,
            )
        )
        monkeypatch.setattr(migration.op, 'get_bind', lambda: connection)

        migration.upgrade()

        keys = set(connection.scalars(sa.select(permissions.c.key)))
        assert {
            'identity_providers.view',
            'identity_providers.manage',
            'identity_providers.provision',
        }.issubset(keys)
        assert connection.scalar(sa.select(sa.func.count()).select_from(role_permissions)) == 0


def test_upgrade_copies_legacy_users_manage_role_assignments(monkeypatch: pytest.MonkeyPatch) -> None:
    migration = _load_migration()
    engine = sa.create_engine('sqlite+pysqlite:///:memory:')
    permissions, roles, role_permissions = _schema(engine)
    now = datetime.now(UTC)

    with engine.begin() as connection:
        connection.execute(
            roles.insert(),
            [
                {'id': 1, 'name': 'admin'},
                {'id': 2, 'name': 'custom-access-admin'},
            ],
        )
        connection.execute(
            permissions.insert().values(
                id=1,
                key='users.manage',
                module='users',
                action='manage',
                description='legacy user management permission',
                created_at=now,
            )
        )
        connection.execute(
            role_permissions.insert(),
            [
                {'role_id': 1, 'permission_id': 1, 'created_at': now},
                {'role_id': 2, 'permission_id': 1, 'created_at': now},
            ],
        )
        monkeypatch.setattr(migration.op, 'get_bind', lambda: connection)

        migration.upgrade()

        target_ids = set(
            connection.scalars(
                sa.select(permissions.c.id).where(
                    permissions.c.key.in_(
                        (
                            'identity_providers.view',
                            'identity_providers.manage',
                            'identity_providers.provision',
                        )
                    )
                )
            )
        )
        copied_pairs = set(
            connection.execute(
                sa.select(role_permissions.c.role_id, role_permissions.c.permission_id).where(
                    role_permissions.c.permission_id.in_(target_ids)
                )
            )
        )
        assert copied_pairs == {(role_id, permission_id) for role_id in (1, 2) for permission_id in target_ids}


def test_upgrade_fails_closed_when_seeded_roles_exist_without_users_manage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migration = _load_migration()
    engine = sa.create_engine('sqlite+pysqlite:///:memory:')
    _, roles, _ = _schema(engine)

    with engine.begin() as connection:
        connection.execute(roles.insert().values(id=1, name='admin'))
        monkeypatch.setattr(migration.op, 'get_bind', lambda: connection)

        with pytest.raises(
            RuntimeError,
            match='users.manage must exist before Identity Provider RBAC can be split safely when persisted roles already exist',
        ):
            migration.upgrade()
