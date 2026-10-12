from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text(encoding='utf-8')


def test_catalog_hero_and_summary_refresh_out_of_band() -> None:
    page = read('app/templates/intelligence/rule_catalog.html')
    hero = read('app/templates/intelligence/partials/_catalog_hero_posture.html')
    results = read('app/templates/intelligence/partials/_catalog_results.html')
    assert "include 'intelligence/partials/_catalog_hero_posture.html'" in page
    assert 'id="catalog-hero-posture"' in hero
    assert 'hx-swap-oob="outerHTML"' in hero
    assert "include 'intelligence/partials/_catalog_hero_posture.html'" in results
    assert 'id="catalog-summary-section"' in results


def test_catalog_posture_uses_scoped_result_context_not_global_catalog() -> None:
    source = read('app/intelligence/service.py')
    assert "'matched_domains': len({str(item.get('domain')) for item in filtered if item.get('domain')})" in source
    assert "context = payload['result_context']" in source
    assert "label, tone = 'No Matching Rules', 'unknown'" in source
    assert "label, tone = 'Reserved Plan', 'unknown'" in source
    assert "label, tone = 'Imported Signal', 'info'" in source
