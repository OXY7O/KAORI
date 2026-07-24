from __future__ import annotations

from app.analytics.capacity.service import (
    _empty_capacity_snapshot,
    _safe_int,
    get_capacity_time_step,
)


def test_capacity_time_range_uses_stable_prometheus_steps() -> None:
    assert get_capacity_time_step('1h') == '5m'
    assert get_capacity_time_step('24h') == '1h'
    assert get_capacity_time_step('60d') == '1d'
    assert get_capacity_time_step('unsupported') == '1h'


def test_capacity_snapshot_coercion_fails_closed() -> None:
    assert _safe_int(True) == 1
    assert _safe_int('2.6') == 3
    assert _safe_int('invalid') == 0
    assert _safe_int(None) == 0

    assert _empty_capacity_snapshot() == {
        'cpu_headroom': 0,
        'cpu_unit': 'Cores',
        'memory_headroom': 0,
        'memory_unit': 'GiB',
        'pod_capacity_remaining': 0,
        'pod_unit': 'Pods',
        'recommendation_count': 0,
    }
