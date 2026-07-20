from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_shared_connection_validation_header_contract() -> None:
    source = read("app/templates/components/connection_validation_header.html")
    assert "macro render(" in source
    assert "border-b border-outline-subtle" in source
    assert "max-w-2xl text-xs leading-5" in source
    assert "caller()" in source
    assert "lg:items-center lg:justify-between" in source


def test_connection_validation_header_is_used_across_integration_providers() -> None:
    expectations = {
        "app/templates/integrations/kubernetes/detail.html": (
            "Refresh connection health and compatibility evidence.",
            "Refresh Runtime",
        ),
        "app/templates/prometheus/instance_detail.html": (
            "Test reachability, then rebuild capability evidence.",
            "Test Connection",
        ),
        "app/templates/prometheus/config.html": (
            "Test reachability, then rebuild metrics readiness evidence.",
            "Run Full Validation",
        ),
        "app/templates/alertmanager/instance_form.html": (
            "Validate endpoint access before registration.",
            "Test Connection",
        ),
        "app/templates/alertmanager/partials/_detail_validation_content.html": (
            "Rebuild capability and readiness evidence.",
            "Run Full Validation",
        ),
    }
    for relative, values in expectations.items():
        source = read(relative)
        assert 'components/connection_validation_header.html' in source
        assert "connection_validation_header.render(" in source
        for value in values:
            assert value in source


def test_alertmanager_endpoint_header_does_not_repeat_long_api_explanation() -> None:
    source = read("app/templates/alertmanager/instance_form.html")
    assert "KAORI uses the base URL and submitted credentials to call the Alertmanager API v2 status interface." not in source
    assert source.count("Test Connection") >= 1
    endpoint_section = source.split("'Endpoint &amp; Access'", 1)[1].split("</section>", 1)[0]
    assert "Test Connection" in endpoint_section


def test_connection_validation_header_standard_is_documented() -> None:
    standard = read("docs/design/components/CONNECTION_VALIDATION_HEADER.md")
    audit = read("docs/design/audits/CONNECTION_VALIDATION_HEADER_AUDIT_2026_07.md")
    index = read("docs/design/README.md")
    assert "approximately 80 characters or fewer" in standard
    assert "one or two closely related actions" in standard
    assert "Kubernetes, Prometheus, and Alertmanager coverage" in audit
    assert "components/CONNECTION_VALIDATION_HEADER.md" in index
