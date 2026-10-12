from werkzeug.datastructures import MultiDict

from app.reports.report_templates.service import create_custom_template, get_template_form_state, validate_template_form_state


def test_unknown_type_rejected_without_persistence(monkeypatch) -> None:
    monkeypatch.setattr(
        'app.reports.report_templates.service.db.session.add',
        lambda *_args: (_ for _ in ()).throw(AssertionError('must not write')),
    )
    form = MultiDict([('name', 'Bad'), ('report_type', 'unpublished'), ('status', 'active')])
    state = get_template_form_state(form)
    assert state['report_type'] == 'unpublished'
    assert 'Please select a valid report type.' in validate_template_form_state(state)
    accepted, errors, template = create_custom_template(form, None)
    assert accepted is False and template is None
    assert 'Please select a valid report type.' in errors


def test_missing_type_and_unknown_status_are_not_defaulted() -> None:
    form = MultiDict([('name', 'Untouched'), ('status', 'invalid')])
    state = get_template_form_state(form)
    assert state['report_type'] == ''
    assert state['status'] == 'invalid'
    assert 'Please select a valid report type.' in validate_template_form_state(state)
    assert 'Please select a valid template status.' in validate_template_form_state(state)


def test_known_type_does_not_mutate_submitted_status() -> None:
    from app.reports.catalog import REPORT_TYPE_SPECS
    name = REPORT_TYPE_SPECS[0].value
    state = get_template_form_state(MultiDict([('name', 'OK'), ('report_type', name), ('status', 'draft')]))
    assert state['report_type'] == name
    assert state['status'] == 'draft'
