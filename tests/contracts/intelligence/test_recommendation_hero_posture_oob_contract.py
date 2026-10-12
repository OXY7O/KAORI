from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_recommendation_hero_and_summary_update_together_on_htmx_filters() -> None:
    page = read('app/templates/intelligence/recommendations.html')
    results = read('app/templates/intelligence/partials/_recommendations_results.html')
    hero = read('app/templates/intelligence/partials/_recommendation_hero_posture.html')
    assert "_recommendation_hero_posture.html" in page
    assert "_recommendation_hero_posture.html" in results
    assert "_recommendation_workspace_info.html" in results
    assert 'id="recommendation-hero-posture"' in hero
    assert 'hx-swap-oob="outerHTML"' in hero
    assert 'payload.summary.actionable' in hero
    assert 'payload.posture.label' in hero
    assert 'page_hero.context_card' in hero


def test_recommendation_hero_posture_is_responsive_grid_child() -> None:
    hero = read('app/templates/intelligence/partials/_recommendation_hero_posture.html')
    shared_hero = read('app/templates/components/page_hero.html')
    assert 'id="recommendation-hero-posture"\n     class="{{ page_hero.aside_classes() }}"' in hero
    assert 'xl:col-span-5' in shared_hero
