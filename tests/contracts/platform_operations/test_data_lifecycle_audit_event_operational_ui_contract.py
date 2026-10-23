"""Administrative Audit Events permanent operations UI contracts (#2943).

This validates source/Jinja design and server guard invariants; actual
PostgreSQL/Celery/Archive Storage and browser acceptance are separate.
"""
from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[3]
WORKSPACE = 'app/templates/platform_operations/data_lifecycle/partials/_domain_workspace.html'


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_audit_event_policy_uses_canonical_components_and_accessible_guide() -> None:
    ui = read(WORKSPACE)
    Environment().parse(ui)
    assert 'components/table.html' in ui
    assert 'components/info_tip.html' in ui
    assert 'components/operation_feedback_oob.html' in ui
    assert "info_tip.render('data-lifecycle-audit-event-policy-guide'," in ui
    assert "info_tip.render('data-lifecycle-audit-event-safety'," in ui
    assert "variant='guide'" in ui
    assert 'Only an active Local Database Super Admin may operate this policy.' in ui


def test_manual_only_domain_hides_misleading_schedule_controls_and_auto_mode() -> None:
    ui = read(WORKSPACE)
    assert "{% if selected.name != 'audit_event' %}" in ui
    assert 'name="schedule_hour"' in ui
    assert 'name="schedule_minute"' in ui
    assert "{{ 'Execution Mode' if selected.name == 'audit_event' else 'Automatic Run' }}" in ui
    assert 'Manual Archive Only. Enable and save the policy before starting a job.' in ui
    assert 'Archive failures retry once, then require manual retry.' in ui
    assert "selected.name not in ('notification_delivery', 'audit_event')" in ui
    assert "selected.name in ('notification_delivery', 'audit_event')" in ui
    assert "selected.name == 'audit_event' else 'Manual archive-only" in ui


def test_compact_status_is_single_state_dependent_element_not_trial_banner() -> None:
    ui = read(WORKSPACE)
    audit = ui.split("{% if selected.name == 'audit_event' %}\n            <div class=\"flex flex-wrap", 1)[1]
    audit = audit.split('{% elif not selected.enabled %}', 1)[0]
    assert 'role="status"' in audit
    assert '{% if lifecycle.active_lifecycle_jobs %}' in audit
    assert '{% elif selected.enabled %}' in audit
    assert 'Archive in progress' in audit
    assert 'Manual Archive Only enabled' in audit
    assert 'Policy paused' in audit
    assert 'Preview is available. Enable and save the policy' in audit
    assert 'Original audit events remain in PostgreSQL.' in audit
    assert 'Another run is unavailable until completion.' in audit
    assert 'data-lifecycle-audit-event-safety' in audit
    assert 'approved synthetic evidence' not in ui
    assert 'Disable the policy after UAT' not in ui
    assert 'disposable UAT evidence' not in ui
    assert 'Archive Only: administrative AuditEvent evidence stays' not in ui


def test_operator_buttons_keep_csrf_rbac_htmx_toast_and_no_cleanup_button() -> None:
    ui = read(WORKSPACE)
    assert 'name="enabled"' in ui
    assert 'hx-target="#data-lifecycle-page"' in ui
    assert "url_for('platform_operations.data_lifecycle.preview'" in ui
    assert 'name="mode" value="archive_only"' in ui
    assert "{% if selected.name not in ('notification_delivery', 'audit_event') %}" in ui
    assert "{% if execution_blocked %}disabled{% endif %}" in ui
    assert 'hx-disabled-elt="find button[type=\'submit\']"' in ui
    assert ui.count('name="csrf_token" value="{{ csrf_token() }}"') == 3
    assert "current_user.has_permission('platform_operations.manage_data_lifecycle')" in ui
    service = read('app/platform_operations/data_lifecycle/service.py')
    assert "if domain_name == 'audit_event':" in read(
        'app/platform_operations/data_lifecycle/retention/service.py',
    )
    assert "_check_audit_event_governance(domain_name, user_id)" in service
    assert "domain_name not in {'notification_delivery', 'audit_event'}" in service
    assert 'OperationalDeliveryPolicy.DECK_ON_FAILURE' in service
    assert "'feedback_delivery': 'toast'" in service


def test_archive_only_source_retains_hot_data_and_sensitive_operations_blocked() -> None:
    adapter = read('app/platform_operations/data_lifecycle/retention/domains/audit_event.py')
    engine = read('app/platform_operations/data_lifecycle/retention/service.py')
    ui = read(WORKSPACE)
    assert 'cleanup_supported = False' in adapter
    assert 'enabled=False' in adapter
    assert 'AuditEvent.created_at < cutoff_at' in adapter
    assert '_require_audit_event_manual_admission(' in engine
    assert "if domain_name == 'audit_event' and not dry_run:" in engine
    assert "if artifact.domain == 'audit_event':" in engine
    assert 'Source-level retention and access controls remain restricted.' in read(
        'app/platform_operations/data_lifecycle/retention/presentation.py',
    )
    assert 'Scheduling and hot cleanup are disabled for this source.' in ui
    assert 'individual-record lookup and object purge remain unavailable' in ui
