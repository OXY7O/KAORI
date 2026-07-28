from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = ROOT / 'app/templates/analytics/forecast/partials/_overview_methodology.html'


def test_forecast_overview_methodology_uses_single_compact_workspace() -> None:
    content = TEMPLATE.read_text(encoding='utf-8')

    assert 'Projected Capacity Posture' in content
    assert 'xl:grid-cols-6' in content
    assert "('Warning', warning_count" in content
    assert "('Model', forecast_payload.method_label" in content
    assert 'xl:grid-cols-3' not in content
    assert 'xl:col-span-2' not in content


def test_methodology_is_presented_as_compact_metadata_not_tall_panel() -> None:
    content = TEMPLATE.read_text(encoding='utf-8')

    assert "selected_history_window ~ ' history'" in content
    assert "selected_forecast_horizon ~ ' horizon'" in content
    assert 'Methodology Boundary' not in content
    assert 'mt-5 divide-y' not in content
