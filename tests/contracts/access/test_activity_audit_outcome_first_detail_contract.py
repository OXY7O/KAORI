from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_warning_or_error_outcome_precedes_secondary_activity_and_metadata() -> None:
    detail = read('app/templates/access/activity_audit/partials/_activity_detail.html')
    assert "{% if item.failure_summary %}" in detail
    assert 'data-activity-outcome="recorded"' in detail
    assert 'aria-labelledby="activity-outcome-heading"' in detail
    assert "item.status == 'error'" in detail
    assert detail.index('data-activity-outcome="recorded"') < detail.index('Activity Detail')
    assert detail.index('data-activity-outcome="recorded"') < detail.index('Execution Evidence')
    assert detail.index('data-activity-outcome="recorded"') < detail.index('Trace References')
    assert detail.index('data-activity-outcome="recorded"') < detail.index('data-activity-audit-context')
    assert "item.failure_type != 'Operational Failure'" in detail
    assert 'Recorded Outcome' in detail
    assert 'item.message != item.failure_summary' in detail
    assert '{% if not item.failure_summary %}' in detail


def test_absent_or_present_failure_context_does_not_invent_blockers() -> None:
    detail = read('app/templates/access/activity_audit/partials/_activity_detail.html')
    assert '{% if item.failure_context %}' in detail
    assert 'detail_ui.evidence_grid(item.failure_context, columns=3, compact=true)' in detail
    assert 'No separate failure-context fields are available in this Activity Register entry.' in detail
    assert 'Next Review Step' in detail
    assert 'This guidance does not confirm a root cause or authorize mutation.' in detail
    assert 'before deciding whether to retry' in detail
    assert '4 blocker(s)' not in detail
    assert 'No provider resource was modified.' not in detail
    assert 'Review the related configuration, target availability, and trace references before retrying.' not in detail


def test_audit_identity_and_source_evidence_remain_present() -> None:
    detail = read('app/templates/access/activity_audit/partials/_activity_detail.html')
    assert "('Evidence', 'Activity Register', 'Notification-backed')" in detail
    assert 'item.created_at|user_datetime' in detail
    assert 'Actor & Access' in detail
    assert 'Target Context' in detail
    assert "detail_ui.detail_row('Email', item.user_email or 'Not recorded')" in detail
    assert "detail_ui.detail_row('Authentication', item.user_auth_source)" in detail
    assert "detail_ui.detail_row('Module', item.module_label)" in detail
    assert 'data-activity-related-sources="committed-only"' in detail
    assert 'No duplicate event is created.' in detail
    assert 'item.trace_references' in detail
    assert 'item.changed_fields' in detail
    assert 'item.execution_evidence' in detail
    assert 'item.technical_evidence' in detail
    assert 'detail_ui.evidence_grid(item.additional_evidence, columns=3, compact=true)' in detail


def test_optional_evidence_uses_shared_accessible_disclosure_not_custom_js() -> None:
    detail = read('app/templates/access/activity_audit/partials/_activity_detail.html')
    assert "{% import \"components/view_more_content.html\" as view_more %}" in detail
    assert "'Additional Evidence'" in detail
    assert "aria_label='Additional Evidence'" in detail
    assert "'Technical Evidence'" in detail
    assert 'open_by_default=false' in detail
    assert 'View Additional Evidence' in detail
    assert 'View Technical Evidence' in detail
    for prohibited in ('onclick=', 'hx-post=', '<form', 'style='):
        assert prohibited not in detail
