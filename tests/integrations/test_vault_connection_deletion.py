"""Guarded Vault registration deletion preserves independent committed evidence."""

from __future__ import annotations

from inspect import unwrap
from types import SimpleNamespace
from typing import Any

import pytest
from flask import Flask

from app.integrations.deletion import DeletionBlocked, DeletionGuard
from app.integrations.secrets_management.secrets_pki.providers.vault.application import routes, service


DEPENDENCY_NAMES = (
    'IntegrationBinding',
    'SecretProviderRepresentation',
    'SecretInventoryCollectionState',
    'PKIIssuerIdentity',
    'PKIIssuerCollectionState',
    'PKIStoredCertificateObservation',
    'PKIStoredCertificateCollectionState',
)


def _provider_instance() -> SimpleNamespace:
    return SimpleNamespace(
        id=15,
        integration_instance_id=99,
        name='Vault Example',
        integration_instance=object(),
    )


def _guard_dependencies(monkeypatch: pytest.MonkeyPatch, *, nonempty: str = '') -> list[int]:
    scoped: list[int] = []

    def query_model(name: str) -> SimpleNamespace:
        def filter_by(**kwargs: Any) -> SimpleNamespace:
            scoped.append(kwargs['integration_instance_id'])
            return SimpleNamespace(count=lambda: 2 if name == nonempty else 0)

        return SimpleNamespace(query=SimpleNamespace(filter_by=filter_by))

    for model_name in DEPENDENCY_NAMES:
        monkeypatch.setattr(service, model_name, query_model(model_name))
    return scoped


@pytest.mark.parametrize('nonempty', DEPENDENCY_NAMES)
def test_vault_deletion_guard_blocks_each_retained_fk_dependency(
    monkeypatch: pytest.MonkeyPatch,
    nonempty: str,
) -> None:
    scoped = _guard_dependencies(monkeypatch, nonempty=nonempty)
    monkeypatch.setattr(
        service,
        'provider_deletion_guard',
        lambda **kwargs: DeletionGuard(blocked=False, reasons=()),
    )

    guard = service.vault_connection_deletion_guard(_provider_instance())

    assert guard.blocked is True
    assert '2 ' in guard.message
    assert len(scoped) == len(DEPENDENCY_NAMES)
    assert all(value == 99 for value in scoped)


def test_vault_deletion_guard_blocks_active_jobs_without_inventory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _guard_dependencies(monkeypatch)
    monkeypatch.setattr(
        service,
        'provider_deletion_guard',
        lambda **kwargs: DeletionGuard(
            blocked=True, reasons=('One active job still references this connection.',), active_jobs=1
        ),
    )
    guard = service.vault_connection_deletion_guard(_provider_instance())

    assert guard.blocked
    assert guard.active_jobs == 1
    assert 'active job' in guard.message


def test_vault_deletion_service_rechecks_guard_under_admission_lock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instance = _provider_instance()
    events: list[str] = []
    monkeypatch.setattr(
        service,
        'acquire_resource_admission_locks',
        lambda *keys: events.append('lock:' + keys[0]),
    )
    monkeypatch.setattr(
        service,
        'vault_connection_deletion_guard',
        lambda item: (
            events.append('guard')
            or DeletionGuard(blocked=True, reasons=('Retained PKI evidence.',))
        ),
    )
    monkeypatch.setattr(
        service,
        'db',
        SimpleNamespace(session=SimpleNamespace(delete=lambda obj: events.append('deleted'))),
    )

    with pytest.raises(DeletionBlocked):
        service.delete_vault_connection(instance)

    assert events == ['lock:integration:secrets_pki:99', 'guard']


def test_vault_deletion_service_removes_only_provider_and_canonical_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instance = _provider_instance()
    events: list[str] = []
    monkeypatch.setattr(service, 'acquire_resource_admission_locks', lambda *keys: events.append('lock'))
    monkeypatch.setattr(
        service, 'vault_connection_deletion_guard',
        lambda item: (events.append('guard') or DeletionGuard(blocked=False, reasons=())),
    )
    monkeypatch.setattr(
        service,
        'db',
        SimpleNamespace(
            session=SimpleNamespace(
                delete=lambda obj: events.append('provider' if obj is instance else 'canonical'),
                flush=lambda: events.append('flush'),
                commit=lambda: events.append('commit'),
                rollback=lambda: events.append('rollback'),
            )
        ),
    )

    service.delete_vault_connection(instance)

    assert events == ['lock', 'guard', 'provider', 'flush', 'canonical', 'commit']


def _web_app(monkeypatch: pytest.MonkeyPatch) -> Flask:
    app = Flask(__name__)
    app.config.update(SECRET_KEY='vault-deletion-test')
    app.register_blueprint(routes.vault_bp)
    monkeypatch.setattr(routes, 'current_user', SimpleNamespace(id=42))
    monkeypatch.setattr(routes, '_instance_or_404', lambda instance_id: _provider_instance())
    return app


@pytest.mark.parametrize('outcome', ['success', 'blocked', 'failed'])
def test_vault_delete_endpoint_returns_safe_feedback(
    monkeypatch: pytest.MonkeyPatch,
    outcome: str,
) -> None:
    app = _web_app(monkeypatch)
    audit: list[dict[str, Any]] = []
    rollbacks: list[str] = []
    monkeypatch.setattr(
        routes,
        'db',
        SimpleNamespace(session=SimpleNamespace(rollback=lambda: rollbacks.append('rolled back'))),
    )

    def delete(instance: Any) -> None:
        if outcome == 'blocked':
            raise DeletionBlocked(DeletionGuard(blocked=True, reasons=('Active Vault evidence.',)))
        if outcome == 'failed':
            from sqlalchemy.exc import IntegrityError

            raise IntegrityError('DELETE', {}, Exception('private provider data'))

    monkeypatch.setattr(routes, 'delete_vault_connection', delete)
    monkeypatch.setattr(routes, 'record_operational_activity', lambda **kwargs: audit.append(kwargs))
    with app.test_request_context(
        '/integrations/secrets-management/secrets-pki/vault/instances/15/delete',
        method='POST',
    ):
        response = unwrap(routes.delete_instance)(15)

    assert response.status_code == 302
    assert len(audit) == 1
    expected_status = {
        'success': 'success',
        'blocked': 'warning',
        'failed': 'error',
    }[outcome]
    assert audit[0]['status'] == expected_status
    assert audit[0]['queue_feedback'] is True
    assert 'private provider data' not in str(audit)
    assert rollbacks == (['rolled back'] if outcome == 'failed' else [])
    if outcome == 'success':
        assert response.location.endswith('/vault/?tab=registry')
    else:
        assert response.location.endswith('/instances/15#inventory')
