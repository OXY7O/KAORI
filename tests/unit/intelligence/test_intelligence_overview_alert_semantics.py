from __future__ import annotations

from types import SimpleNamespace

from app.common.alert_case_source_state import is_active_alert_case
from app.intelligence.overview import _overview_posture


def _case(source_state: str, workflow_state: str, source_type: str = 'recommendation'):
    return SimpleNamespace(source_type=source_type, source_state=source_state, workflow_state=workflow_state)


def test_source_resolved_open_case_is_not_active() -> None:
    assert not is_active_alert_case(_case('resolved', 'open'))
    assert is_active_alert_case(_case('firing', 'open'))
    assert is_active_alert_case(_case('unknown', 'acknowledged'))
    assert not is_active_alert_case(_case('firing', 'closed'))
    assert not is_active_alert_case(_case('firing', 'open', 'provider_alert'))


def _posture(
    *,
    critical=0,
    warning=0,
    source_unknown=0,
    postmortem_required=0,
    active=0,
    delivery_failures=0,
    verification_pending=0,
):
    return _overview_posture(
        summary={
            'findings': 0,
            'critical': 0,
            'warning': 0,
            'registered_assets': 1,
        },
        alerts={
            'active': active,
            'critical': critical,
            'warning': warning,
            'source_unknown': source_unknown,
            'postmortem_required': postmortem_required,
            'delivery_failures': delivery_failures,
            'verification_pending': verification_pending,
        },
        automation={'failures': 0, 'pending_governance': 0},
    )


def test_critical_firing_takes_precedence() -> None:
    assert _posture(critical=1)['label'] == 'Critical Review'


def test_warning_unknown_and_postmortem_are_not_clear() -> None:
    assert _posture(warning=1)['label'] == 'Review Required'
    assert _posture(source_unknown=1)['label'] == 'Review Required'
    assert _posture(postmortem_required=1)['label'] == 'Review Required'


def test_recent_failed_delivery_is_control_attention() -> None:
    assert _posture(delivery_failures=1)['label'] == 'Control Attention'
