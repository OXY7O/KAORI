from __future__ import annotations

from app.storage.object_storage.analytics.analysis import (
    capacity_posture,
    compare_evidence,
    derive_headroom,
    error_ratio,
    forecast_posture,
    performance_posture,
    summarize_trend,
)
from app.storage.object_storage.analytics.recommendations import (
    build_capacity_recommendations,
    build_forecast_recommendations,
    build_performance_recommendations,
)


def test_headroom_prefers_direct_metric_and_derives_when_absent() -> None:
    direct, direct_source = derive_headroom(100.0, 35.0, 65.0)
    derived, derived_source = derive_headroom(100.0, None, 65.0)

    assert direct == 35.0
    assert direct_source == 'Operational Metric'
    assert derived == 35.0
    assert derived_source == 'Derived from Capacity − Usage'


def test_error_ratio_distinguishes_zero_traffic_from_zero_errors() -> None:
    assert error_ratio(5.0, 100.0) == 5.0
    assert error_ratio(0.0, 0.0) == 0.0
    assert error_ratio(None, 0.0) is None


def test_trend_summary_uses_selected_window_slope() -> None:
    summary = summarize_trend(
        [
            {'timestamp': 0.0, 'value': 100.0},
            {'timestamp': 86400.0, 'value': 125.0},
            {'timestamp': 172800.0, 'value': 150.0},
        ]
    )

    assert summary.sample_count == 3
    assert summary.delta == 50.0
    assert summary.delta_percent == 50.0
    assert summary.growth_per_day == 25.0
    assert summary.direction == 'increasing'


def test_reconciliation_uses_review_band_without_claiming_source_failure() -> None:
    aligned = compare_evidence(100.0, 98.0)
    review = compare_evidence(100.0, 90.0)
    material = compare_evidence(100.0, 70.0)

    assert aligned.status == 'Within Baseline'
    assert aligned.tone == 'normal'
    assert review.status == 'Review Drift'
    assert review.tone == 'warning'
    assert material.status == 'Material Drift'
    assert material.tone == 'warning'


def test_capacity_posture_thresholds_are_explicit() -> None:
    assert capacity_posture(None).tone == 'unknown'
    assert capacity_posture(84.9).tone == 'normal'
    assert capacity_posture(85.0).tone == 'warning'
    assert capacity_posture(95.0).tone == 'critical'


def test_performance_posture_prioritizes_availability_and_error_pressure() -> None:
    assert performance_posture(error_percent=None, waiting=None, offline_nodes=None).tone == 'unknown'
    assert performance_posture(error_percent=1.0, waiting=0.0, offline_nodes=0.0).tone == 'normal'
    assert performance_posture(error_percent=5.0, waiting=0.0, offline_nodes=0.0).tone == 'warning'
    assert performance_posture(error_percent=1.0, waiting=0.0, offline_nodes=1.0).tone == 'critical'


def test_forecast_posture_keeps_linear_projection_as_planning_boundary() -> None:
    assert forecast_posture(None, None).tone == 'unknown'
    assert forecast_posture(-1.0, None).status == 'Stable'
    assert forecast_posture(1.0, 20.0).tone == 'critical'
    assert forecast_posture(1.0, 60.0).tone == 'warning'
    assert forecast_posture(1.0, 120.0).tone == 'normal'


def test_capacity_recommendations_change_with_headroom_pressure() -> None:
    normal = build_capacity_recommendations(
        {
            'utilization': 40.0,
            'capacity_usage': {
                'capacity_evidence_available': True,
                'quota_critical_count': 0,
                'quota_warning_count': 0,
                'quota_unknown_count': 0,
            },
            'usage_trend_summary': {'direction': 'stable'},
        }
    )
    pressured = build_capacity_recommendations(
        {
            'utilization': 96.0,
            'capacity_usage': {
                'capacity_evidence_available': True,
                'quota_critical_count': 1,
                'quota_warning_count': 0,
                'quota_unknown_count': 0,
            },
            'usage_trend_summary': {'direction': 'increasing'},
        }
    )

    assert pressured != normal
    assert any(item['priority'] in {'P1', 'P2'} for item in pressured)
    assert any(item['source_label'] == 'Capacity & Usage' for item in pressured)


def test_performance_recommendations_change_with_error_pressure() -> None:
    normal = build_performance_recommendations(
        {
            'error_ratio': 0.5,
            'waiting': 0.0,
            'offline_nodes': 0.0,
            'performance': {'bucket_count': 1, 'bucket_request_evidence_count': 1},
        }
    )
    pressured = build_performance_recommendations(
        {
            'error_ratio': 8.0,
            'waiting': 3.0,
            'offline_nodes': 0.0,
            'performance': {'bucket_count': 1, 'bucket_request_evidence_count': 1},
        }
    )

    assert pressured != normal
    assert any(item['priority'] in {'P1', 'P2'} for item in pressured)
    assert any(item['source_label'] == 'Request Health' for item in pressured)


def test_forecast_recommendations_keep_missing_materialization_unknown() -> None:
    cards = build_forecast_recommendations(
        {'forecast': {}, 'forecast_posture': {'tone': 'unknown'}},
        {'usable': False},
    )

    assert len(cards) == 1
    assert cards[0]['tone'] == 'unknown'
    assert cards[0]['is_actionable'] is False
    assert cards[0]['source_label'] == 'Forecast Worker'
