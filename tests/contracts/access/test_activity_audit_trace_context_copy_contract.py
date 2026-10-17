from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_audit_context_uses_trace_reference_definition_list_pattern() -> None:
    detail = read('app/templates/access/activity_audit/partials/_activity_detail.html')
    trace = detail.split('{% if item.trace_references %}', 1)[1].split('<section data-activity-audit-context', 1)[0]
    context = detail.split('<section data-activity-audit-context', 1)[1].split('{% if item.additional_evidence %}', 1)[
        0
    ]
    assert 'grid gap-px bg-outline-subtle sm:grid-cols-2' in trace
    assert 'grid min-w-0 gap-px bg-outline-subtle sm:grid-cols-2' in context
    assert context.count('<dl class="divide-y divide-outline-subtle">') == 2
    assert context.count('<dt class="text-xs font-medium text-content-muted">') == 5
    assert context.count('text-content-primary [overflow-wrap:anywhere]') == 5
    assert 'aria-labelledby="activity-actor-context-heading"' in context
    assert 'aria-labelledby="activity-target-context-heading"' in context
    for field in ('Email', 'Role', 'Authentication', 'Target Type', 'Module'):
        assert f'>{field}</dt>' in context
    for value in (
        "{{ item.user_email or 'Not recorded' }}",
        '{{ item.user_role }}',
        '{{ item.user_auth_source }}',
        '{{ item.target_type }}',
        '{{ item.module_label }}',
    ):
        assert value in context


def test_trace_icon_matches_violet_section_identity() -> None:
    detail = read('app/templates/access/activity_audit/partials/_activity_detail.html')
    trace = detail.split('{% if item.trace_references %}', 1)[1].split('<section data-activity-audit-context', 1)[0]
    context = detail.split('<section data-activity-audit-context', 1)[1].split('{% if item.additional_evidence %}', 1)[
        0
    ]
    assert 'bg-kaori-soft text-kaori-primary' in trace
    assert 'bg-kaori-soft text-kaori-primary' in context
    assert 'bg-surface-subtle text-content-secondary' not in trace
    assert 'data-lucide="route"' in trace
    assert 'data-lucide="shield-check"' in context


def test_eight_overview_descriptions_use_approved_short_copy() -> None:
    summary = read('app/templates/access/activity_audit/partials/_activity_summary_cards.html')
    for wording in (
        'Notification-backed activity · 24h.',
        'Successful outcomes in the last 24 hours.',
        'Warnings and failures requiring review.',
        'Unique immutable actors in recent evidence.',
        'Audit metadata excludes credentials.',
        'Authorized Notification-backed activity.',
        'Hot PostgreSQL; verified Data Lifecycle archive.',
        'Actor, role and source recorded at commit.',
    ):
        assert wording in summary


def test_read_only_committed_source_and_disclosure_remain() -> None:
    detail = read('app/templates/access/activity_audit/partials/_activity_detail.html')
    assert 'data-activity-related-sources="committed-only"' in detail
    assert 'item.trace_references' in detail
    assert "layout='unified', pinned=false" in detail
    assert 'data-activity-metadata-layout="responsive-pairs"' in detail
    for forbidden in ('hx-post=', '<form', 'onclick=', 'style='):
        assert forbidden not in detail
