from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TEMPLATES = ROOT / "app" / "templates" / "analytics" / "alerts" / "partials"


def _read(name: str) -> str:
    return (TEMPLATES / name).read_text(encoding="utf-8")


def test_search_placeholder_is_compact() -> None:
    template = _read("_filters.html")
    assert 'placeholder="Search signals..."' in template
    assert "Search alert, pod, node, namespace" not in template


def test_anomaly_column_and_namespace_row_are_not_redundant() -> None:
    table = _read("_anomalies_table.html")
    row = _read("_anomalies_table_row.html")
    assert ">Anomaly</div>" in table
    assert "Anomaly &amp; Namespace" not in table
    assert 'data-lucide="box"' not in row
    assert "{{ anomaly.namespace }}" in row


def test_ownership_workspace_uses_compact_internal_sections() -> None:
    ownership = _read("_ownership_summary.html")
    readiness = _read("_incident_readiness.html")
    assert "Coverage Score" in ownership
    assert "Owner Distribution" in ownership
    assert "Runbook Coverage" in ownership
    assert "Metadata Gaps" in ownership
    assert "Escalation Readiness" in readiness
    assert "grid min-w-full gap-3 sm:grid-cols-2" in readiness
    assert "p-5 sm:p-6" not in ownership
    assert "p-5 sm:p-6" not in readiness
