from pathlib import Path


def test_analytics_overview_hero_caps_metadata_and_uses_manage_clusters_action():
    hero = Path('app/templates/kubernetes/analytics/overview/partials/_hero.html').read_text()
    assert "page_hero.analytics_metadata('server'" in hero
    assert 'hero_secondary_icon = "clock-3"' in hero
    assert 'hero_tertiary_icon = "bell"' in hero
    assert 'hero_tertiary_label = "Blocked Readiness"' in hero
    assert "page_hero.meta_label('" not in hero
    assert 'list-checks' not in hero

    posture = Path('app/templates/kubernetes/analytics/overview/partials/_hero_posture.html').read_text()
    assert 'page_hero.context_card_body(' in posture
    assert "'Analytics Status'" in posture
    assert 'metrics[:2]' in Path('app/templates/components/page_hero.html').read_text()
    assert "url_for('integrations.kubernetes')" in posture
    assert 'Manage Clusters' in posture
    assert 'context_bottom_notice' not in posture


def test_overview_guidance_blocks_use_icon_led_callouts():
    surface = Path('app/templates/analytics/components/_analysis_surfaces.html').read_text()
    assert 'macro interpretation_callout' in surface

    health = Path('app/templates/kubernetes/analytics/overview/partials/_health_summary.html').read_text()
    resource = Path('app/templates/kubernetes/analytics/overview/partials/_resource_snapshot.html').read_text()
    assert 'overview_surface.interpretation_callout(' in health
    assert 'overview_surface.interpretation_callout(' in resource
