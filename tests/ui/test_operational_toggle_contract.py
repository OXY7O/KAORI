from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_shared_operational_toggle_contract() -> None:
    source = read("app/templates/components/operational_toggle.html")
    assert "macro render(" in source
    assert "tone == 'warning'" in source
    assert "tone == 'critical'" in source
    assert "border-outline-default bg-surface-card" in source
    assert "min-h-20" in source
    assert "caller()" in source


def test_equivalent_prometheus_and_alertmanager_toggles_use_shared_neutral_component() -> None:
    for relative in (
        "app/templates/prometheus/instance_form.html",
        "app/templates/alertmanager/instance_form.html",
        "app/templates/alertmanager/partials/_detail_configuration.html",
    ):
        source = read(relative)
        assert 'components/operational_toggle.html' in source
        assert "operational_toggle.render(" in source
        assert "Verify TLS Certificate" in source
        assert "Allow KAORI to Use This Connection" in source
        assert "tone='warning'" not in source

    for relative in (
        "app/templates/prometheus/config.html",
        "app/templates/alertmanager/config.html",
    ):
        source = read(relative)
        assert 'components/operational_toggle.html' in source
        assert "operational_toggle.render(" in source
        assert "Verify TLS Certificate" in source
        assert "tone='warning'" not in source


def test_kubernetes_legacy_tls_is_the_explicit_warning_exception() -> None:
    source = read("app/templates/cluster/partials/_form.html")
    assert "Verify Kubernetes API TLS Certificate" in source
    assert "Allow Legacy TLS Certificate" in source
    assert "tone='warning'" in source
    assert source.count("operational_toggle.render(") == 2


def test_operational_toggle_standard_is_documented() -> None:
    standard = read("docs/design/components/OPERATIONAL_TOGGLE.md")
    audit = read("docs/design/audits/OPERATIONAL_TOGGLE_AUDIT_2026_07.md")
    index = read("docs/design/README.md")
    assert "security-related label does not automatically receive" in standard
    assert "Allow Legacy TLS Certificate" in audit
    assert "components/OPERATIONAL_TOGGLE.md" in index
