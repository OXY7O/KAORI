from datetime import UTC, datetime
from types import SimpleNamespace

from app.artifact_registry.presentation_common import _overview_inventory_kpi_evidence
from app.artifact_registry.sync import (
    _mark_inventory_collection_failed,
    _mark_inventory_collection_started,
)


def _state(*, committed: bool, error: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        status='ready' if committed else 'not_collected',
        last_committed_at=datetime(2026, 10, 5, tzinfo=UTC) if committed else None,
        last_started_at=None,
        last_error=error,
    )


def test_committed_inventory_stays_ready_while_refresh_is_in_flight() -> None:
    state = _state(committed=True, error='previous attempt failed')
    started_at = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)

    _mark_inventory_collection_started(state, started_at=started_at)

    assert state.status == 'ready'
    assert state.last_started_at == started_at
    assert state.last_error == 'previous attempt failed'


def test_committed_inventory_stays_ready_when_refresh_fails() -> None:
    state = _state(committed=True)

    _mark_inventory_collection_failed(state, RuntimeError('provider timeout'))

    assert state.status == 'ready'
    assert state.last_error == 'provider timeout'


def test_initial_inventory_collection_has_no_ready_snapshot_until_commit() -> None:
    state = _state(committed=False)
    started_at = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)

    _mark_inventory_collection_started(state, started_at=started_at)
    assert state.status == 'collecting'

    _mark_inventory_collection_failed(state, RuntimeError('provider unavailable'))
    assert state.status == 'failed'
    assert state.last_error == 'provider unavailable'


def test_dashboard_kpis_require_committed_inventory_before_zero_is_observable() -> None:
    active = SimpleNamespace(id=11)
    historical = SimpleNamespace(integration_instance_id=99, last_committed_at=datetime(2026, 10, 5, tzinfo=UTC))
    pending = SimpleNamespace(integration_instance_id=11, last_committed_at=None)

    assert _overview_inventory_kpi_evidence([active], []) == ([], 'Not Collected')
    assert _overview_inventory_kpi_evidence([active], [pending, historical]) == ([], 'Not Collected')

    committed = SimpleNamespace(integration_instance_id=11, last_committed_at=datetime(2026, 10, 5, tzinfo=UTC))
    assert _overview_inventory_kpi_evidence([active], [committed]) == ([11], 'Committed Inventory')


def test_dashboard_fleet_kpi_evidence_excludes_inactive_and_discloses_partial_coverage() -> None:
    active_providers = [SimpleNamespace(id=11), SimpleNamespace(id=12)]
    committed = SimpleNamespace(integration_instance_id=11, last_committed_at=datetime(2026, 10, 5, tzinfo=UTC))
    pending = SimpleNamespace(integration_instance_id=12, last_committed_at=None)
    retired = SimpleNamespace(integration_instance_id=99, last_committed_at=datetime(2026, 10, 5, tzinfo=UTC))

    assert _overview_inventory_kpi_evidence(active_providers, [committed, pending, retired]) == (
        [11],
        'Partial Inventory (1/2)',
    )
    complete = SimpleNamespace(integration_instance_id=12, last_committed_at=datetime(2026, 10, 5, tzinfo=UTC))
    assert _overview_inventory_kpi_evidence(active_providers, [committed, complete, retired]) == (
        [11, 12],
        'Committed Inventory',
    )
    assert _overview_inventory_kpi_evidence([], [retired]) == ([], 'Not Collected')
