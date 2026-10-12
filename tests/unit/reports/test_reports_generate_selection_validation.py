from werkzeug.datastructures import MultiDict

from app.reports.catalog import REPORT_TYPE_OPTIONS
from app.reports.generate.service import (
    _validate_period_and_format,
    _validate_sections,
    get_form_state_from_form,
)


def _report_type(family: str) -> str:
    return next(item['value'] for item in REPORT_TYPE_OPTIONS if item['family'] == family)


def test_analytics_empty_posted_sections_are_not_defaulted() -> None:
    report_type = _report_type('analytics')
    state = get_form_state_from_form(MultiDict([('report_type', report_type)]), for_submission=True)
    assert state['sections'] == []
    assert 'Please select at least one report section.' in _validate_sections(state, report_type)


def test_analytics_invalid_sections_remain_visible_to_validator() -> None:
    report_type = _report_type('analytics')
    state = get_form_state_from_form(
        MultiDict([('report_type', report_type), ('sections', 'not_a_published_section')]),
        for_submission=True,
    )
    assert state['sections'] == ['not_a_published_section']
    assert 'One or more selected report sections are invalid.' in _validate_sections(state, report_type)


def test_analytics_snapshot_is_rejected_not_rewritten_to_30_days() -> None:
    report_type = _report_type('analytics')
    state = get_form_state_from_form(
        MultiDict([('report_type', report_type), ('period', 'snapshot')]),
        for_submission=True,
    )
    assert state['period'] == 'snapshot'
    assert 'Analytics reports require an explicit time range.' in _validate_period_and_format(state, report_type)


def test_inventory_content_is_locked_but_tampering_is_rejected() -> None:
    report_type = _report_type('inventory')
    state = get_form_state_from_form(
        MultiDict([('report_type', report_type), ('sections', 'invalid_section')]),
        for_submission=True,
    )
    assert state['sections'] == list(next(item['default_sections'] for item in REPORT_TYPE_OPTIONS if item['value'] == report_type))
    assert 'Inventory report sections are fixed by the published contract.' in _validate_sections(state, report_type)


def test_inventory_non_snapshot_period_is_rejected() -> None:
    report_type = _report_type('inventory')
    state = get_form_state_from_form(
        MultiDict([('report_type', report_type), ('period', '30d')]),
        for_submission=True,
    )
    assert state['period'] == '30d'
    assert 'Inventory reports require the committed snapshot period.' in _validate_period_and_format(state, report_type)
