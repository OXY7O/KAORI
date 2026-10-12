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
