from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.storage.object_storage.analytics import job_adapter, materialization


def test_forecast_worker_blocks_before_creating_pending_snapshot_without_inventory(monkeypatch) -> None:
    system = SimpleNamespace(id='store-1', inventory_observed_at=None)
    monkeypatch.setattr(
        materialization,
        'mark_forecast_pending',
        lambda **_kw: pytest.fail('Cannot persist a pending forecast before first Inventory Sync'),
    )
    with pytest.raises(RuntimeError, match='Inventory Sync Required'):
        materialization.materialize_forecast(
            system=system,
            history_window='30d',
            freshness_minutes=120,
            stale_grace_minutes=4320,
            job_execution_id=3,
        )


def test_forecast_dispatch_excludes_unobserved_system_and_keeps_observed_empty(monkeypatch) -> None:
    never = SimpleNamespace(id='never', name='Never', inventory_observed_at=None)
    observed = SimpleNamespace(
        id='observed',
        name='Observed Empty',
        inventory_observed_at=datetime(2026, 10, 12, tzinfo=UTC),
    )
    monkeypatch.setattr(job_adapter, '_eligible_systems', lambda: ([never, observed], []))
    policy = SimpleNamespace(configuration_json={'history_windows': ['30d']})
    items, diagnostics = job_adapter._work_items(policy, only_due=False)
    assert [item['system_id'] for item in items] == ['observed']
    assert any('Never: Object Storage Inventory Sync Required' in detail for detail in diagnostics)
