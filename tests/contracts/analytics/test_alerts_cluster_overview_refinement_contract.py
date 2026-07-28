from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
TEMPLATES = ROOT / "app" / "templates"


def _read(relative: str) -> str:
    return (TEMPLATES / relative).read_text(encoding="utf-8")


def test_alert_search_icon_uses_input_relative_alignment() -> None:
    controls = _read("analytics/alerts/partials/_filters.html")

    assert 'class="relative mt-1 block"' in controls
    assert 'absolute inset-y-0 left-0 flex w-10 items-center justify-center' in controls
    assert "top-[37px]" not in controls
    assert 'class="h-10 w-full min-w-0' in controls


def test_cluster_overview_uses_consolidated_workspace_layout() -> None:
    overview = _read("analytics/alerts/partials/_cluster_signal_overview.html")

    assert "Cluster Signal Overview" in overview
    assert "Investigation Posture" in overview
    assert "Signal Summary" in overview
    assert "Recommended Focus" in overview
    assert "Current alert and anomaly counts without repeating distribution cards." in overview


def test_cluster_overview_removes_repeated_progress_cards() -> None:
    overview = _read("analytics/alerts/partials/_cluster_signal_overview.html")

    assert 'components/progress_bar.html' not in overview
    assert "progress_bar.bar" not in overview
    assert "Signal Distribution" not in overview
    assert "truncate" not in overview
    assert "whitespace-nowrap" not in overview


def test_cluster_overview_keeps_provider_and_fallback_context() -> None:
    overview = _read("analytics/alerts/partials/_cluster_signal_overview.html")

    assert "overview.source|title" in overview
    assert "overview.connected" in overview
    assert "overview.fallback_used" in overview
    assert "overview.fallback_reason" in overview
