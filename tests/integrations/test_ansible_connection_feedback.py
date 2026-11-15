"""Issue #4878: Ansible source registration feedback uses KAORI's canonical toast/Audit policy.

The route is exercised with an in-memory form/provider stub. No database,
network call, real Git source read or Ansible execution is performed here.
"""

from __future__ import annotations

from inspect import unwrap
from types import SimpleNamespace
from typing import Any

import pytest
from flask import Flask
from sqlalchemy.exc import SQLAlchemyError

from app.integrations import routes
from app.platform_operations.notifications.event_catalog import event_category_key
from app.platform_operations.notifications.feedback import OperationalDeliveryPolicy
from app.platform_operations.notifications.service import _feedback_delivery


@pytest.mark.parametrize(
    ('outcome', 'action', 'expected_status', 'expected_event'),
    [
        ('test_success', 'test', 'success', 'ansible_source_validation_checked'),
        ('test_failure', 'test', 'error', 'ansible_source_validation_failed'),
        ('policy_rejected', 'test', 'warning', 'ansible_source_registration_policy_rejected'),
        ('invalid_fields', 'test', 'warning', 'ansible_source_registration_input_rejected'),
        ('expired_form', 'test', 'warning', 'ansible_source_registration_input_rejected'),
        ('save_missing_proof', 'save', 'warning', 'ansible_source_registration_proof_rejected'),
        ('save_duplicate', 'save', 'warning', 'ansible_source_registration_rejected'),
        ('save_failure', 'save', 'error', 'ansible_source_registration_failed'),
        ('save_success', 'save', 'success', 'ansible_source_connection_registered'),
        ('unsupported_action', 'unknown', 'warning', 'ansible_source_registration_action_rejected'),
    ],
)
def test_registration_action_produces_one_canonical_receipt_without_source_leak(
    monkeypatch: pytest.MonkeyPatch,
    outcome: str,
    action: str,
    expected_status: str,
    expected_event: str,
) -> None:
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'ansible-feedback-test-only'
    app.register_blueprint(routes.integrations_bp)
    captured: list[dict[str, Any]] = []
    values = SimpleNamespace(repository='OXY7O/kaori-operations', revision='a' * 40)
    diagnostic = 'private-provider-or-storage-diagnostic-must-not-leak'

    class FakeForm:
        errors = (
            {'csrf_token': [diagnostic]}
            if outcome == 'expired_form'
            else {'repository': [diagnostic]}
            if outcome == 'invalid_fields'
            else {}
        )
        source_test_proof = SimpleNamespace(data='previous-proof')

        def validate_on_submit(self) -> bool:
            return outcome not in {'invalid_fields', 'expired_form'}

        def to_input(self) -> SimpleNamespace:
            if outcome == 'policy_rejected':
                raise ValueError(diagnostic)
            return values

    def fake_verify(repository: str, revision: str) -> object:
        if outcome == 'test_failure':
            raise ValueError(diagnostic)
        assert repository == values.repository
        assert revision == values.revision
        return object()

    def fake_save(*args: Any, **kwargs: Any) -> SimpleNamespace:
        if outcome == 'save_duplicate':
            raise ValueError('An automation connection with this name already exists.')
        if outcome == 'save_failure':
            raise SQLAlchemyError(diagnostic)
        return SimpleNamespace(id=17)

    monkeypatch.setattr(routes, 'current_user', SimpleNamespace(id=42))
    monkeypatch.setattr(routes, 'AnsibleSourceConnectionForm', FakeForm)
    monkeypatch.setattr(routes, 'verify_public_kubespray_source', fake_verify)
    monkeypatch.setattr(routes, 'issue_source_proof', lambda *args: 'signed-source-proof')
    monkeypatch.setattr(
        routes,
        'verified_source_proof',
        lambda *args: None if outcome == 'save_missing_proof' else {'status': 'source_checked'},
    )
    monkeypatch.setattr(routes, 'save_source_connection', fake_save)
    monkeypatch.setattr(routes, 'record_operational_activity', lambda **kwargs: captured.append(kwargs))
    monkeypatch.setattr(routes, 'get_navigation_notification_context', lambda **kwargs: {})
    monkeypatch.setattr(routes, 'render_template', lambda template, **context: context)

    with app.test_request_context(
        '/integrations/ansible/connections/new',
        method='POST',
        data={'action': action, 'source_test_proof': 'previous-proof'},
    ):
        # Flask permission middleware is independently covered by the web tests.
        response = unwrap(routes.ansible_new_connection)()

    assert len(captured) == 1
    event = captured[0]
    assert event['event_type'] == expected_event
    assert event_category_key(event['event_type']) == 'integrations'
    assert event['status'] == expected_status
    assert event['queue_feedback'] is True
    assert event['metadata']['provider'] == 'ansible'
    assert event['metadata'].get('feedback_delivery', 'toast') == 'toast'
    assert _feedback_delivery(
        event_type=event['event_type'], status=event['status'], metadata=event['metadata']
    ) == 'toast'
    assert diagnostic not in repr(event)
    assert 'previous-proof' not in repr(event)

    if outcome == 'save_success':
        assert response.status_code == 302
        assert event['action_url'].endswith('/integrations/ansible/connections/17')
        # The existing successful registration remains one persisted event,
        # rather than an extra transient toast or duplicate registration event.
        assert 'delivery_policy' not in event
    else:
        assert isinstance(response, dict)
        assert response['source_test_proof'] == ('signed-source-proof' if outcome == 'test_success' else '')
        assert 'feedback' not in response
        assert event['delivery_policy'] == OperationalDeliveryPolicy.AUDIT_ONLY
        assert event['action_url'].endswith('/integrations/ansible/connections/new')
        if outcome == 'invalid_fields':
            assert 'Git Repository' in event['message']
        if outcome == 'expired_form':
            assert 'Form session expired' in event['message']
        if outcome == 'save_duplicate':
            assert 'already exists' in event['message']


def test_form_feedback_has_no_runtime_notification_on_initial_get(monkeypatch: pytest.MonkeyPatch) -> None:
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'ansible-feedback-test-only'
    app.register_blueprint(routes.integrations_bp)
    feedback: list[dict[str, Any]] = []
    monkeypatch.setattr(routes, 'current_user', SimpleNamespace(id=42))
    monkeypatch.setattr(
        routes,
        'AnsibleSourceConnectionForm',
        lambda: SimpleNamespace(errors={}, source_test_proof=SimpleNamespace(data='')),
    )
    monkeypatch.setattr(routes, 'record_operational_activity', lambda **kwargs: feedback.append(kwargs))
    monkeypatch.setattr(routes, 'get_navigation_notification_context', lambda **kwargs: {})
    monkeypatch.setattr(routes, 'render_template', lambda template, **context: context)

    with app.test_request_context('/integrations/ansible/connections/new', method='GET'):
        response = unwrap(routes.ansible_new_connection)()

    assert feedback == []
    assert response['source_test_proof'] == ''
    assert 'feedback' not in response
