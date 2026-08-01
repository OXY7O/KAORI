from pathlib import Path


def test_overview_posture_metrics_use_inventory_compact_scale():
    template = Path('app/templates/analytics/overview/partials/_hero_posture.html').read_text()
    assert template.count('text-lg font-semibold leading-6 text-brand-foreground') == 2
    assert 'text-2xl font-semibold text-brand-foreground' not in template
