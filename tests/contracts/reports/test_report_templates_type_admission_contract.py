from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_posted_type_and_status_are_not_silently_normalized() -> None:
    service = (ROOT / 'app/reports/report_templates/service.py').read_text()
    parse = service.split('def get_template_form_state(', 1)[1].split('def validate_template_form_state(', 1)[0]
    validate = service.split('def validate_template_form_state(', 1)[1].split('def apply_template_state(', 1)[0]
    assert "report_type = str(form.get('report_type') or '').strip()" in parse
    assert "'status': str(form.get('status') or '').strip()" in parse
    assert 'normalize_report_type(' not in parse
    assert 'normalize_template_status(' not in parse
    assert "if form_state['report_type'] not in get_allowed_report_types():\n        return errors" in validate
