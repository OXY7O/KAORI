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
    assert 'data-kaori-summary-layout="unified"' in shared
    assert 'grid min-w-0 gap-px overflow-hidden rounded-lg border border-outline-subtle' in shared
    assert "'xl:col-span-2' if target_wide and loop.index0 == 1" in shared
    assert 'min-w-0 bg-surface-card px-4 py-3 sm:px-5 sm:py-3.5' in shared
    assert 'data-kaori-summary-layout="target-wide"' in shared
    assert '{% if pinned %}data-resource-detail-summary{% endif %}' in shared
    assert '[overflow-wrap:anywhere]' in shared
    assert "shell.querySelector(':scope > [data-resource-detail-summary]')" in modal
    assert 'elements.content.replaceChildren(...cloneChildren(shell))' in modal


def test_failure_summary_uses_wrapped_evidence_text_and_labelled_rows() -> None:
    detail = read('app/templates/access/activity_audit/partials/_activity_detail.html')
    start = detail.index('data-activity-outcome="recorded"')
    end = detail.index('{% if item.detail and item.detail != item.message', start)
    outcome = detail[start:end]
    assert 'Recorded Outcome' in outcome
    assert 'data-activity-recorded-outcome-text' in outcome
    assert 'rounded-lg bg-surface-elevated' in outcome
    assert 'whitespace-pre-wrap break-words' in outcome
    assert '[overflow-wrap:anywhere]">{{ item.failure_summary }}</p>' in outcome
    assert 'truncate' not in outcome and 'line-clamp' not in outcome
    assert 'Recorded Impact' in outcome
    assert 'border-t border-outline-subtle pt-3' in outcome
    assert 'rounded-lg border border-outline-subtle bg-surface-elevated px-4 py-3.5' not in outcome
    assert '{% if item.failure_context %}' in outcome
    assert 'No separate failure-context fields are available' in outcome
    assert 'Next Review Step' in outcome


def test_context_uses_full_width_trace_style_rows_for_long_identity_text() -> None:
    detail = read('app/templates/access/activity_audit/partials/_activity_detail.html')
    start = detail.index('<section data-activity-audit-context')
    end = detail.index('{% if item.additional_evidence %}', start)
    context = detail[start:end]
    assert 'grid min-w-0 gap-px bg-outline-subtle sm:grid-cols-2' in context
    assert context.count('<dl class="divide-y divide-outline-subtle">') == 2
    assert context.count('<dt class="text-xs font-medium text-content-muted">') == 5
    assert context.count('[overflow-wrap:anywhere]') == 5
    assert 'Actor & Access' in context
    assert 'Target Context' in context
    assert 'sm:grid-cols-3' not in context
    for value in (
        "{{ item.user_email or 'Not recorded' }}",
        '{{ item.user_role }}',
        '{{ item.user_auth_source }}',
        '{{ item.target_type }}',
        '{{ item.module_label }}',
    ):
        assert value in context


def test_optional_metadata_displays_long_fields_as_open_two_column_rows() -> None:
    detail = read('app/templates/access/activity_audit/partials/_activity_detail.html')
    start = detail.index('{% if item.additional_evidence %}')
    end = detail.index('{% if item.technical_evidence %}', start)
    additional = detail[start:end]
    assert 'view_more.render(' in additional
    assert 'open_by_default=false' in additional
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


def test_long_activity_and_technical_values_remain_wrapped_and_unclipped() -> None:
    detail = read('app/templates/access/activity_audit/partials/_activity_detail.html')
    for expression in ('item.failure_summary', 'item.message', 'item.detail', 'evidence.value'):
        assert f'[overflow-wrap:anywhere]">{{{{ {expression} }}}}</p>' in detail
    assert '[overflow-wrap:anywhere]">{{ source.label }}</p>' in detail
    assert '[overflow-wrap:anywhere]">{{ source.note }}</p>' in detail
    assert '[overflow-wrap:anywhere]">{{ field.label }}</p>' in detail
    assert 'whitespace-nowrap' not in detail
    assert '|truncate' not in detail
    assert '|safe' not in detail
