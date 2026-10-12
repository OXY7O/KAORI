from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_context_strip_is_inside_extracted_modal_header_not_separate_card() -> None:
    detail = read('app/templates/access/activity_audit/partials/_activity_detail.html')
    shared = read('app/templates/components/details/_detail_content.html')
    host_js = read('app/static/js/detail_rows.js')

    header_start = detail.index('<header data-resource-detail-header')
    header_close = detail.index('</header>', header_start)
    summary = detail.index('detail_ui.summary_strip([', header_start)
    body_start = detail.index('<div class="space-y-4 p-5">', header_close)
    assert header_start < summary < header_close < body_start
    assert detail.count('detail_ui.summary_strip([') == 1
    assert "layout='unified', pinned=false" in detail
    assert "('Actor', item.user_label, item.user_role)" in detail
    assert "('Target', item.target_name, item.target_type)" in detail
    assert "('Recorded', item.created_at|user_datetime, item.created_label)" in detail
    assert "('Evidence', 'Activity Register', 'Notification-backed')" in detail
    assert 'mt-3 grid min-w-0 gap-x-6 gap-y-3 border-t border-outline-subtle pt-3' in shared
    assert 'gap-y-4 rounded-xl border border-outline-subtle bg-surface-card' not in shared
    assert 'data-kaori-summary-layout="unified"' in shared
    assert "shell.querySelector(':scope > [data-resource-detail-header]')" in host_js
    assert "header.remove()" in host_js
    assert "elements.header.replaceChildren(...cloneChildren(header))" in host_js
    assert "'lg:col-span-2' if unified and loop.index0 == 1" in shared


def test_audit_context_avoids_narrow_three_way_role_and_email_columns() -> None:
    detail = read('app/templates/access/activity_audit/partials/_activity_detail.html')
    context = detail.split('<section data-activity-audit-context', 1)[1].split(
        '{% if item.additional_evidence %}', 1
    )[0]
    shared = read('app/templates/components/details/_detail_content.html')
    assert 'sm:grid-cols-2 sm:p-5' in context
    assert context.count('mt-3 space-y-3') == 2
    assert 'sm:grid-cols-3' not in context
    assert 'md:grid-cols-5' not in context
    assert "detail_ui.stacked_detail_row('Email', item.user_email or 'Not recorded')" in context
    assert "detail_ui.stacked_detail_row('Role', item.user_role)" in context
    assert "detail_ui.stacked_detail_row('Authentication', item.user_auth_source)" in context
    assert "detail_ui.stacked_detail_row('Target Type', item.target_type)" in context
    assert "detail_ui.stacked_detail_row('Module', item.module_label)" in context
    assert 'max-w-full whitespace-normal' in shared
    assert '[overflow-wrap:anywhere]' in shared


def test_read_only_committed_evidence_and_disclosure_unchanged() -> None:
    detail = read('app/templates/access/activity_audit/partials/_activity_detail.html')
    assert 'data-activity-outcome="recorded"' in detail
    assert 'data-activity-related-sources="committed-only"' in detail
    assert 'item.trace_references' in detail
    assert 'item.changed_fields' in detail
    assert 'item.execution_evidence' in detail
    assert 'item.technical_evidence' in detail
    assert 'data-activity-metadata-layout="responsive-pairs"' in detail
    for forbidden in ('onclick=', 'hx-post=', 'style=', '<form'):
        assert forbidden not in detail
