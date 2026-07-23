from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.analytics.alerts import sources
from app.integrations.prometheus.exceptions import PrometheusConnectionError


def _cluster() -> SimpleNamespace:
    return SimpleNamespace(id=7)


def _status(
    *,
    source: str,
    connected: bool,
    configured: bool = True,
    label: str | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    return {
        'source': source,
        'selected_source': source,
        'resolved_source': source if connected else 'none',
        'label': label or (f'{source.title()} Connected' if connected else f'{source.title()} Unavailable'),
        'configured': configured,
        'connected': connected,
        'fallback_used': False,
        'fallback_reason': None,
        'error': error,
        'response_time_ms': 12 if connected else None,
        'last_checked_at': None,
    }


def _alert(*, source: str, name: str) -> dict[str, Any]:
    return {
        'name': name,
        'severity': 'warning',
        'status': 'firing',
        'namespace': 'production',
        'target': 'api-1',
        'source': source,
        'summary': name,
        'description': name,
        'starts_at': '-',
        'starts_at_display': '-',
        'ends_at': '-',
        'ends_at_display': '-',
        'labels': {'alertname': name},
        'annotations': {},
        'owner': 'platform',
        'runbook_url': '',
        'contact': '',
        'generator_url': '',
        'fingerprint': '',
    }


def test_auto_source_prefers_connected_alertmanager_without_prometheus_call(monkeypatch) -> None:
    alertmanager_alert = _alert(source='Alertmanager', name='PodDown')

    monkeypatch.setattr(
        sources,
        'load_alertmanager_alerts',
        lambda **_: ([alertmanager_alert], _status(source='alertmanager', connected=True)),
    )

    def unexpected_prometheus_call(**_: Any) -> tuple[list[Any], dict[str, Any]]:
        raise AssertionError('Prometheus fallback must not run while Alertmanager is connected.')

    monkeypatch.setattr(sources, 'load_prometheus_alerts', unexpected_prometheus_call)

    alerts, status = sources.load_alerts_by_source(
        cluster=_cluster(),
        source='auto',
    )

    assert alerts == [alertmanager_alert]
    assert status['selected_source'] == 'auto'
    assert status['resolved_source'] == 'alertmanager'
    assert status['connected'] is True
    assert status['fallback_used'] is False
    assert status['fallback_reason'] is None


def test_auto_source_falls_back_to_connected_prometheus_with_reason(monkeypatch) -> None:
    prometheus_alert = _alert(source='Prometheus', name='HighCPU')

    monkeypatch.setattr(
        sources,
        'load_alertmanager_alerts',
        lambda **_: (
            [],
            _status(
                source='alertmanager',
                connected=False,
                label='Alertmanager Unavailable',
                error='connection refused',
            ),
        ),
    )
    monkeypatch.setattr(
        sources,
        'load_prometheus_alerts',
        lambda **_: ([prometheus_alert], _status(source='prometheus', connected=True)),
    )

    alerts, status = sources.load_alerts_by_source(
        cluster=_cluster(),
        source='auto',
    )

    assert alerts == [prometheus_alert]
    assert status['selected_source'] == 'auto'
    assert status['resolved_source'] == 'prometheus'
    assert status['connected'] is True
    assert status['fallback_used'] is True
    assert status['label'] == 'Prometheus Fallback Connected'
    assert status['error'] is None
    assert status['fallback_reason'] == (
        'Alertmanager unavailable: connection refused. Using Prometheus ALERTS fallback.'
    )


def test_auto_source_reports_combined_failure_when_both_sources_are_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(
        sources,
        'load_alertmanager_alerts',
        lambda **_: (
            [],
            _status(
                source='alertmanager',
                connected=False,
                configured=True,
                error='alertmanager timeout',
            ),
        ),
    )
    monkeypatch.setattr(
        sources,
        'load_prometheus_alerts',
        lambda **_: (
            [],
            _status(
                source='prometheus',
                connected=False,
                configured=False,
                error='prometheus binding missing',
            ),
        ),
    )

    alerts, status = sources.load_alerts_by_source(
        cluster=_cluster(),
        source='auto',
    )

    assert alerts == []
    assert status['source'] == 'auto'
    assert status['selected_source'] == 'auto'
    assert status['resolved_source'] == 'none'
    assert status['label'] == 'Alert Sources Unavailable'
    assert status['configured'] is True
    assert status['connected'] is False
    assert status['fallback_used'] is True
    assert status['fallback_reason'] == (
        'Alertmanager unavailable: alertmanager timeout. Prometheus fallback also unavailable.'
    )
    assert status['error'] == 'alertmanager timeout | prometheus binding missing'


@pytest.mark.parametrize('selected_source', ['alertmanager', 'prometheus'])
def test_explicit_source_selection_does_not_cross_fallback(monkeypatch, selected_source: str) -> None:
    calls: list[str] = []

    def load_alertmanager(**_: Any) -> tuple[list[Any], dict[str, Any]]:
        calls.append('alertmanager')
        return [], _status(source='alertmanager', connected=False, error='alertmanager unavailable')

    def load_prometheus(**_: Any) -> tuple[list[Any], dict[str, Any]]:
        calls.append('prometheus')
        return [], _status(source='prometheus', connected=False, error='prometheus unavailable')

    monkeypatch.setattr(sources, 'load_alertmanager_alerts', load_alertmanager)
    monkeypatch.setattr(sources, 'load_prometheus_alerts', load_prometheus)

    alerts, status = sources.load_alerts_by_source(
        cluster=_cluster(),
        source=selected_source,
    )

    assert alerts == []
    assert calls == [selected_source]
    assert status['selected_source'] == selected_source
    assert status['fallback_used'] is False
    assert status['fallback_reason'] is None


def test_alertmanager_loader_ignores_non_mapping_alert_items(monkeypatch) -> None:
    monkeypatch.setattr(
        sources,
        'get_alertmanager_alerts',
        lambda **_: {
            'connected': True,
            'alerts': [
                {
                    'labels': {
                        'alertname': 'PodDown',
                        'severity': 'warning',
                    },
                    'annotations': {},
                },
                'malformed-string',
                None,
                [],
            ],
            'error': None,
        },
    )
    monkeypatch.setattr(
        sources,
        'get_alertmanager_status',
        lambda **_: {
            'configured': True,
            'connected': True,
            'label': 'Alertmanager Connected',
        },
    )

    alerts, status = sources.load_alertmanager_alerts(cluster=_cluster())

    assert [alert['name'] for alert in alerts] == ['PodDown']
    assert status['connected'] is True
    assert status['resolved_source'] == 'alertmanager'


def test_prometheus_loader_treats_non_list_result_as_empty_connected_payload(monkeypatch) -> None:
    class MalformedPrometheusService:
        def __init__(self, cluster: Any) -> None:
            self.cluster = cluster

        def instant_query(self, query: str) -> dict[str, Any]:
            assert query == sources.PROMETHEUS_ALERTS_QUERY
            return {
                'data': {
                    'result': {
                        'unexpected': 'mapping',
                    }
                }
            }

    monkeypatch.setattr(sources, 'PrometheusService', MalformedPrometheusService)

    alerts, status = sources.load_prometheus_alerts(cluster=_cluster())

    assert alerts == []
    assert status['configured'] is True
    assert status['connected'] is True
    assert status['resolved_source'] == 'prometheus'
    assert status['error'] is None


def test_prometheus_provider_exceptions_are_normalized_into_source_status(monkeypatch) -> None:
    class UnavailablePrometheusService:
        def __init__(self, cluster: Any) -> None:
            self.cluster = cluster

        def instant_query(self, query: str) -> dict[str, Any]:
            raise PrometheusConnectionError('connection refused')

    monkeypatch.setattr(sources, 'PrometheusService', UnavailablePrometheusService)

    alerts, status = sources.load_prometheus_alerts(cluster=_cluster())

    assert alerts == []
    assert status['label'] == 'Prometheus Unavailable'
    assert status['configured'] is False
    assert status['connected'] is False
    assert status['resolved_source'] == 'none'
    assert status['error'] == 'connection refused'


def test_unexpected_alertmanager_exception_is_normalized_into_source_status(monkeypatch) -> None:
    def raise_provider_error(**_: Any) -> dict[str, Any]:
        raise RuntimeError('unexpected alertmanager failure')

    logged: list[tuple[Any, ...]] = []

    monkeypatch.setattr(sources, 'get_alertmanager_alerts', raise_provider_error)
    monkeypatch.setattr(
        sources.logger,
        'exception',
        lambda *args, **_: logged.append(args),
    )

    alerts, status = sources.load_alertmanager_alerts(cluster=_cluster())

    assert alerts == []
    assert status['label'] == 'Alertmanager Error'
    assert status['configured'] is True
    assert status['connected'] is False
    assert status['resolved_source'] == 'none'
    assert status['fallback_used'] is False
    assert status['fallback_reason'] is None
    assert status['error'] == 'unexpected alertmanager failure'
    assert isinstance(status['response_time_ms'], int)
    assert status['last_checked_at'] is not None
    assert logged == [
        (
            'Unexpected Alertmanager alert loading failure for cluster %s.',
            7,
        )
    ]


def test_auto_source_falls_back_after_unexpected_alertmanager_exception(monkeypatch) -> None:
    prometheus_alert = _alert(source='Prometheus', name='HighCPU')

    def raise_provider_error(**_: Any) -> dict[str, Any]:
        raise RuntimeError('unexpected alertmanager failure')

    monkeypatch.setattr(sources, 'get_alertmanager_alerts', raise_provider_error)
    monkeypatch.setattr(sources.logger, 'exception', lambda *_, **__: None)
    monkeypatch.setattr(
        sources,
        'load_prometheus_alerts',
        lambda **_: ([prometheus_alert], _status(source='prometheus', connected=True)),
    )

    alerts, status = sources.load_alerts_by_source(
        cluster=_cluster(),
        source='auto',
    )

    assert alerts == [prometheus_alert]
    assert status['selected_source'] == 'auto'
    assert status['resolved_source'] == 'prometheus'
    assert status['connected'] is True
    assert status['fallback_used'] is True
    assert status['label'] == 'Prometheus Fallback Connected'
    assert status['error'] is None
    assert status['fallback_reason'] == (
        'Alertmanager unavailable: unexpected alertmanager failure. '
        'Using Prometheus ALERTS fallback.'
    )


def test_explicit_alertmanager_source_normalizes_exception_without_cross_fallback(monkeypatch) -> None:
    def raise_provider_error(**_: Any) -> dict[str, Any]:
        raise RuntimeError('unexpected alertmanager failure')

    def unexpected_prometheus_call(**_: Any) -> tuple[list[Any], dict[str, Any]]:
        raise AssertionError('Explicit Alertmanager selection must not call Prometheus.')

    monkeypatch.setattr(sources, 'get_alertmanager_alerts', raise_provider_error)
    monkeypatch.setattr(sources.logger, 'exception', lambda *_, **__: None)
    monkeypatch.setattr(sources, 'load_prometheus_alerts', unexpected_prometheus_call)

    alerts, status = sources.load_alerts_by_source(
        cluster=_cluster(),
        source='alertmanager',
    )

    assert alerts == []
    assert status['selected_source'] == 'alertmanager'
    assert status['resolved_source'] == 'none'
    assert status['connected'] is False
    assert status['fallback_used'] is False
    assert status['fallback_reason'] is None
    assert status['error'] == 'unexpected alertmanager failure'
