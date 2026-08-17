from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[3]


class FakeMetricsSourceError(Exception):
    pass


def _load_anomalies_module():
    names = [
        'app',
        'app.analytics',
        'app.analytics.kubernetes.alerts',
        'app.analytics.kubernetes.alerts.metrics',
        'app.integrations',
        'app.integrations.metrics.exceptions',
        'app.integrations.metrics.query_profiles',
        'app.models',
        'app.metrics.repository',
        'app.metrics.service',
    ]
    previous = {name: sys.modules.get(name) for name in names}
    try:
        for package in (
            'app',
            'app.analytics',
            'app.analytics.kubernetes.alerts',
            'app.integrations',
        ):
            sys.modules[package] = ModuleType(package)

        metrics = ModuleType('app.analytics.kubernetes.alerts.metrics')
        metrics.get_metric_labels = lambda item: dict(item.get('metric') or {})
        metrics.get_metric_value = lambda item: float((item.get('value') or [0, 0])[1])
        sys.modules[metrics.__name__] = metrics

        exceptions = ModuleType('app.integrations.metrics.exceptions')
        exceptions.MetricsSourceError = FakeMetricsSourceError
        sys.modules[exceptions.__name__] = exceptions

        profiles = ModuleType('app.integrations.metrics.query_profiles')
        profiles.get_query_expression = lambda key: key
        sys.modules[profiles.__name__] = profiles

        models = ModuleType('app.models')
        models.Cluster = object
        sys.modules[models.__name__] = models

        repository = ModuleType('app.metrics.repository')
        repository.resolve_instance_for_cluster = lambda cluster_id: object()
        sys.modules[repository.__name__] = repository

        service = ModuleType('app.metrics.service')
        service.MetricsService = object
        sys.modules[service.__name__] = service

        spec = importlib.util.spec_from_file_location(
            'alerts_anomalies_under_test',
            ROOT / 'app/analytics/kubernetes/alerts/anomalies.py',
        )
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        for name, value in previous.items():
            if value is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = value


def test_one_failed_anomaly_query_preserves_successful_candidates() -> None:
    anomalies = _load_anomalies_module()

    class Service:
        def __init__(self, cluster):
            self.calls = 0

        def instant_query(self, query):
            self.calls += 1
            if self.calls == 1:
                return {
                    'data': {
                        'result': [
                            {
                                'metric': {'namespace': 'payments', 'pod': 'api-1'},
                                'value': [0, '6'],
                            }
                        ]
                    }
                }
            raise FakeMetricsSourceError('readiness query timeout')

    anomalies.MetricsService = Service
    cluster = type('Cluster', (), {'id': 'cluster-1'})()
    rows, status = anomalies.load_metrics_source_anomaly_metrics(cluster=cluster)

    assert len(rows) == 1
    assert rows[0]['severity'] == 'critical'
    assert status['connected'] is True
    assert status['partial'] is True
    assert status['available_queries'] == ['restart']
    assert status['failed_queries'] == ['readiness']


def test_missing_metrics_source_binding_returns_unavailable_evidence() -> None:
    anomalies = _load_anomalies_module()
    anomalies.resolve_instance_for_cluster = lambda cluster_id: None

    class UnexpectedService:
        def __init__(self, cluster):
            raise AssertionError('MetricsService must not be created without a binding')

    anomalies.MetricsService = UnexpectedService
    cluster = type('Cluster', (), {'id': 'cluster-1'})()
    rows, status = anomalies.load_metrics_source_anomaly_metrics(cluster=cluster)

    assert rows == []
    assert status['configured'] is False
    assert status['connected'] is False
    assert status['partial'] is True
    assert status['failed_queries'] == ['restart', 'readiness']


def test_metrics_source_resolution_failure_is_controlled() -> None:
    anomalies = _load_anomalies_module()

    class FailingService:
        def __init__(self, cluster):
            raise FakeMetricsSourceError('binding capability unavailable')

    anomalies.MetricsService = FailingService
    cluster = type('Cluster', (), {'id': 'cluster-1'})()
    rows, status = anomalies.load_metrics_source_anomaly_metrics(cluster=cluster)

    assert rows == []
    assert status['configured'] is True
    assert status['connected'] is False
    assert status['partial'] is True
    assert 'binding capability unavailable' in status['error']
