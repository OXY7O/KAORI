"""Vault registry persistence invariants for first registration and failed flush.

These bounded tests use a fake SQLAlchemy session, not a live database.
The actual PostgreSQL constraint and Activity Audit are Human UAT gates.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.integrations.secrets_management.secrets_pki.providers.vault.application import service
from app.integrations.secrets_management.secrets_pki.providers.vault.application.types import VaultConnectionInput


class _FakeQuery:
    def filter(self, *args: object) -> _FakeQuery:
        return self

    def first(self) -> None:
        return None


class _FakeIdentity:
    query = _FakeQuery()
    integration_type = ''
    name = ''
    id = 0

    def __init__(self) -> None:
        self.id = 0


class _FakeVault:
    def __init__(self) -> None:
        self.integration_instance_id: int | None = None


class _FakeSession:
    def __init__(self, *, fail_flush: bool = False) -> None:
        self.added: list[object] = []
        self.fail_flush = fail_flush
        self.flush_calls = 0
        self.rollback_calls = 0
        self.commit_calls = 0
        self.name_at_flush: str | None = None

    def add(self, record: object) -> None:
        self.added.append(record)

    def flush(self) -> None:
        self.flush_calls += 1
        identity = next(item for item in self.added if isinstance(item, _FakeIdentity))
        self.name_at_flush = identity.name
        assert identity.integration_type == 'secrets_pki'
        assert identity.provider_key == 'vault'
        assert identity.adapter_key == 'vault_http_v1'
        assert identity.name == 'Vault X300'
        if self.fail_flush:
            raise SQLAlchemyError('simulated database constraint failure')
        identity.id = 17

    def rollback(self) -> None:
        self.rollback_calls += 1

    def commit(self) -> None:
        self.commit_calls += 1


def _input() -> VaultConnectionInput:
    return VaultConnectionInput(
        name='Vault X300',
        environment='development',
        description='Local Vault integration',
        endpoint='https://vault.example.internal:8200',
        namespace=None,
        auth_mount='approle',
        role_id='test-only-role',
        secret_id='test-only-secret',
        timeout=5,
        enabled=True,
    )


def _prepare(monkeypatch: pytest.MonkeyPatch, session: _FakeSession) -> None:
    monkeypatch.setattr(service, 'db', SimpleNamespace(session=session))
    monkeypatch.setattr(service, 'IntegrationInstance', _FakeIdentity)
    monkeypatch.setattr(service, 'VaultInstance', _FakeVault)
    monkeypatch.setattr(service, 'validate_vault_endpoint', lambda endpoint: endpoint)
    monkeypatch.setattr(service, 'validate_auth_mount', lambda mount: mount)


def test_vault_registration_initializes_required_identity_before_first_flush(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _FakeSession()
    _prepare(monkeypatch, session)

    instance = service.save_connection(_input())

    assert session.flush_calls == 1
    assert session.name_at_flush == 'Vault X300'
    assert session.commit_calls == 1
    assert session.rollback_calls == 0
    assert instance.integration_instance_id == 17
    identity = next(obj for obj in session.added if isinstance(obj, _FakeIdentity))
    assert identity.name == 'Vault X300'
    assert identity.environment == 'development'
    assert identity.metadata_json['asset_type'] == 'vault_instance'
    assert identity.metadata_json['asset_key'] == '17'


def test_vault_failed_identity_flush_rolls_back_before_audit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _FakeSession(fail_flush=True)
    _prepare(monkeypatch, session)

    with pytest.raises(SQLAlchemyError, match='simulated database constraint failure'):
        service.save_connection(_input())

    assert session.flush_calls == 1
    assert session.commit_calls == 0
    assert session.rollback_calls == 1


def test_vault_existing_connection_update_does_not_insert_another_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _FakeSession()
    _prepare(monkeypatch, session)
    values = _input()
    identity = _FakeIdentity()
    identity.id = 17
    identity.name = values.name
    identity.readiness_status = 'ready'
    instance = _FakeVault()
    instance.integration_instance_id = identity.id
    instance.integration_instance = identity
    instance.endpoint = values.endpoint
    instance.namespace = values.namespace
    instance.auth_mount = values.auth_mount
    instance.role_id = values.role_id
    instance.secret_id = values.secret_id
    instance.timeout = values.timeout
    instance.kv2_mounts = []
    instance.pki_mounts = []
    instance.pki_stored_certs_enabled = False

    updated = service.save_connection(values, existing=instance)

    assert updated is instance
    assert session.flush_calls == 0
    assert session.rollback_calls == 0
    assert session.commit_calls == 1
    assert identity.readiness_status == 'ready'
    assert identity.metadata_json['asset_key'] == '17'
