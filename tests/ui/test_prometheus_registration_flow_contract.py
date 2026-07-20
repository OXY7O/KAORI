from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / 'app/templates/prometheus/instance_form.html'
ROUTES = ROOT / 'app/prometheus/routes.py'
SERVICE = ROOT / 'app/prometheus/service.py'
REGISTRATION = ROOT / 'app/prometheus/registration.py'
RESULT = ROOT / 'app/templates/prometheus/partials/_connection_test_result.html'
STANDARD = ROOT / 'docs/design/components/INTEGRATION_MANAGE_WORKSPACE.md'


def read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def test_prometheus_registration_requires_verified_connection_proof() -> None:
    template = read(TEMPLATE)
    routes = read(ROUTES)
    registration = read(REGISTRATION)

    for fragment in (
        "url_for('prometheus.test_new_instance_connection')",
        'name="connection_test_proof"',
        'disabled x-bind:disabled="!connectionVerified"',
        'x-on:prometheus-connection-tested.window="applyConnectionTest($event)"',
        'invalidateConnectionTest(event)',
        'Register after Test Connection succeeds.',
    ):
        assert fragment in template

    for fragment in (
        "@prometheus_bp.post('/instances/test-connection')",
        'verify_registration_proof(',
        'issue_registration_proof(',
        "'registration_stage': 'connection_test_proof'",
        "'registration_stage': 'pre_save_recheck'",
        "'prometheus-connection-tested'",
    ):
        assert fragment in routes

    assert 'REGISTRATION_PROOF_MAX_AGE_SECONDS = 600' in registration
    assert "field_name in {'password', 'bearer_token'}" in registration


def test_prometheus_registration_guidance_uses_agreed_order() -> None:
    template = read(TEMPLATE)

    registration_flow = template.index("'Prometheus Registration Flow'")
    related_workspace = template.index("eyebrow='Related Analytics Workspace'")
    connection_contract = template.index("'Connection Identity & Contract'")
    after_registration = template.index("'After Registration'")

    assert registration_flow < related_workspace
    assert connection_contract < after_registration
    assert "('Test Connection', 'Verify reachability and compatibility before KAORI enables registration.')" in template


def test_draft_probe_is_non_persistent_and_all_outcomes_use_toast_audit() -> None:
    service = read(SERVICE)
    routes = read(ROUTES)
    result = read(RESULT)

    assert 'def test_connection(self, *, persist: bool = True)' in service
    assert 'PrometheusService(draft).test_connection(persist=False)' in service
    assert "event_type='prometheus_connection_test'" in routes
    assert "event_type='prometheus_connection_test_failed'" in routes
    assert "event_type='prometheus_instance_create_rejected'" in routes
    assert "event_type='prometheus_instance_create_failed'" in routes
    assert "event_type='prometheus_instance_created'" in routes
    assert "operation_feedback_oob.html" in result


def test_provider_registration_standard_is_documented() -> None:
    standard = read(STANDARD)
    for phrase in (
        'Provider registration contract',
        'successful Test Connection',
        'short-lived signed proof',
        'invalidate the proof',
        'one toast and one durable Activity Audit record',
    ):
        assert phrase in standard
