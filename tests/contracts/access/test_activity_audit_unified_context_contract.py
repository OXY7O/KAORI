from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_unified_summary_renders_one_surface_and_preserves_all_four_facts() -> None:
    detail = read('app/templates/access/activity_audit/partials/_activity_detail.html')
    shared = read('app/templates/components/details/_detail_content.html')
    assert "layout='unified', pinned=false" in detail
    assert "('Actor', item.user_label, item.user_role)" in detail
    assert "('Target', item.target_name, item.target_type)" in detail
    assert "('Recorded', item.created_at|user_datetime, item.created_label)" in detail
    assert "('Evidence', 'Activity Register', 'Notification-backed')" in detail
    assert 'data-kaori-summary-layout="unified"' in shared
    assert 'mt-3 grid min-w-0 gap-x-6 gap-y-3 border-t border-outline-subtle pt-3' in shared
    assert "'min-w-0' if unified else" in shared
    assert "'lg:col-span-2' if unified and loop.index0 == 1" in shared
    assert '[overflow-wrap:anywhere]' in shared
    assert 'target_wide = layout == ' in shared
    assert "layout='default', pinned=true" in shared


def test_audit_context_uses_full_width_values_in_two_responsive_groups() -> None:
    detail = read('app/templates/access/activity_audit/partials/_activity_detail.html')
    context = detail.split('<section data-activity-audit-context', 1)[1].split(
        '{% if item.additional_evidence %}', 1
    )[0]
    assert 'Committed actor identity and target attribution.' in context
    assert 'gap-x-8 gap-y-5 p-4 sm:grid-cols-2 sm:p-5' in context
    assert context.count('mt-3 space-y-3') == 2
    assert 'sm:grid-cols-3' not in context
    assert 'md:col-span-3' not in context
    assert 'md:col-span-2' not in context
    assert 'aria-label="Actor and Access"' in context
    assert 'aria-label="Target Context"' in context
    assert "detail_ui.stacked_detail_row('Email', item.user_email or 'Not recorded')" in context
    assert "detail_ui.stacked_detail_row('Role', item.user_role)" in context
    assert "detail_ui.stacked_detail_row('Authentication', item.user_auth_source)" in context
    assert "detail_ui.stacked_detail_row('Target Type', item.target_type)" in context
    assert "detail_ui.stacked_detail_row('Module', item.module_label)" in context

def test_evidence_authorities_and_optional_metadata_are_preserved() -> None:
    detail = read('app/templates/access/activity_audit/partials/_activity_detail.html')
    assert 'data-activity-outcome="recorded"' in detail
    assert 'data-activity-related-sources="committed-only"' in detail
    assert 'item.trace_references' in detail
    assert 'item.changed_fields' in detail
    assert "view_more.render(" in detail
    assert 'data-activity-metadata-layout="responsive-pairs"' in detail
    assert 'item.technical_evidence' in detail
    for forbidden in ('onclick=', 'hx-post=', '<form', 'style='):
        assert forbidden not in detail
