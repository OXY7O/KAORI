from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from flask import Flask

from app.storage.object_storage.inventory import sync


class _Session:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0
        self.deleted: list[object] = []

    def refresh(self, _system, attribute_names=None) -> None:
        assert attribute_names in (None, ['inventory_observed_at'], ['metadata_json', 'readiness_status', 'enabled'])

    def expire(self, _system, fields=None) -> None:
        assert fields == ['buckets']

    def delete(self, value) -> None:
        self.deleted.append(value)

    def flush(self) -> None:
        return None

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


def _snapshot(*, buckets=(), warnings: int = 0):
    return SimpleNamespace(
        buckets=tuple(buckets), warning_count=warnings, latency_ms=3, usage_stats_mode='disabled',
    )


def _system(*, previously_collected: bool = True):
    old = datetime(2026, 10, 1, tzinfo=UTC)
    return SimpleNamespace(
        id='storage-1', name='Storage One',
        buckets=[SimpleNamespace(name='previous')] if previously_collected else [],
        inventory_observed_at=old if previously_collected else None,
    )


@pytest.fixture
def setup(monkeypatch):
    session = _Session()
    monkeypatch.setattr(sync, 'db', SimpleNamespace(session=session))
    monkeypatch.setattr(sync, '_lock_system_inventory_sync', lambda _system_id: None)
    flask = Flask('storage-empty-reconciliation-test')
    with flask.app_context():
        yield session


def _instance(system):
    return SimpleNamespace(
        integration_instance=SimpleNamespace(enabled=True, lifecycle_status='active', metadata_json={}),
        readiness_status='ready', object_storage_system=system,
    )


def _authorization(system, *, count: int = 1):
    return {
        'system_id': system.id,
        'confirmed_by_user_id': 7,
        'previous_bucket_count': count,
        'previous_inventory_observed_at': system.inventory_observed_at.isoformat(),
    }


def test_first_successfully_observed_zero_bucket_snapshot_is_committed(
    setup: _Session, monkeypatch,
) -> None:
    system = _system(previously_collected=False)
    monkeypatch.setattr(sync, 'collect_instance_bucket_inventory', lambda *_a, **_kw: _snapshot())
    result = sync.sync_object_storage_inventory(_instance(system))
    assert result['total'] == 0
    assert result['deleted'] == 0
    assert setup.commits == 1
    assert setup.rollbacks == 0
    assert system.inventory_observed_at is not None


def test_ordinary_sync_refuses_suspicious_empty_and_keeps_last_good(
    setup: _Session, monkeypatch,
) -> None:
    system = _system()
    previous = system.inventory_observed_at
    monkeypatch.setattr(sync, 'collect_instance_bucket_inventory', lambda *_a, **_kw: _snapshot())
    with pytest.raises(RuntimeError, match='preserved the previous committed snapshot'):
        sync.sync_object_storage_inventory(_instance(system))
    assert setup.commits == 0
    assert setup.rollbacks == 1
    assert not setup.deleted
    assert system.inventory_observed_at == previous


def test_operator_authorized_empty_requires_two_independent_discoveries(
    setup: _Session, monkeypatch,
) -> None:
    system = _system()
    confirmation = _authorization(system)
    calls: list[str] = []

    def collect(_instance, *, usage_stats_mode, **_kw):
        calls.append(usage_stats_mode)
        return _snapshot()

    monkeypatch.setattr(sync, 'collect_instance_bucket_inventory', collect)
    result = sync.sync_object_storage_inventory(_instance(system), empty_reconciliation=confirmation)
    assert calls == ['disabled', 'disabled']
    assert result['total'] == 0
    assert result['deleted'] == 1
    assert len(setup.deleted) == 1
    assert setup.commits == 1
    assert setup.rollbacks == 0
    evidence = result['empty_reconciliation_evidence']
    assert evidence['confirmed_by_user_id'] == 7
    assert evidence['discovery_confirmations'] == 2
    assert evidence['previous_bucket_count'] == 1
    assert evidence['removed_bucket_count'] == 1


@pytest.mark.parametrize('kind', ['changed_snapshot', 'second_discovery_nonempty', 'second_discovery_warning'])
def test_reconciliation_fails_closed_on_drift_or_disagreement(
    setup: _Session, monkeypatch, kind: str,
) -> None:
    system = _system()
    authorization = _authorization(system)
    calls = 0

    def collect(_instance, **_kw):
        nonlocal calls
        calls += 1
        if calls == 2 and kind == 'second_discovery_nonempty':
            return _snapshot(buckets=[SimpleNamespace(name='returned')])
        if calls == 2 and kind == 'second_discovery_warning':
            return _snapshot(warnings=1)
        return _snapshot()

    monkeypatch.setattr(sync, 'collect_instance_bucket_inventory', collect)
    if kind == 'changed_snapshot':
        authorization['previous_bucket_count'] = 2
    with pytest.raises(RuntimeError):
        sync.sync_object_storage_inventory(_instance(system), empty_reconciliation=authorization)
    assert calls == (0 if kind == 'changed_snapshot' else 2)
    assert setup.commits == 0
    assert setup.rollbacks == 1
    assert not setup.deleted
    assert system.inventory_observed_at == datetime(2026, 10, 1, tzinfo=UTC)


@pytest.mark.parametrize('payload', [
    {},
    {'Buckets': None},
    {'Buckets': [], 'IsTruncated': True},
    {'Buckets': [], 'NextContinuationToken': 'more'},
    {'Buckets': [{'Name': ''}]},
    {'Buckets': ['invalid-record']},
])
def test_incomplete_bucket_discovery_is_not_authoritative_empty(payload) -> None:
    from app.integrations.storage.object_storage.providers.minio.client import _bucket_inventory
    from app.integrations.storage.object_storage.providers.minio.contracts import MinioConnectionError

    with pytest.raises(MinioConnectionError, match='incomplete or malformed'):
        _bucket_inventory(payload)
    assert _bucket_inventory({'Buckets': []}) == ()


def test_successful_inventory_sync_commits_current_source_generation(
    setup: _Session, monkeypatch,
) -> None:
    system = _system(previously_collected=False)
    instance = _instance(system)
    instance.integration_instance.metadata_json = {
        'object_storage_connection_generation': 3,
        'object_storage_inventory_generation': 2,
    }
    monkeypatch.setattr(sync, 'collect_instance_bucket_inventory', lambda *_a, **_kw: _snapshot())

    sync.sync_object_storage_inventory(instance)

    assert setup.commits == 1
    assert instance.integration_instance.metadata_json['object_storage_inventory_generation'] == 3


def test_failed_inventory_sync_does_not_promote_previous_source_generation(
    setup: _Session, monkeypatch,
) -> None:
    system = _system()
    instance = _instance(system)
    instance.integration_instance.metadata_json = {
        'object_storage_connection_generation': 3,
        'object_storage_inventory_generation': 2,
    }
    monkeypatch.setattr(sync, 'collect_instance_bucket_inventory', lambda *_a, **_kw: _snapshot())

    with pytest.raises(RuntimeError, match='preserved the previous committed snapshot'):
        sync.sync_object_storage_inventory(instance)

    assert setup.rollbacks == 1
    assert instance.integration_instance.metadata_json['object_storage_inventory_generation'] == 2
