from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERO_FILES = [
    "app/templates/analytics/overview/partials/_hero_posture.html",
    "app/templates/analytics/alerts/partials/_hero.html",
    "app/templates/analytics/capacity/partials/_hero.html",
    "app/templates/analytics/storage/partials/_hero.html",
    "app/templates/analytics/top_consumers/partials/_hero.html",
    "app/templates/analytics/utilization/partials/_hero.html",
    "app/templates/analytics/workload/partials/_hero.html",
    "app/templates/analytics/forecast/index.html",
]


def test_shared_posture_note_has_standard_minimum_height_and_readable_copy():
    source = (ROOT / "app/templates/components/page_hero.html").read_text()
    assert "macro context_posture_note" in source
    assert "min-h-11" in source
    assert "text-xs font-semibold leading-5" in source
    assert "border-brand-outline bg-brand-surface" in source


def test_all_kubernetes_analytics_heroes_use_shared_posture_note():
    for relative_path in HERO_FILES:
        source = (ROOT / relative_path).read_text()
        assert "page_hero.context_posture_note(" in source, relative_path
        assert 'class="mt-2 text-xs leading-5 text-brand-foreground-muted"' not in source
        assert 'class="mt-2 text-sm leading-5 text-brand-foreground-muted"' not in source
