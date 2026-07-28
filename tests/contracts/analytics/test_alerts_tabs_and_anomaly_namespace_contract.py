from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
TEMPLATES = ROOT / "app" / "templates"


def _read(relative: str) -> str:
    return (TEMPLATES / relative).read_text(encoding="utf-8")


def test_anomaly_summary_uses_namespace_instead_of_description() -> None:
    table = _read("analytics/alerts/partials/_anomalies_table.html")
    row = _read("analytics/alerts/partials/_anomalies_table_row.html")
    summary = row.split('id="{{ row_key }}-details"', maxsplit=1)[0]

    assert ">Anomaly</div>" in table
    assert "Anomaly &amp; Namespace" not in table
    assert "Signal Context" in table
    assert "{{ anomaly.namespace }}" in summary
    assert "{{ anomaly.description }}" not in summary
    assert "{{ anomaly.description }}" in row
    assert "{{ anomaly.target }}" in summary


def test_routing_and_ownership_are_dedicated_primary_tabs() -> None:
    index = _read("analytics/alerts/index.html")

    assert "('routing', 'Routing & Suppression', 'route')" in index
    assert "('ownership', 'Ownership & Runbook Coverage', 'book-open-check')" in index
    assert "alerts-content-panel-routing" in index
    assert "alerts-content-panel-ownership" in index
    assert "alerts-content-panel-readiness" not in index
    assert "activeTab === 'ownership'" in index


def test_routing_tab_uses_one_divided_workspace() -> None:
    index = _read("analytics/alerts/index.html")
    routing = _read("analytics/alerts/partials/_routing_summary.html")
    suppression = _read("analytics/alerts/partials/_silence_inhibition_summary.html")

    assert "Routing &amp; Suppression" in index
    assert "overflow-hidden rounded-xl border border-outline-default" in index
    assert "<section" not in routing
    assert "<section" not in suppression
    assert "Active Silence Scope" in suppression
    assert "Inhibition Policy Readiness" in suppression
    assert "Active Silence Records" in suppression


def test_ownership_tab_uses_one_divided_workspace() -> None:
    index = _read("analytics/alerts/index.html")
    ownership = _read("analytics/alerts/partials/_ownership_summary.html")
    readiness = _read("analytics/alerts/partials/_incident_readiness.html")

    assert "Ownership &amp; Runbook Coverage" in index
    assert "Coverage Score" in ownership
    assert "Runbook Coverage" in ownership
    assert "Metadata Gaps" in ownership
    assert "Escalation Readiness" in readiness
    assert "rounded-xl border border-outline-default" not in ownership
    assert "rounded-xl border border-outline-default" not in readiness
    assert "p-5 sm:p-6" not in ownership
    assert "p-5 sm:p-6" not in readiness
