from pathlib import Path


def test_generated_reports_handoff_matches_destination_permission():
    root = Path(__file__).resolve().parents[3]
    page = (root / 'app/templates/reports/storage/index.html').read_text()
    generated = (root / 'app/reports/generated/routes.py').read_text()
    assert "{% if current_user.has_permission('reports.view') %}" in page
    guarded = page.split("url_for('reports.generated_reports')", 1)[0]
    assert "current_user.has_permission('reports.view')" in guarded[-170:]
    assert "@permission_required('reports.view')" in generated
