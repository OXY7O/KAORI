import pytest
from werkzeug.datastructures import MultiDict

from app.reports.generate import service as report_service
from app.reports.generate.service import create_report_request, get_form_state_from_form, validate_form_state


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


@pytest.mark.parametrize(
    ('submitted_type', 'case'),
    [
        (None, 'missing'),
        ('', 'blank'),
        ('unknown_contract', 'unsupported'),
    ],
)
def test_invalid_report_type_post_never_persists_report_or_job_execution(
    monkeypatch, submitted_type: str | None, case: str
) -> None:
    """The actual POST service must reject before any Report/JobExecution write."""
    form = MultiDict([] if submitted_type is None else [('report_type', submitted_type)])
    attempted_writes: list[str] = []

    def forbidden_write(*_args, **_kwargs) -> None:
        attempted_writes.append('db-write')
        raise AssertionError(f'{case}: invalid report type attempted a database write')

    def forbidden_storage_check() -> None:
        raise AssertionError(f'{case}: invalid report type reached the storage/creation path')

    # For invalid POSTs every persistence call is forbidden, not just Report.add.
    # JobExecution is only dispatched by the route after a successful Report return.
    for operation in ('add', 'flush', 'commit'):
        monkeypatch.setattr(report_service.db.session, operation, forbidden_write)
    monkeypatch.setattr(report_service, 'get_report_storage_backend_status', forbidden_storage_check)

    success, errors, report = create_report_request(form, user_id=None)

    assert success is False
    assert errors == ['Please select a valid published report type.']
    assert report is None
    assert attempted_writes == []
