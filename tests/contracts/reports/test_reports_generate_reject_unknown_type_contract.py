from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_submission_retains_raw_report_type_for_fail_closed_validation() -> None:
    service = (ROOT / 'app/reports/generate/service.py').read_text()
    assert "'_submitted_report_type': str(form.get('report_type') or '').strip()" in service
    assert "form_state.get('_submitted_report_type', report_type) not in published_types" in service
    assert "return ['Please select a valid published report type.']" in service
    assert service.index("form_state.get('_submitted_report_type', report_type)") < service.index(
        'report_spec = get_report_type_spec(report_type)', service.index('def validate_form_state(')
    )
