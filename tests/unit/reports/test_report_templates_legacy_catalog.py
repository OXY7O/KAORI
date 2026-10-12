from types import SimpleNamespace

from app.reports.report_templates.service import get_custom_template_contract_errors


def test_removed_report_type_remains_reviewable_without_fallback() -> None:
    record = SimpleNamespace(
        report_type='retired_2024', output_format='pdf',
        status='active', sections_as_list=lambda: ['old_section'],
    )
    assert get_custom_template_contract_errors(record) == [
        'Report type is no longer published in the canonical catalog.'
    ]


def test_valid_current_type_is_not_flagged() -> None:
    from app.reports.catalog import REPORT_TYPE_SPECS
    spec = REPORT_TYPE_SPECS[0]
    record = SimpleNamespace(
        report_type=spec.value, output_format=spec.default_format,
        status='active', sections_as_list=lambda: list(spec.default_sections),
    )
    assert get_custom_template_contract_errors(record) == []


def test_malformed_sections_are_recorded_as_invalid_without_runtime_crash() -> None:
    from app.reports.catalog import REPORT_TYPE_SPECS
    spec = REPORT_TYPE_SPECS[0]
    record = SimpleNamespace(
        report_type=spec.value, output_format=spec.default_format,
        status='active', sections_as_list=lambda: [{'non_string': True}],
    )
    assert 'Stored section selection no longer matches the canonical contract.' in (
        get_custom_template_contract_errors(record)
    )


def test_legacy_edit_form_ignores_nested_section_values_without_503() -> None:
    from app.reports.catalog import REPORT_TYPE_SPECS
    from app.reports.report_templates.service import get_template_form_context
    spec = REPORT_TYPE_SPECS[0]
    record = SimpleNamespace(
        id=99, name='Legacy', description=None, report_type=spec.value,
        status='draft', output_format=spec.default_format, source_template_key='system:legacy',
        sections_as_list=lambda: [{'nested': 'not a section'}, spec.default_sections[0]],
    )
    state = get_template_form_context(record)
    assert state['sections'] == [spec.default_sections[0]]
    assert state['id'] == 99
