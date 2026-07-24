from __future__ import annotations

import pytest

from app.analytics.storage.service import (
    _count_pvc_risks,
    _empty_storage_snapshot,
    _get_top_storage_namespace,
    _parse_storage_display_to_gib,
)


def test_storage_risk_count_uses_semantic_status_and_utilization_thresholds() -> None:
    rows = [
        {'risk': {'label': 'Critical'}, 'usage_percent': 10, 'status': 'Bound'},
        {'risk': {'label': 'Normal'}, 'usage_percent': 20, 'status': 'Pending'},
        {'risk': {'label': 'Normal'}, 'usage_percent': 75, 'status': 'Bound'},
        {'risk': {'label': 'Normal'}, 'usage_percent': 74.9, 'status': 'Bound'},
        {'risk': {'label': 'Warning'}, 'usage_percent': 99, 'status': 'Lost'},
    ]

    assert _count_pvc_risks(rows) == 4


def test_storage_namespace_rollup_normalizes_display_units() -> None:
    rows = [
        {'namespace': 'payments', 'used': '1 TiB'},
        {'namespace': 'payments', 'used': '512 GiB'},
        {'namespace': 'observability', 'used': '1024 GiB'},
    ]

    assert _parse_storage_display_to_gib('1024 MiB') == pytest.approx(1.0)
    assert _parse_storage_display_to_gib('1 TiB') == pytest.approx(1024.0)
    assert _parse_storage_display_to_gib('invalid') == 0.0
    assert _get_top_storage_namespace(rows) == 'payments'


def test_empty_storage_snapshot_has_stable_report_contract() -> None:
    assert _empty_storage_snapshot() == {
        'pvc_requested': '0 GiB',
        'pvc_used': '0 GiB',
        'pvc_free': '0 GiB',
        'pvc_risk_count': 0,
        'used_percent': 0,
        'free_percent': 0,
        'top_namespace': '-',
        'recommendation_count': 0,
    }
