"""Data Lifecycle action and feedback contracts for operator UAT (#2929).

Source checks complement (but cannot replace) PostgreSQL, worker, browser
and Notification Deck acceptance in the approved disposable DevContainer.
"""

import ast
from pathlib import Path

from jinja2 import Environment

from app.platform_operations.notifications.feedback import OperationalDeliveryPolicy
from app.platform_operations.notifications.service import _feedback_delivery

ROOT = Path(__file__).resolve().parents[3]
WORKSPACE = 'app/templates/platform_operations/data_lifecycle/partials/_domain_workspace.html'
SERVICE = 'app/platform_operations/data_lifecycle/service.py'
ROUTES = 'app/platform_operations/data_lifecycle/routes.py'


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_alert_policy_title_uses_existing_accessible_guide_only_for_incidents() -> None:
    template = read(WORKSPACE)
    Environment().parse(template)
    assert '{% import "components/info_tip.html" as info_tip %}' in template
    assert "{% if selected.name == 'alert_incident' %}" in template
    assert "info_tip.render('data-lifecycle-alert-incident-policy-guide'," in template
    assert "variant='guide'" in template
    assert "placement='right'" in template
    assert 'Only Closed cases can enter the archive boundary' in template
    assert 'the searchable case index stays in PostgreSQL' in template

    source = read('app/platform_operations/data_lifecycle/retention/presentation.py')
    assert 'Case lifecycle evidence from initial detection through final closure.' in source
    assert 'Cleanup blocked; transient failures retry once, then need manual retry.' in template


def test_four_operator_actions_keep_safety_authenticity_and_progressive_enhancement() -> None:
    template = read(WORKSPACE)
    assert "url_for('platform_operations.data_lifecycle.save_policy')" in template
    assert "url_for('platform_operations.data_lifecycle.preview'" in template
    assert template.count("url_for('platform_operations.data_lifecycle.run')") == 4
    assert 'name="mode" value="archive_only"' in template
    assert 'name="mode" value="archive_and_cleanup"' in template
    assert template.count('type="submit"') == 3
    assert template.count('hx-disabled-elt="find button[type=\'submit\']"') == 3
    assert template.count('name="csrf_token" value="{{ csrf_token() }}"') == 3
    assert 'hx-target="#data-lifecycle-page"' in template
    assert template.count('hx-target="#data-lifecycle-domain-workspace"') >= 3
    assert '{% if can_manage %}' in template
    assert "{% if selected.name not in ('notification_delivery', 'audit_event') %}" in template
    assert '{% if execution_blocked %}disabled{% endif %}' in template


def test_preview_and_manual_execution_return_full_page_without_htmx() -> None:
    routes = read(ROUTES)
    preview = routes.split('def preview()', 1)[1].split('def save_policy()', 1)[0]
    run = routes.split('def run()', 1)[1].split('def verify(', 1)[0]

    for handler in (preview, run):
        assert "if request.headers.get('HX-Request') == 'true':" in handler
        assert "'platform_operations/data_lifecycle/partials/_domain_workspace.html'" in handler
        assert "return render_template('platform_operations/data_lifecycle/index.html', lifecycle=context)" in handler

    assert "@permission_required('platform_operations.view_data_lifecycle')" in routes
    assert "@permission_required('platform_operations.manage_data_lifecycle')" in routes
    assert 'domain_name=_mutation_domain()' in run
    assert "mode=str(request.form.get('mode') or 'archive_only')" in run
    assert '_context(preview=True)' in preview


def test_foreground_toast_and_deck_visibility_use_canonical_existing_policy() -> None:
    metadata = {'job_execution_id': 45, 'feedback_delivery': 'toast'}
    assert (
        _feedback_delivery(
            event_type='data_lifecycle_execution_requested',
            status='info',
            metadata=metadata,
        )
        == 'toast'
    )
    assert (
        _feedback_delivery(
            event_type='data_lifecycle_execution_requested',
            status='info',
            metadata={'job_execution_id': 45},
        )
        == 'activity_center'
    )
    assert OperationalDeliveryPolicy.DECK_ON_FAILURE.deck_visible('success') is False
    assert OperationalDeliveryPolicy.DECK_ON_FAILURE.deck_visible('info') is False
    assert OperationalDeliveryPolicy.DECK_ON_FAILURE.deck_visible('warning') is True
    assert OperationalDeliveryPolicy.DECK_ON_FAILURE.deck_visible('error') is True

    service = read(SERVICE)
    tree = ast.parse(service)
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == 'record_operational_activity'
    ]
    assert len(calls) == 9
    for call in calls:
        policy = next(keyword.value for keyword in call.keywords if keyword.arg == 'delivery_policy')
        assert isinstance(policy, ast.Attribute)
        assert policy.attr == 'DECK_ON_FAILURE'

    assert service.count("'feedback_delivery': 'toast'") == 3
    assert "job_type='data_lifecycle'" in service
    assert "queue_name=str(current_app.config.get('RETENTION_CELERY_QUEUE'" in service


def test_shared_oob_toast_and_activity_evidence_are_not_replaced_with_custom_ui() -> None:
    template = read(WORKSPACE)
    oob = read('app/templates/components/operation_feedback_oob.html')
    toast = read('app/templates/components/operational_toast.html')
    assert 'components/operation_feedback_oob.html' in template
    assert 'components/operational_toast.html' in oob
    assert "delivery=operation_feedback.delivery|default('toast')" in oob
    assert 'hx-swap-oob="beforeend:#operational-toast-stack"' in toast
    assert 'notification_deck_visible' in oob
    assert 'data-operational-notification-refresh' in toast
