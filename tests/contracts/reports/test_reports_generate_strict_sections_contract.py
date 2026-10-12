from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_posted_sections_and_period_are_preserved_for_backend_validation() -> None:
    service = (ROOT / 'app/reports/generate/service.py').read_text()
    routes = (ROOT / 'app/reports/generate/routes.py').read_text()
    assert "for_submission: bool = False" in service
    assert "sections = submitted_sections" in service
    assert "elif for_submission:" in service
    assert "form_state = get_form_state_from_form(request.form, for_submission=True)" in routes
    assert "form, for_submission=True" in service
    assert "Analytics reports require an explicit time range." in service
    assert "Inventory report sections are fixed by the published contract." in service
