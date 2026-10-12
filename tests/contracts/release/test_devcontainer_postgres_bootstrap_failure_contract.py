"""Negative admission tests for DevContainer-only PostgreSQL role boundaries.

These tests never open a database or consume Docker secrets.
"""
from __future__ import annotations

import sys

import pytest

from scripts.devcontainer.bootstrap_runtime_role import (
    _read_secret,
    main as bootstrap_roles,
)
from scripts.devcontainer.initialize_database import main as migrate_schema


def test_first_bootstrap_rejects_prod_before_database_access(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('APP_ENV', 'production')
    with pytest.raises(RuntimeError, match='APP_ENV must be development'):
        bootstrap_roles()


def test_first_bootstrap_rejects_legacy_superuser_secret_in_app_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv('APP_ENV', 'development')
    monkeypatch.delenv('KAORI_DB_MIGRATION_URL', raising=False)
    monkeypatch.setenv('POSTGRES_PASSWORD', 'insecure-application-environment')
    with pytest.raises(RuntimeError, match='move legacy POSTGRES_PASSWORD'):
        bootstrap_roles()


def test_first_bootstrap_rejects_migration_credential_in_one_shot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv('APP_ENV', 'development')
    monkeypatch.setenv('KAORI_DB_MIGRATION_URL', 'not-authorized-here')
    with pytest.raises(RuntimeError, match='migration URL is forbidden'):
        bootstrap_roles()


def test_first_bootstrap_rejects_password_file_outside_docker_secrets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv('UNTRUSTED_POSTGRES_SECRET_FILE', '/tmp/unsafe')
    with pytest.raises(RuntimeError, match='mounted Docker secret'):
        _read_secret('UNTRUSTED_POSTGRES_SECRET_FILE')


def test_explicit_schema_migration_rejects_production_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv('APP_ENV', 'production')
    monkeypatch.setattr(sys, 'argv', ['initialize_database'])
    with pytest.raises(RuntimeError, match='only the local development runtime'):
        migrate_schema()


def test_explicit_schema_migration_rejects_ambient_privileged_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv('APP_ENV', 'development')
    monkeypatch.setenv('KAORI_DB_MIGRATION_URL', 'must-not-be-persisted')
    monkeypatch.setattr(sys, 'argv', ['initialize_database'])
    with pytest.raises(RuntimeError, match='remove ambient migration credentials'):
        migrate_schema()
