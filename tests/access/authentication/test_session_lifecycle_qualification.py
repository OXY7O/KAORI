"""Session lifecycle audit presentation regression (#5284)."""

import pytest

from app.platform_operations.notifications.event_catalog import build_event_context


@pytest.mark.parametrize(
    'action',
    ('session_expired', 'session_policy_changed', 'session_policy_unchanged'),
)
def test_lifecycle_events_are_security_control_evidence(action: str) -> None:
    context = build_event_context('authentication', {'access_action': action}, action)
    assert context['module_label'] == 'Access'
    assert context['target_type'] == 'Security Control'
    assert context['target_name'] == 'Session Security'
    assert context['source_label'] == 'Authentication security'
    assert context['event_icon'] == 'shield-check'
