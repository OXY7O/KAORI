from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

from app.common.analytics.metrics import (
    MetricsSourceError,
    MetricsSourceFailureKind,
    MetricsSourceIdentity,
)
from app.storage.object_storage.analytics.analysis import metric_risk_signals
from app.storage.object_storage.analytics.runtime import EvidenceReader
from app.storage.object_storage.analytics.sources.providers.minio import metrics as metrics_source

ROOT = Path(__file__).resolve().parents[4]


def load_module(name: str, relative: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Mirror normal import semantics so decorators (notably dataclasses on
    # Python 3.12 with postponed annotations) can resolve cls.__module__.
    previous = sys.modules.get(name)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        if previous is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = previous
        raise
    return module


def test_metrics_source_adapter_parses_scalar_bucket_vector_and_matrix() -> None:
    vector_payload = {
        'data': {
            'result': [
                {'metric': {'bucket': 'archive'}, 'value': [1_700_000_000, '2048']},
                {'metric': {'bucket': 'reports'}, 'value': [1_700_000_000, '4096']},
            ]
        }
    }
    matrix_payload = {'data': {'result': [{'metric': {}, 'values': [[100, '10'], [200, '20.5']]}]}}

    assert metrics_source._vector_scalar(vector_payload) == 2048.0
    assert metrics_source._vector_by_label(vector_payload, 'bucket') == {
        'archive': 2048.0,
        'reports': 4096.0,
    }
    assert metrics_source._matrix_points(matrix_payload) == [
        {'timestamp': 100.0, 'value': 10.0},
        {'timestamp': 200.0, 'value': 20.5},
    ]


def test_request_reader_stops_after_source_wide_transport_failure() -> None:
    class Source:
        identity = MetricsSourceIdentity('metrics_source', 'fake', 'Fake Metrics', 'fake-1', 'Fake Metrics · fake-1')

        def __init__(self) -> None:
            self.calls: list[str] = []

        def scalar(self, metric_key: str) -> float | None:
            self.calls.append(f'scalar:{metric_key}')
            raise MetricsSourceError(
                'network unreachable',
                kind=MetricsSourceFailureKind.TRANSPORT,
                provider_key='fake',
            )

        def vector(self, metric_key: str, label: str) -> dict[str, float]:
            self.calls.append(f'vector:{metric_key}:{label}')
            return {'should-not-run': 1.0}

        def trend(self, metric_key: str, time_range: str) -> list[dict[str, float]]:
            self.calls.append(f'trend:{metric_key}:{time_range}')
            return [{'timestamp': 1.0, 'value': 1.0}]

    source = Source()
    reader = EvidenceReader(source)

    assert reader.scalar('object_storage.capacity.total_bytes') is None
    assert reader.scalar('object_storage.capacity.free_bytes') is None
    assert reader.vector('object_storage.bucket.usage') == {}
    assert reader.trend('object_storage.usage.total_bytes', '24h') == []
    assert source.calls == ['scalar:object_storage.capacity.total_bytes']
    assert reader.source_wide_failure is not None
    assert reader.failed_query_count == 1


def test_query_specific_failure_does_not_trip_source_wide_fail_fast() -> None:
    class Source:
        identity = MetricsSourceIdentity('metrics_source', 'fake', 'Fake Metrics', 'fake-1', 'Fake Metrics · fake-1')

        def __init__(self) -> None:
            self.calls = 0

        def scalar(self, _metric_key: str) -> float | None:
            self.calls += 1
            if self.calls == 1:
                raise MetricsSourceError('bad query', kind=MetricsSourceFailureKind.QUERY, provider_key='fake')
            return 42.0

        def vector(self, _metric_key: str, _label: str) -> dict[str, float]:
            return {}

        def trend(self, _metric_key: str, _time_range: str) -> list[dict[str, float]]:
            return []

    source = Source()
    reader = EvidenceReader(source)

    assert reader.scalar('metric.one') is None
    assert reader.scalar('metric.two') == 42.0
    assert source.calls == 2
    assert reader.source_wide_failure is None
    assert reader.failed_query_count == 1
    assert reader.successful_query_count == 1


def test_object_storage_signal_does_not_claim_healthy_without_metric_evidence() -> None:
    signals = metric_risk_signals(
        utilization=None,
        error_ratio=None,
        waiting=None,
        offline_nodes=None,
    )

    assert signals == [
        {
            'severity': 'unknown',
            'title': 'Metric Evidence Unavailable',
            'detail': 'Operational risk cannot be evaluated until metric evidence is available.',
        }
    ]


def test_object_storage_forecast_projects_growth_without_claiming_capacity_eta_on_decline() -> None:
    forecasting = load_module(
        'object_storage_forecasting_under_test', 'app/storage/object_storage/analytics/forecasting.py'
    )
    growing = forecasting.linear_forecast(
        [
            {'timestamp': 0.0, 'value': 100.0},
            {'timestamp': 86_400.0, 'value': 200.0},
        ],
        capacity_bytes=1000.0,
    )
    declining = forecasting.linear_forecast(
        [
            {'timestamp': 0.0, 'value': 200.0},
            {'timestamp': 86_400.0, 'value': 100.0},
        ],
        capacity_bytes=1000.0,
    )

    assert growing['growth_per_day'] == 100.0
    assert growing['projected_7d'] == 900.0
    assert growing['days_to_capacity'] == 8.0
    assert declining['growth_per_day'] == -100.0
    assert declining['days_to_capacity'] is None


def test_object_storage_capacity_presentation_uses_kaori_thresholds() -> None:
    presentation = load_module(
        'object_storage_presentation_under_test', 'app/storage/object_storage/analytics/presentation.py'
    )

    assert presentation.format_bytes(1024) == '1.0 KiB'
    assert presentation.utilization_percent(850, 1000) == 85.0
    assert presentation.utilization_tone(84.9) == 'normal'
    assert presentation.utilization_tone(85.0) == 'warning'
    assert presentation.utilization_tone(95.0) == 'critical'


def test_object_storage_capacity_usage_view_separates_physical_and_quota_boundaries() -> None:
    presentation = load_module(
        'object_storage_capacity_presentation_under_test',
        'app/storage/object_storage/analytics/presentation.py',
    )

    view = presentation.build_capacity_usage_view(
        capacity_total=1000.0,
        usage_total=850.0,
        capacity_free=150.0,
        capacity_free_source='Operational Metric',
        utilization=85.0,
        trend_summary={
            'sample_count': 4,
            'growth_per_day': 10.0,
            'growth_per_day_display': '10.0 B per day',
            'delta_display': '40 B',
            'delta_percent_display': '4.9%',
            'direction': 'increasing',
            'direction_label': 'Increasing',
            'tone': 'warning',
        },
        bucket_analysis={
            'bucket_count': 4,
            'quota_known_count': 3,
            'quota_unknown_count': 1,
            'quota_pressure_count': 2,
            'critical_quota_count': 1,
            'top_usage_share_display': '52.0%',
            'concentration_label': 'Concentrated',
            'concentration_tone': 'warning',
        },
    )

    assert view['capacity_evidence_available'] is True
    assert view['quota_coverage_display'] == '75.0%'
    assert view['quota_within_count'] == 1
    assert view['quota_warning_count'] == 1
    assert view['quota_critical_count'] == 1
    assert view['quota_status'] == 'Critical Quota Pressure'
    assert view['growth_capacity_percent_display'] == '1.0%'


def test_object_storage_performance_posture_does_not_claim_healthy_with_partial_evidence() -> None:
    analysis = load_module(
        'object_storage_analysis_performance_under_test', 'app/storage/object_storage/analytics/analysis.py'
    )

    posture = analysis.performance_posture(
        error_percent=1.0,
        waiting=None,
        offline_nodes=0.0,
    )

    assert posture.status == 'Partial Evidence'
    assert posture.tone == 'unknown'
    assert 'supporting evidence is incomplete' in posture.headline


def test_object_storage_performance_view_keeps_demand_and_reliability_semantics_separate() -> None:
    presentation = load_module(
        'object_storage_performance_presentation_under_test',
        'app/storage/object_storage/analytics/presentation.py',
    )

    view = presentation.build_performance_view(
        presentation.PerformanceEvidence(
            request_rate=120.0,
            error_rate=2.4,
            error_ratio=2.0,
            success_ratio=98.0,
            waiting=0.0,
            inflight=8.0,
            offline_nodes=0.0,
            received_bps=1000.0,
            sent_bps=3000.0,
            request_trend_summary={
                'direction': 'increasing',
                'sample_count': 8,
                'delta_display': '20.00/s',
                'delta_percent_display': '20.0%',
            },
            error_trend_summary={
                'direction': 'decreasing',
                'sample_count': 8,
                'delta_display': '-0.20/s',
                'delta_percent_display': '7.7%',
            },
            bucket_analysis={
                'bucket_count': 4,
                'request_evidence_count': 4,
                'error_evidence_count': 3,
                'top_request_rate': {'name': 'media', 'request_rate_display': '60.00/s'},
                'top_error_ratio': {'name': 'archive', 'error_ratio_display': '4.0%'},
            },
        )
    )

    assert view['reliability_status'] == 'Within Error Baseline'
    assert view['queue_status'] == 'No Waiting Requests'
    assert view['node_status'] == 'No Offline Nodes'
    assert view['request_trend_status'] == 'Increasing Demand'
    assert view['request_trend_tone'] == 'info'
    assert view['error_trend_status'] == 'Errors Decreasing'
    assert view['received_share_display'] == '25.0%'
    assert view['sent_share_display'] == '75.0%'
    assert view['bucket_request_coverage_display'] == '100.0%'
    assert view['bucket_error_coverage_display'] == '75.0%'
    assert view['top_request_bucket_name'] == 'media'
    assert view['top_error_bucket_name'] == 'archive'
