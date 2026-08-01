from pathlib import Path


def test_storage_snapshot_places_top_namespace_in_full_width_bottom_row():
    template = Path('app/templates/analytics/overview/partials/_storage_snapshot.html').read_text()
    assert 'Top Namespace' in template
    assert "interpretation_grid_classes('lg:grid-cols-3')" in template
    assert 'Used Capacity' in template and 'Free Capacity' in template


def test_forecast_snapshot_places_decision_in_full_width_bottom_row():
    template = Path('app/templates/analytics/overview/partials/_forecast_snapshot.html').read_text()
    assert "interpretation_grid_classes('border-t border-outline-subtle lg:grid-cols-3')" in template
    assert 'Forecast Decision' in template
    # chart article should no longer contain the interpretation row inline
    assert template.count('Forecast Decision') == 1
