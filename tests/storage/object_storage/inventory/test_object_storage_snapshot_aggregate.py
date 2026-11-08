from datetime import UTC, datetime

from app.storage.object_storage.inventory.system_presentation import (
    _overview_snapshot,
    _overview_snapshot_from_counts,
)


def test_sql_aggregate_snapshot_preserves_existing_semantics() -> None:
    latest = datetime.now(UTC)
    rows = [
        {'last_inventory_at': latest, 'status_tone': 'normal'},
        {'last_inventory_at': None, 'status_tone': 'warning'},
    ]
    expected = _overview_snapshot(rows)
    projected = _overview_snapshot_from_counts(
        total_systems=2,
        inventoried_count=1,
        latest=latest,
        missing_count=1,
        stale_count=0,
        provider_exception_count=1,
    )
    assert projected == expected
    assert projected['status'] == 'Review Snapshot'
    assert projected['coverage_label'] == '1 / 2 Systems'


def test_empty_aggregate_snapshot_does_not_claim_collection() -> None:
    state = _overview_snapshot_from_counts(0, 0, None, 0, 0, 0)
    assert state['status'] == 'No Sources'
    assert state['tone'] == 'unknown'
    assert state['coverage_label'] == '0 / 0 Systems'
