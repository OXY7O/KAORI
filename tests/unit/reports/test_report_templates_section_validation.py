from werkzeug.datastructures import MultiDict

from app.reports.catalog import REPORT_TYPE_SPECS
from app.reports.report_templates.service import get_template_form_state, validate_template_form_state


def _type(family: str):
    return next(spec for spec in REPORT_TYPE_SPECS if spec.family == family)


def _state(report_type: str, sections: list[str]) -> dict:
    form = MultiDict([('name', 'Sections'), ('report_type', report_type), ('status', 'draft')])
    for section in sections:
        form.add('sections', section)
    return get_template_form_state(form)


def test_analytics_empty_sections_cannot_be_replaced_with_defaults() -> None:
    spec = _type('analytics')
    state = _state(spec.value, [])
    assert state['sections'] == []
    assert 'Please select at least one template section.' in validate_template_form_state(state)


def test_analytics_invalid_and_duplicate_sections_are_rejected() -> None:
    spec = _type('analytics')
    for sections in [['foreign_section'], [spec.default_sections[0], 'foreign_section'], [spec.default_sections[0]] * 2]:
        state = _state(spec.value, sections)
        assert state['sections'] == sections
        assert 'One or more selected template sections are invalid or duplicated.' in validate_template_form_state(state)


def test_valid_analytics_selection_is_accepted() -> None:
    spec = _type('analytics')
    state = _state(spec.value, [spec.default_sections[0]])
    assert not any('section' in error.lower() for error in validate_template_form_state(state))


def test_inventory_contract_is_immutable_even_when_post_is_forged() -> None:
    spec = _type('inventory')
    valid = _state(spec.value, list(spec.default_sections))
    assert 'Inventory sections are fixed by the published report contract.' not in validate_template_form_state(valid)
    changed = _state(spec.value, ['unauthorized'])
    assert 'Inventory sections are fixed by the published report contract.' in validate_template_form_state(changed)
