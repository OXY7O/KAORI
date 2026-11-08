from __future__ import annotations

from dataclasses import replace

from flask import Flask

from app.integrations.registry.providers.harbor.application import registration
from app.integrations.registry.providers.harbor.application.contracts import HarborRegistrationInput


def _values() -> HarborRegistrationInput:
    return HarborRegistrationInput(
        name='Harbor Production',
        environment='production',
        description='Primary read-only Registry provider',
        endpoint='https://harbor.example.test',
        auth_type='basic',
        username='robot$kaori',
        password='registration-secret',
        timeout=5,
        verify_ssl=True,
        enabled=True,
    )


def _app() -> Flask:
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'test-only-secret-key'
    return app


def test_registration_proof_accepts_same_user_and_effective_payload() -> None:
    values = _values()

    with _app().app_context():
        token = registration.issue_registration_proof(values=values, user_id=17)
        verified, message = registration.verify_registration_proof(
            token=token,
            values=values,
            user_id=17,
        )

    assert verified is True
    assert message == ''


def test_registration_proof_is_invalid_after_connection_settings_change() -> None:
    values = _values()

    with _app().app_context():
        token = registration.issue_registration_proof(values=values, user_id=17)
        verified, message = registration.verify_registration_proof(
            token=token,
            values=replace(values, endpoint='https://harbor-secondary.example.test'),
            user_id=17,
        )

    assert verified is False
    assert message == 'Connection settings changed after testing. Run Test Connection again.'


def test_registration_proof_is_bound_to_submitting_user() -> None:
    values = _values()

    with _app().app_context():
        token = registration.issue_registration_proof(values=values, user_id=17)
        verified, message = registration.verify_registration_proof(
            token=token,
            values=values,
            user_id=23,
        )

    assert verified is False
    assert message == 'The connection test belongs to another session. Run Test Connection again.'


def test_registration_proof_expires_before_registration(monkeypatch) -> None:
    values = _values()

    with _app().app_context():
        token = registration.issue_registration_proof(values=values, user_id=17)
        monkeypatch.setattr(registration, 'REGISTRATION_PROOF_MAX_AGE_SECONDS', -1)
        verified, message = registration.verify_registration_proof(
            token=token,
            values=values,
            user_id=17,
        )

    assert verified is False
    assert message == 'The successful connection test expired. Run Test Connection again.'
