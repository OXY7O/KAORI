from datetime import UTC, datetime, timedelta

from app.storage_inventory.presentation import (
    OBJECT_STORAGE_INVENTORY_FRESHNESS_HOURS,
    _compatibility_profile_display,
    _inventory_guidance,
    _inventory_signals,
    _is_stale,
    _release_display,
    _snapshot_status,
)


def test_snapshot_status_distinguishes_current_stale_and_missing() -> None:
    now = datetime.now(UTC)
    assert _snapshot_status(None) == ('Not Collected', 'warning')
    assert _snapshot_status(now) == ('Current', 'normal')
    assert _snapshot_status(now - timedelta(hours=OBJECT_STORAGE_INVENTORY_FRESHNESS_HOURS + 1)) == (
        'Stale',
        'warning',
    )


def test_is_stale_accepts_naive_database_timestamps() -> None:
    now = datetime.now(UTC)
    naive_old = (now - timedelta(hours=OBJECT_STORAGE_INVENTORY_FRESHNESS_HOURS + 1)).replace(tzinfo=None)
    assert _is_stale(naive_old, now=now) is True


def test_inventory_signals_keep_provider_and_snapshot_conditions_explicit() -> None:
    row = {
        'status_tone': 'critical',
        'last_inventory_at': None,
    }
    signals = _inventory_signals(row)
    labels = {signal['label'] for signal in signals}
    assert labels == {'Provider Attention', 'Inventory Not Collected'}
    guidance = _inventory_guidance(row, signals)
    assert guidance['title'] == 'Review Provider Readiness'


def test_object_storage_release_and_profile_labels_are_operator_friendly() -> None:
    assert _release_display('RELEASE.2024-08-03T04-33-23Z') == '2024-08-03'
    assert _compatibility_profile_display('minio-release-2024-08-03') == 'MinIO 2024-08-03'
    assert _compatibility_profile_display('astor-release-2025-01-16') == 'AStor 2025-01-16'


def test_unknown_release_and_profile_values_remain_visible() -> None:
    assert _release_display('2026.1') == '2026.1'
    assert _compatibility_profile_display('vendor_profile_v2') == 'Vendor Profile V2'
