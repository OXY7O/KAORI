from werkzeug.datastructures import MultiDict

from app.reports.generate.service import get_form_state_from_form, validate_form_state


def test_unsupported_posted_report_type_fails_before_scope_reads(monkeypatch) -> None:
    def forbidden(*_args, **_kwargs):
        raise AssertionError('invalid type must not query a scope or create a report')

    monkeypatch.setattr('app.reports.generate.service._validate_primary_scope', forbidden)
    state = get_form_state_from_form(MultiDict([('report_type', 'unknown_contract')]))
    assert state['_submitted_report_type'] == 'unknown_contract'
    assert validate_form_state(state) == ['Please select a valid published report type.']


def test_missing_posted_type_fails_closed_before_scope_reads(monkeypatch) -> None:
    def forbidden(*_args, **_kwargs):
        raise AssertionError('missing type must not query a scope or create a report')

    monkeypatch.setattr('app.reports.generate.service._validate_primary_scope', forbidden)
    state = get_form_state_from_form(MultiDict())
    assert validate_form_state(state) == ['Please select a valid published report type.']


def test_explicit_first_published_type_is_not_mistaken_for_fallback() -> None:
    from app.reports.catalog import REPORT_TYPE_OPTIONS

    requested = REPORT_TYPE_OPTIONS[0]['value']
    state = get_form_state_from_form(MultiDict([('report_type', requested)]))
    assert state['_submitted_report_type'] == requested
    assert state['report_type'] == requested
