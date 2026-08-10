from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

MODULE_PATH = Path('app/analytics/common/presentation.py')
SPEC = spec_from_file_location('analytics_common_presentation_standalone', MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
present_prometheus_status = MODULE.present_prometheus_status


def test_ready_status_uses_canonical_labels_and_provider_timestamp() -> None:
    checked_at = object()
    result = present_prometheus_status(
        {
            'configured': True,
            'connected': True,
            'response_time_ms': 1955.6,
            'last_checked_at': checked_at,
        }
    )

    assert result['state'] == 'query_ready'
    assert result['status_label'] == 'Query Ready'
    assert result['tone'] == 'normal'
    assert result['response_time_ms'] == 1956
    assert result['response_time_display'] == '1956 ms'
    assert result['last_checked_at'] is checked_at


def test_degraded_status_is_not_reported_as_ready() -> None:
    result = present_prometheus_status(
        {
            'configured': True,
            'connected': True,
            'observation_degraded': True,
        }
    )

    assert result['state'] == 'query_degraded'
    assert result['status_label'] == 'Query Degraded'
    assert result['tone'] == 'warning'


def test_not_configured_and_waiting_states_remain_distinct() -> None:
    waiting = present_prometheus_status({'configured': False, 'label': 'Waiting for Cluster'})
    not_configured = present_prometheus_status({'configured': False, 'label': 'Prometheus Not Configured'})

    assert waiting['state'] == 'waiting_for_cluster'
    assert waiting['status_label'] == 'Waiting for Cluster'
    assert not_configured['state'] == 'not_configured'
    assert not_configured['status_label'] == 'Not Configured'


def test_unavailable_status_preserves_diagnostic_error() -> None:
    result = present_prometheus_status(
        {
            'configured': True,
            'connected': False,
            'error': 'Connection timed out.',
        }
    )

    assert result['state'] == 'unavailable'
    assert result['status_label'] == 'Unavailable'
    assert result['message'] == 'Connection timed out.'
    assert result['response_time_display'] == 'No Response'
