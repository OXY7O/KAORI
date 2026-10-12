from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_name_is_bounded_by_model_contract_on_client_and_server() -> None:
    service = (ROOT / 'app/reports/generate/service.py').read_text()
    template = (ROOT / 'app/templates/reports/generate/index.html').read_text()
    model = (ROOT / 'app/models/report.py').read_text()
    assert 'MAX_REPORT_NAME_LENGTH = 255' in service
    assert "name_errors = validate_report_name(form_state.get('name'))" in service
    assert 'maxlength="255"' in template
    assert 'db.String(255)' in model
