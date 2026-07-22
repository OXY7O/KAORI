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
    assert 'components/loading_bar.html' in source
    assert 'loading_bar.render' in source
    assert 'loading_id=None' in source


def test_alertmanager_endpoint_header_does_not_repeat_long_api_explanation() -> None:
    source = read("app/templates/alertmanager/instance_form.html")
    assert "KAORI uses the base URL and submitted credentials to call the Alertmanager API v2 status interface." not in source
    assert source.count("Test Connection") >= 1
    endpoint_section = source.split("'Endpoint & Access'", 1)[1].split("</section>", 1)[0]
    assert "Test Connection" in endpoint_section



def test_registration_connection_test_loading_bar_is_owned_by_header() -> None:
    expectations = {
        "app/templates/alertmanager/instance_form.html": "alertmanager-connection-test-loading",
        "app/templates/prometheus/instance_form.html": "prometheus-connection-test-loading",
        "app/templates/cluster/partials/_form.html": "kubernetes-connection-test-loading",
    }
    header = read("app/templates/components/connection_validation_header.html")
    loading = read("app/templates/components/loading_bar.html")
    assert "loading_bar.render" in header
    assert "mt-4 h-1 overflow-hidden rounded-full bg-kaori-soft" in loading
    assert "w-1/3 animate-pulse rounded-full bg-kaori-primary" in loading
    for relative, indicator_id in expectations.items():
        source = read(relative)
        assert "'Endpoint & Access'" in source
        assert f"loading_id='{indicator_id}'" in source
        assert f'hx-indicator="#{indicator_id}"' in source
        assert 'absolute bottom-2' not in source


def test_connection_validation_header_standard_is_documented() -> None:
    standard = read("docs/design/components/CONNECTION_VALIDATION_HEADER.md")
    audit = read("docs/design/audits/CONNECTION_VALIDATION_HEADER_AUDIT_2026_07.md")
    index = read("docs/design/README.md")
    assert "approximately 80 characters or fewer" in standard
    assert "one or two closely related actions" in standard
    assert "Kubernetes, Prometheus, and Alertmanager coverage" in audit
    assert "components/CONNECTION_VALIDATION_HEADER.md" in index
