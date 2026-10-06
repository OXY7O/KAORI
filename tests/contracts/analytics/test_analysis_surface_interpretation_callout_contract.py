from pathlib import Path


def test_analysis_surfaces_owns_interpretation_callout_macro():
    surface = Path('app/templates/analytics/components/_analysis_surfaces.html').read_text()
    assert '{% macro interpretation_callout(' in surface

    for template_path in (
        'app/templates/kubernetes/analytics/overview/partials/_health_summary.html',
        'app/templates/kubernetes/analytics/overview/partials/_resource_snapshot.html',
    ):
        template = Path(template_path).read_text()
        assert 'analytics/components/_analysis_surfaces.html' in template
        assert 'overview_surface.interpretation_callout(' in template
