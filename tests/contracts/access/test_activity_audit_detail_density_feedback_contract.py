from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_long_identity_context_uses_shared_responsive_summary_variant() -> None:
    detail = read('app/templates/access/activity_audit/partials/_activity_detail.html')
    shared = read('app/templates/components/details/_detail_content.html')
    modal = read('app/static/js/detail_rows.js')

    assert "layout='target-wide', pinned=false" in detail
    assert "('Target', item.target_name, item.target_type)" in detail
    assert "('Recorded', item.created_at|user_datetime, item.created_label)" in detail
    assert "('Evidence', 'Activity Register', 'Notification-backed')" in detail
    assert "layout='default', pinned=true" in shared
    assert "data-kaori-summary-layout=\"target-wide\"" in shared
    assert "xl:grid-cols-[minmax(0,1.05fr)_minmax(0,1.45fr)_minmax(0,0.95fr)_minmax(0,0.85fr)]" in shared
    assert '{% if pinned %}data-resource-detail-summary{% endif %}' in shared
    assert '[overflow-wrap:anywhere]' in shared
    assert "shell.querySelector(':scope > [data-resource-detail-summary]')" in modal
    assert "elements.content.replaceChildren(...cloneChildren(shell))" in modal


def test_failure_summary_uses_labelled_rows_without_nested_card() -> None:
    detail = read('app/templates/access/activity_audit/partials/_activity_detail.html')
    start = detail.index('data-activity-outcome="recorded"')
    end = detail.index('{% if item.detail and item.detail != item.message', start)
    outcome = detail[start:end]
    assert 'Recorded Outcome' in outcome
    assert 'Recorded Impact' in outcome
    assert 'border-t border-outline-subtle pt-3' in outcome
    assert 'rounded-lg border border-outline-subtle bg-surface-elevated px-4 py-3.5' not in outcome
    assert '{% if item.failure_context %}' in outcome
    assert 'No separate failure-context fields are available' in outcome
    assert 'Next Review Step' in outcome


def test_context_stacks_left_aligned_values_without_table_right_alignment() -> None:
    detail = read('app/templates/access/activity_audit/partials/_activity_detail.html')
    shared = read('app/templates/components/details/_detail_content.html')
    start = detail.index('<section data-activity-audit-context')
    end = detail.index('{% if item.additional_evidence %}', start)
    context = detail[start:end]
    assert 'gap-x-10 gap-y-6 p-4 sm:p-5 md:grid-cols-2' in context
    assert "detail_ui.stacked_detail_row('Email', item.user_email or 'Not recorded')" in context
    assert "detail_ui.stacked_detail_row('Role', item.user_role)" in context
    assert "detail_ui.stacked_detail_row('Authentication', item.user_auth_source)" in context
    assert "detail_ui.stacked_detail_row('Target Type', item.target_type)" in context
    assert "detail_ui.stacked_detail_row('Module', item.module_label)" in context
    assert 'detail_ui.detail_row(' not in context
    assert "overflow-wrap:anywhere" in shared


def test_optional_metadata_displays_long_fields_as_open_two_column_rows() -> None:
    detail = read('app/templates/access/activity_audit/partials/_activity_detail.html')
    start = detail.index('{% if item.additional_evidence %}')
    end = detail.index('{% if item.technical_evidence %}', start)
    additional = detail[start:end]
    assert "view_more.render(" in additional
    assert "open_by_default=false" in additional
    assert 'data-activity-metadata-layout="responsive-pairs"' in additional
    assert 'grid min-w-0 gap-x-8 sm:grid-cols-2' in additional
    assert '{% for evidence in item.additional_evidence %}' in additional
    assert 'detail_ui.stacked_detail_row(evidence.label, evidence.value)' in additional
    assert 'evidence.supporting is defined and evidence.supporting' in additional
    assert 'detail_ui.evidence_grid(item.additional_evidence' not in additional
    assert 'break-words text-xs leading-5 text-content-muted [overflow-wrap:anywhere]' in additional


def test_read_only_security_and_committed_links_remain_unchanged() -> None:
    detail = read('app/templates/access/activity_audit/partials/_activity_detail.html')
    assert 'data-activity-related-sources="committed-only"' in detail
    assert 'No duplicate event is created.' in detail
    assert 'item.failure_summary' in detail
    assert 'item.changed_fields' in detail
    assert 'item.trace_references' in detail
    assert 'item.execution_evidence' in detail
    assert "'View Technical Evidence'" in detail
    for forbidden in ('hx-post=', 'onclick=', 'style=', '<form'):
        assert forbidden not in detail
