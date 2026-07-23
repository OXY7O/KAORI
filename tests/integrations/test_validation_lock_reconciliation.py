from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.integrations.validation import state


class FakeRedis:
    def __init__(self, values: dict[str, str] | None = None) -> None:
        self.values = dict(values or {})

    def get(self, key: str) -> str | None:
        return self.values.get(key)

    def eval(self, script: str, key_count: int, *args: Any) -> int:
        keys = [str(value) for value in args[:key_count]]
        argv = [str(value) for value in args[key_count:]]
        if script == state._COMPARE_DELETE_SCRIPT:
            key = keys[0]
            owner = argv[0]
            if self.values.get(key) == owner:
                del self.values[key]
                return 1
            return 0
        if script == state._CLAIM_SCRIPT:
            if any(key in self.values for key in keys):
                return 0
            self.values[keys[0]] = argv[0]
            return 1
        raise AssertionError('Unexpected Redis script')


@pytest.mark.parametrize('terminal_status', ['succeeded', 'failed', 'canceled', 'expired'])
def test_terminal_job_lock_is_reclaimed(monkeypatch: pytest.MonkeyPatch, terminal_status: str) -> None:
    key = 'kaori:integration-validation:lock:prometheus:full_validation:9'
    client = FakeRedis({key: 'old-task'})
    monkeypatch.setattr(
        'app.jobs.service.get_job_by_task_id',
        lambda task_id: SimpleNamespace(status=terminal_status) if task_id == 'old-task' else None,
    )

    assert state._release_stale_validation_lock(client, key) is True
    assert client.get(key) is None


def test_missing_canonical_job_lock_is_reclaimed(monkeypatch: pytest.MonkeyPatch) -> None:
    key = 'kaori:integration-validation:lock:alertmanager:runtime_refresh:4'
    client = FakeRedis({key: 'missing-task'})
    monkeypatch.setattr('app.jobs.service.get_job_by_task_id', lambda task_id: None)

    assert state._release_stale_validation_lock(client, key) is True
    assert client.get(key) is None


@pytest.mark.parametrize('active_status', ['queued', 'running', 'retrying', 'cancel_requested'])
def test_active_job_lock_is_preserved(monkeypatch: pytest.MonkeyPatch, active_status: str) -> None:
    key = 'kaori:integration-validation:lock:kubernetes:full_validation:3'
    client = FakeRedis({key: 'active-task'})
    monkeypatch.setattr(
        'app.jobs.service.get_job_by_task_id',
        lambda task_id: SimpleNamespace(status=active_status),
    )

    assert state._release_stale_validation_lock(client, key) is False
    assert client.get(key) == 'active-task'


def test_claim_reconciles_terminal_owner_before_acquiring(monkeypatch: pytest.MonkeyPatch) -> None:
    key = 'kaori:integration-validation:lock:prometheus:full_validation:12'
    client = FakeRedis({key: 'terminal-task'})
    monkeypatch.setattr(state, '_redis_client', lambda: client)
    monkeypatch.setattr(state, '_lock_ttl_seconds', lambda: 300)
    monkeypatch.setattr(state, 'store_validation_metadata', lambda **kwargs: None)
    monkeypatch.setattr(
        'app.jobs.service.get_job_by_task_id',
        lambda task_id: SimpleNamespace(status='failed') if task_id == 'terminal-task' else None,
    )

    acquired = state.claim_validation_job(
        task_id='new-task',
        provider_type='prometheus',
        operation='full_validation',
        instance_id=12,
        binding_id=None,
        metadata={'task_id': 'new-task'},
    )

    assert acquired is True
    assert client.get(key) == 'new-task'
