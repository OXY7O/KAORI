from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_template_post_sections_are_not_sanitized_into_defaults() -> None:
    service = (ROOT / 'app/reports/report_templates/service.py').read_text()
    parser = service.split('def get_template_form_state(', 1)[1].split('def validate_template_form_state(', 1)[0]
    validator = service.split('def validate_template_form_state(', 1)[1].split('def apply_template_state(', 1)[0]
    assert "sections = form.getlist('sections')" in parser
    assert 'sanitize_sections(' not in parser
    assert 'sections = get_default_sections(report_type)' not in parser
    assert 'selected != defaults' in validator
    assert 'len(selected) != len(set(selected))' in validator
