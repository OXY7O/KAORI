from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_alert_escalation_explains_each_promotion_control() -> None:
    detail = read('app/templates/intelligence/partials/_catalog_detail_content.html')

    assert 'How Alert Escalation Works' in detail
    for label in (
        'Escalation Mode',
        'Grouping',
        'Stability Window',
        'Minimum Observations',
    ):
        assert f'>{label}<' in detail
    assert 'Manual waits for an authorized operator' in detail
    assert 'one aggregated Rule + Asset case' in detail
    assert 'Minimum continuous time an automatic finding must remain eligible' in detail
    assert 'Minimum committed evaluation count required for automatic promotion' in detail
    assert 'Automatic mode additionally enforces the Stability Window and Minimum Observations.' in detail


def test_selected_findings_uses_clear_grouped_cards_and_explicit_risk_owner() -> None:
    detail = read('app/templates/intelligence/partials/_catalog_detail_content.html')

    assert 'data-kaori-selected-findings' in detail
    selected = detail[detail.index('data-kaori-selected-findings') :]
    assert 'bg-surface-card' in selected
    assert 'bg-surface-page' not in selected[: selected.index('Create Accepted Risk') if 'Create Accepted Risk' in selected else len(selected)]
    assert 'asset.uncovered_count' in selected
    assert 'asset.excepted_count' in selected
    assert 'Already covered' in selected
    assert 'Available for this accepted-risk scope' in selected
    assert 'name="owner_user_id"' in detail
    assert 'item.rule_exceptions.owner_options' in detail
    assert 'The selected Risk Owner is accountable for follow-up.' in detail


def test_work_inbox_is_one_shared_deck_not_a_second_drawer() -> None:
    shell = read('app/templates/components/navigation/_notification_center.html')
    queries = read('app/platform_operations/notifications/queries.py')
    constants = read('app/platform_operations/notifications/constants.py')

    assert shell.count('id="notification-deck"') == 1
    assert 'openNotificationDeck(\'inbox\')' in shell
    assert 'message-square-text' in shell
    assert 'Work Inbox' in shell
    assert 'notification-deck-inbox-content' in shell
    assert "Notification.event_type.in_(WORK_INBOX_EVENT_TYPES)" in queries
    assert "Notification.event_type.notin_(WORK_INBOX_EVENT_TYPES)" in queries
    for event_type in (
        'alert_case_assigned',
        'alert_case_acknowledgement_overdue',
        'alert_case_silence_expired',
        'alert_case_verification_required',
        'rule_exception_assigned',
        'rule_exception_expiring',
        'rule_exception_revoked',
    ):
        assert event_type in constants


def test_alert_case_and_accepted_risk_delegation_create_persistent_work_items() -> None:
    routes = read('app/intelligence/alert_intelligence/routes.py')
    exceptions = read('app/intelligence/rule_exceptions.py')
    task = read('app/platform_operations/notifications/alert_delivery/tasks.py')

    assert "event_type='alert_case_assigned'" in routes
    assert "event_type='rule_exception_assigned'" in routes
    assert "event_type='rule_exception_revoked'" in routes
    assert "delivery_policy='persistent'" in routes
    assert "'work_inbox': True" in routes
    assert "event_type='rule_exception_expiring'" in exceptions
    assert 'notify_expiring_rule_exceptions' in task


def test_intelligence_mutations_use_activity_audit_toast_and_deck_policy() -> None:
    alert_routes = read('app/intelligence/alert_intelligence/routes.py')
    automation_routes = read('app/intelligence/automation_control/routes.py')
    catalog = read('app/definitions/catalogs/platform_operations/notifications/event_categories.yaml')

    assert 'record_operational_activity(' in alert_routes
    assert "delivery_policy='audit_only'" in alert_routes
    assert "delivery_policy='deck_on_failure'" in alert_routes
    assert 'queue_feedback=True' in alert_routes
    assert 'record_operational_activity(' in automation_routes
    assert "delivery_policy='audit_only'" in automation_routes
    assert "delivery_policy='deck_on_failure'" in automation_routes
    assert 'queue_transient_feedback' not in automation_routes
    for prefix in (
        'alert_case_',
        'alert_routing_',
        'alert_notification_',
        'recommendation_alert_',
        'rule_exception_',
        'automation_control_',
    ):
        assert f'- {prefix}' in catalog
