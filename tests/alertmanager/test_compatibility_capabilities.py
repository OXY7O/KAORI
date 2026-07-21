from app.integrations.alertmanager.probes import discover_payload_capabilities
from app.integrations.alertmanager.profiles import resolve_profile
from app.integrations.alertmanager.requirements import evaluate_module_readiness


def test_payload_capability_discovery_uses_observed_alert_metadata():
    capabilities = discover_payload_capabilities(
        [
            {
                'labels': {'alertname': 'PodDown', 'severity': 'critical'},
                'annotations': {'summary': 'Pod is unavailable', 'runbook_url': 'https://runbook.invalid/pod'},
                'fingerprint': 'abc123',
                'startsAt': '2026-07-18T00:00:00Z',
                'generatorURL': 'https://prometheus.invalid/graph',
                'receivers': [{'name': 'telegram'}],
            }
        ],
        [{'matchers': [{'name': 'namespace', 'value': 'prod'}]}],
    )
    assert {
        'alert_labels',
        'alertname_label',
        'severity_label',
        'fingerprint',
        'starts_at',
        'receiver_metadata',
        'summary_annotation',
        'runbook_url',
        'generator_url',
        'silence_matchers',
    } <= capabilities


def test_profile_registry_maps_supported_runtime_lines():
    legacy = resolve_profile('0.25.0')
    current = resolve_profile('v0.33.1')
    assert legacy is not None and legacy.key == 'alertmanager-v0-25'
    assert current is not None and current.key == 'alertmanager-v0-33'
    assert resolve_profile('0.40.0') is None


def test_module_readiness_distinguishes_required_and_optional_capabilities():
    rows = {row['key']: row for row in evaluate_module_readiness({'alerts_v2', 'alert_labels', 'alertname_label', 'starts_at'})}
    assert rows['alert_inventory']['status'] == 'ready'
    assert rows['kubernetes_alerts']['status'] == 'degraded'
    assert rows['alert_intelligence']['status'] == 'unavailable'
    assert rows['runbook_integration']['status'] == 'unavailable'
