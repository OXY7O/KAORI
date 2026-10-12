from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_generate_cta_requires_exact_destination_permission() -> None:
    template = (ROOT / 'app/templates/reports/report_templates/index.html').read_text()
    routes = (ROOT / 'app/reports/generate/routes.py').read_text()
    assert "template.can_generate and current_user.has_permission('reports.generate')" in template
    assert 'Generate Access Required' in template
    assert 'Activate to Generate' in template
    assert "@permission_required('reports.generate')" in routes
