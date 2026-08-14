from pathlib import Path

PARTIALS = [
    '_workload_snapshot.html',
    '_storage_snapshot.html',
    '_top_consumers_snapshot.html',
    '_forecast_snapshot.html',
    '_alerts_snapshot.html',
    '_actionable_recommendation_summary.html',
]


def test_overview_domain_guidance_uses_shared_interpretation_callout():
    base = Path('app/templates/analytics/kubernetes/overview/partials')
    for name in PARTIALS:
        text = (base / name).read_text()
        assert 'overview_surface.interpretation_callout(' in text, name


def test_shared_analysis_surface_owns_interpretation_callout():
    text = Path('app/templates/analytics/components/_analysis_surfaces.html').read_text()
    assert '{% macro interpretation_callout(' in text
