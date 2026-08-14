from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

from app.analytics.object_storage.analysis import metric_risk_signals
from app.analytics.object_storage.runtime import EvidenceReader
from app.analytics.object_storage.sources import minio_prometheus as prometheus_source
from app.analytics.shared.metrics import (
    MetricsSourceError,
    MetricsSourceFailureKind,
    MetricsSourceIdentity,
)

ROOT = Path(__file__).resolve().parents[3]


def load_module(name: str, relative: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_prometheus_adapter_parses_scalar_bucket_vector_and_matrix() -> None:
    vector_payload = {
        'data': {
            'result': [
                {'metric': {'bucket': 'archive'}, 'value': [1_700_000_000, '2048']},
                {'metric': {'bucket': 'reports'}, 'value': [1_700_000_000, '4096']},
            ]
        }
    }
    matrix_payload = {'data': {'result': [{'metric': {}, 'values': [[100, '10'], [200, '20.5']]}]}}

    assert prometheus_source._vector_scalar(vector_payload) == 2048.0
    assert prometheus_source._vector_by_label(vector_payload, 'bucket') == {
        'archive': 2048.0,
        'reports': 4096.0,
    }
    assert prometheus_source._matrix_points(matrix_payload) == [
        {'timestamp': 100.0, 'value': 10.0},
        {'timestamp': 200.0, 'value': 20.5},
    ]


def test_request_reader_stops_after_source_wide_transport_failure() -> None:
    class Source:
        identity = MetricsSourceIdentity('fake', 'Fake Metrics', 'fake-1', 'Fake Metrics · fake-1')

        def __init__(self) -> None:
            self.calls: list[str] = []

        def scalar(self, metric_key: str) -> float | None:
            self.calls.append(f'scalar:{metric_key}')
            raise MetricsSourceError(
                'network unreachable',
                kind=MetricsSourceFailureKind.TRANSPORT,
                provider='fake',
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
        identity = MetricsSourceIdentity('fake', 'Fake Metrics', 'fake-1', 'Fake Metrics · fake-1')

        def __init__(self) -> None:
            self.calls = 0

        def scalar(self, _metric_key: str) -> float | None:
            self.calls += 1
            if self.calls == 1:
                raise MetricsSourceError('bad query', kind=MetricsSourceFailureKind.QUERY, provider='fake')
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
    forecasting = load_module('object_storage_forecasting_under_test', 'app/analytics/object_storage/forecasting.py')
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
    presentation = load_module('object_storage_presentation_under_test', 'app/analytics/object_storage/presentation.py')

    assert presentation.format_bytes(1024) == '1.0 KiB'
    assert presentation.utilization_percent(850, 1000) == 85.0
    assert presentation.utilization_tone(84.9) == 'normal'
    assert presentation.utilization_tone(85.0) == 'warning'
    assert presentation.utilization_tone(95.0) == 'critical'
