"""Live route-level contract for Vault Test/Register/Edit operational feedback.

The external Vault API, provider persistence and Activity Audit writer are
replaced by in-memory fakes; no credentials or Vault calls leave this test.
"""

from __future__ import annotations

from inspect import unwrap
from types import SimpleNamespace
from typing import Any

import pytest
from flask import Flask

from app.integrations.secrets_management.secrets_pki.providers.vault.application import routes
from app.integrations.secrets_management.secrets_pki.providers.vault.application.types import VaultConnectionInput


@pytest.mark.parametrize('mode', ['register', 'edit'])
@pytest.mark.parametrize(
    ('outcome', 'action', 'expected_status', 'event_suffix'),
    [
        ('test_success', 'test', 'success', 'test'),
        ('test_failure', 'test', 'error', 'test_failed'),
        ('save_missing_proof', 'save', 'warning', 'proof_rejected'),
        ('save_failed', 'save', 'error', 'failed'),
        ('save_success', 'save', 'success', 'saved'),
        ('invalid_fields', 'test', 'warning', 'input_rejected'),
        ('unsupported_action', 'unexpected', 'warning', 'action_rejected'),
    ],
)
def test_vault_form_actions_use_canonical_feedback_without_secrets(
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
    outcome: str,
    action: str,
    expected_status: str,
    event_suffix: str,
) -> None:
    app = Flask(__name__)
    app.config.update(SECRET_KEY='vault-feedback-test-only')
    app.register_blueprint(routes.vault_bp)
    feedback_events: list[dict[str, Any]] = []
    values = VaultConnectionInput(
        name='Vault Test',
        environment='development',
        description=None,
        endpoint='https://vault.example.internal:8200',
        namespace=None,
        auth_mount='approle',
        role_id='test-only-role',
        secret_id='not-for-ui-or-audit',
        timeout=5,
        enabled=True,
    )

    class FakeForm:
        errors = {'secret_id': ['AppRole SecretID is required.']} if outcome == 'invalid_fields' else {}

        def validate_on_submit(self) -> bool:
            return outcome != 'invalid_fields'

        def to_input(self) -> VaultConnectionInput:
            return values

    fake_instance = SimpleNamespace(id=17, secret_id='not-for-ui-or-audit')
    monkeypatch.setattr(routes, 'current_user', SimpleNamespace(id=42))
    monkeypatch.setattr(routes, 'VaultConnectionForm', lambda **kwargs: FakeForm())
    monkeypatch.setattr(routes, 'get_vault_connection_instance', lambda instance_id: fake_instance)
    monkeypatch.setattr(routes, 'get_navigation_notification_context', lambda **kwargs: {})
    monkeypatch.setattr(routes, 'render_template', lambda template, **context: context)
    monkeypatch.setattr(routes, 'record_operational_activity', lambda **kwargs: feedback_events.append(kwargs))
    monkeypatch.setattr(routes, 'issue_proof', lambda values, user_id: 'signed-proof')
    monkeypatch.setattr(
        routes,
        'verified_secret',
        lambda proof, values, user_id: None if outcome == 'save_missing_proof' else values.secret_id,
    )

    def fake_test_connection(_: VaultConnectionInput) -> None:
        if outcome == 'test_failure':
            raise ValueError('raw-provider-error-must-not-be-exposed')

    def fake_save_connection(*args: Any, **kwargs: Any) -> SimpleNamespace:
        if outcome == 'save_failed':
            raise ValueError('raw-storage-error-must-not-be-exposed')
        return fake_instance

    monkeypatch.setattr(routes, 'test_connection', fake_test_connection)
    monkeypatch.setattr(routes, 'save_connection', fake_save_connection)

    url = (
        '/integrations/secrets-management/secrets-pki/vault/instances/new'
        if mode == 'register'
        else '/integrations/secrets-management/secrets-pki/vault/instances/17/edit'
    )
    with app.test_request_context(
        url,
        method='POST',
        data={'action': action, 'connection_test_proof': 'previous-proof'},
    ):
        # Exercise route logic, not Flask-Login/RBAC middleware; permissions
        # are independently covered by the existing integration contract.
        handler = unwrap(routes.new_instance if mode == 'register' else routes.edit_instance)
        result = handler() if mode == 'register' else handler(17)

    assert len(feedback_events) == 1
    feedback = feedback_events[0]
    assert feedback['status'] == expected_status
    assert feedback['queue_feedback'] is True
    assert feedback['event_type'].startswith('vault_')
    if outcome == 'save_success':
        assert feedback['event_type'] in {'vault_connection_registered', 'vault_connection_updated'}
    else:
        assert feedback['event_type'].endswith(event_suffix)
    assert 'not-for-ui-or-audit' not in repr(feedback)
    assert 'raw-provider-error-must-not-be-exposed' not in repr(feedback)
    assert 'raw-storage-error-must-not-be-exposed' not in repr(feedback)
    if outcome == 'invalid_fields':
        assert 'AppRole SecretID' in feedback['message']
        assert 'not-for-ui-or-audit' not in feedback['message']
    if outcome == 'save_success':
        assert result.status_code == 302
        assert feedback['event_type'] in {'vault_connection_registered', 'vault_connection_updated'}
    else:
        assert isinstance(result, dict)
        assert result['proof'] == ('signed-proof' if outcome == 'test_success' else '')
        assert 'message' not in result
        assert feedback['delivery_policy'] == 'audit_only'
        assert feedback['action_url'].endswith(url)


@pytest.mark.parametrize(
    ('errors', 'action', 'expected_message'),
    [
        (
            {'secret_id': ['Private value must not be exposed']},
            'test',
            'AppRole SecretID is required to test a new Vault connection.',
        ),
        (
            {'role_id': ['Unsafe raw role value']},
            'test',
            'Correct AppRole RoleID before continuing.',
        ),
        (
            {'name': ['Unsafe name'], 'secret_id': ['Unsafe secret']},
            'save',
            'Correct Connection Name, AppRole SecretID before continuing.',
        ),
        (
            {'csrf_token': ['CSRF value must not be exposed']},
            'test',
            'Form session expired. Reload the page and retry Test Connection.',
        ),
        (
            {'unexpected': ['Raw untrusted validator error']},
            'test',
            'Review the form validation errors before continuing.',
        ),
    ],
)
def test_vault_rejected_form_toast_names_only_safe_fields(
    errors: dict[str, list[str]],
    action: str,
    expected_message: str,
) -> None:
    form = SimpleNamespace(errors=errors)
    message = routes._form_validation_message(form, action=action)
    assert message == expected_message
    assert not any(error in message for messages in errors.values() for error in messages)
