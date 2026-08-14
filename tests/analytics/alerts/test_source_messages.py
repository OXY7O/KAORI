from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[3] / 'app/analytics/kubernetes/alerts/source_messages.py'
SPEC = spec_from_file_location('alert_source_messages_contract', MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

friendly_alert_fallback_reason = MODULE.friendly_alert_fallback_reason
friendly_alert_source_error = MODULE.friendly_alert_source_error
friendly_combined_alert_error = MODULE.friendly_combined_alert_error


def test_timeout_error_is_user_friendly_and_hides_endpoint() -> None:
    raw = "HTTPSConnectionPool(host='internal.example', port=443): Max retries exceeded with url: /api/v2/alerts (ConnectTimeoutError)"
    message = friendly_alert_source_error(raw, source_label='Alertmanager')
    assert message == 'Alertmanager is temporarily unreachable. KAORI will retry automatically.'
    assert 'internal.example' not in message
    assert '/api/v2/alerts' not in message


def test_authentication_and_tls_errors_have_actionable_messages() -> None:
    assert 'credentials' in friendly_alert_source_error('403 Forbidden', source_label='Prometheus')
    assert 'certificate' in friendly_alert_source_error(
        'certificate verify failed: self signed certificate', source_label='Prometheus'
    )


def test_fallback_messages_do_not_include_provider_exceptions() -> None:
    assert friendly_alert_fallback_reason(primary_available=False, fallback_available=True) == (
        'Alertmanager is unavailable, so KAORI is using the Prometheus ALERTS fallback.'
    )
    assert 'retry automatically' in friendly_combined_alert_error()
