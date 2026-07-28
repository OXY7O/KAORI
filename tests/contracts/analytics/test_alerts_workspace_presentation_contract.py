from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
TEMPLATES = ROOT / "app" / "templates"


def _read(relative: str) -> str:
    return (TEMPLATES / relative).read_text(encoding="utf-8")


def test_cluster_signal_overview_is_outside_workspace_tabs() -> None:
    template = _read("analytics/alerts/index.html")

    overview_include = '{% include "analytics/alerts/partials/_cluster_signal_overview.html" %}'
    workspace = "Alerts &amp; Anomalies Workspace"

    assert overview_include in template
    assert workspace in template
    assert template.index(overview_include) < template.index(workspace)
    assert "('signals', 'Signal Overview'" not in template
    assert "embedded=true" in template


def test_alert_controls_include_both_provider_statuses() -> None:
    controls = _read("analytics/alerts/partials/_filters.html")
    source_status = _read("analytics/alerts/partials/_source_status.html")

    assert "Alert Controls &amp; Source Readiness" in controls
    assert '_source_status.html" %}' in controls
    assert "Alertmanager" in source_status
    assert "Prometheus" in source_status
    assert "Primary Source" in source_status
    assert "Fallback Source" in source_status
    assert "Signal Control &amp; Source Health" not in source_status


def test_workspace_tabs_and_content_share_one_container() -> None:
    template = _read("analytics/alerts/index.html")
    tabs = _read("analytics/components/_content_tabs.html")

    assert 'class="overflow-hidden rounded-xl border border-outline-default bg-surface-card shadow-sm"' in template
    assert "analytics_content_tabs.render" in template
    assert "embedded=true" in template
    assert "embedded=false" in tabs
    assert "border-b border-outline-subtle" in tabs


def test_redundant_lens_cards_and_expandables_are_removed() -> None:
    files = [
        "analytics/alerts/partials/_routing_summary.html",
        "analytics/alerts/partials/_silence_inhibition_summary.html",
        "analytics/alerts/partials/_ownership_summary.html",
        "analytics/alerts/partials/_incident_readiness.html",
        "analytics/alerts/partials/_recommendations.html",
    ]
    content = "\n".join(_read(path) for path in files)

    for phrase in (
        "Routing lens",
        "Noise-control lens",
        "Triage ownership lens",
        "Incident decision lens",
        "What this means",
        "<details",
        "<summary",
    ):
        assert phrase not in content


def test_cluster_overview_uses_compact_signal_summary() -> None:
    overview = _read("analytics/alerts/partials/_cluster_signal_overview.html")

    assert "Cluster Signal Overview" in overview
    assert "Active Alerts" in overview
    assert "Critical Alerts" in overview
    assert "Warning Alerts" in overview
    assert "Dominant Signal" in overview
    assert "Signal Distribution" not in overview
    assert "truncate" not in overview
    assert "whitespace-nowrap" not in overview


def test_external_alertmanager_action_uses_standard_button() -> None:
    recommendations = _read("analytics/alerts/partials/_recommendations.html")

    assert 'components/action_button.html' in recommendations
    assert "action_button.classes('secondary')" in recommendations
    assert 'target="_blank"' in recommendations
    assert 'rel="noopener noreferrer"' in recommendations


def test_invalid_utility_fragments_are_removed() -> None:
    alerts_table = _read("analytics/alerts/partials/_alerts_table.html")
    anomalies_table = _read("analytics/alerts/partials/_anomalies_table.html")
    content = alerts_table + anomalies_table

    assert " /60" not in content
