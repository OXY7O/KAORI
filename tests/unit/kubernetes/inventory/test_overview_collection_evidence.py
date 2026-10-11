from datetime import UTC, datetime

from app.kubernetes.inventory.overview import (
    _collection_evidence_complete,
    _collection_evidence_exceptions,
    _connection_presentation,
    _build_inventory_signals,
    _inventory_guidance,
)


def test_collection_evidence_missing_or_partial_is_never_complete() -> None:
    assert not _collection_evidence_complete(None)
    assert not _collection_evidence_complete({})
    assert not _collection_evidence_complete({'inventory.pods': 'Collected', 'inventory.services': 'Failed'})
    assert _collection_evidence_complete({'inventory.pods': 'Collected', 'inventory.services': 'Collected'})


def test_missing_and_failed_collection_exceptions_are_explicit() -> None:
    observed = datetime.now(UTC)
    assert _collection_evidence_exceptions({}, observed) == [('inventory', 'Not Reported')]
    assert _collection_evidence_exceptions({}, None) == []
    assert _collection_evidence_exceptions(
        {'inventory.pods': 'Collected', 'inventory.services': 'Failed'}, observed
    ) == [('inventory.services', 'Failed')]


def test_unknown_connection_state_is_not_fabricated_disconnection() -> None:
    assert _connection_presentation('connected') == ('Connected', 'normal')
    assert _connection_presentation('failed') == ('Disconnected', 'critical')
    assert _connection_presentation('unknown') == ('Not Observed', 'unknown')
    assert _connection_presentation(None) == ('Not Observed', 'unknown')


def test_partial_collection_flags_overview_and_operator_guidance() -> None:
    observed = datetime.now(UTC)
    signals = _build_inventory_signals(
        connected=True,
        synced_at=observed,
        connection_status='connected',
        collection_evidence={'inventory.pods': 'Failed'},
        node_count=1,
        workload_count=0,
        pod_count=0,
        storage_count=0,
    )
    assert any(item['label'] == 'Collection Incomplete' for item in signals)
    guidance = _inventory_guidance(
        connected=True, synced_at=observed, signals=signals,
        connection_status='connected', collection_evidence={'inventory.pods': 'Failed'},
    )
    assert guidance['title'] == 'Review Collection Coverage'
    assert guidance['tone'] == 'warning'
