from pathlib import Path


def test_overview_posture_metrics_use_inventory_compact_scale() -> None:
    posture = Path('app/templates/kubernetes/analytics/overview/partials/_hero_posture.html').read_text()
    shared = Path('app/templates/components/page_hero.html').read_text()

    assert 'page_hero.context_card_body(' in posture
    assert 'metrics[:2]' in shared
    assert 'text-lg font-semibold leading-6 text-brand-foreground' in shared
    assert 'text-2xl font-semibold text-brand-foreground' not in posture
