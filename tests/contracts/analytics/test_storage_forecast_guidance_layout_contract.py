from pathlib import Path


def test_storage_snapshot_fills_lower_left_area_with_guidance_blocks():
    template = Path('app/templates/analytics/overview/partials/_storage_snapshot.html').read_text()
    assert 'How To Read' in template
    assert 'What To Watch' in template
    assert 'overview_surface.interpretation_callout(' in template


def test_forecast_decision_moves_into_interpretation_row():
    template = Path('app/templates/analytics/overview/partials/_forecast_snapshot.html').read_text()
    assert "interpretation_grid_classes('mt-4 rounded-lg border border-outline-subtle lg:grid-cols-3')" in template
    assert 'Forecast Decision' in template
    assert "guidance_card_classes('mt-4 flex items-start gap-3 p-3')" not in template
