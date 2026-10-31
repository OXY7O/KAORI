"""GitHub App registration proof is short-lived, scoped and never carries secrets."""

from __future__ import annotations

from dataclasses import replace

from flask import Flask
from itsdangerous import SignatureExpired

from app.integrations.source_control.source_control.providers.github.application import (
    registration_proof,
)
from app.integrations.source_control.source_control.providers.github.registration import (
    GitHubConnectionInput,
)


def _values() -> GitHubConnectionInput:
    return GitHubConnectionInput(
        name='UAT GitHub',
        environment='development',
        description='Read-only test connection',
        app_id='123456',
        installation_id='654321',
        account_id='789012',
        private_key_pem='-----BEGIN RSA PRIVATE KEY-----\\nnot-a-real-key\\n-----END RSA PRIVATE KEY-----',
        webhook_secret='not-a-real-secret-of-any-kind',
        enabled=True,
    )


def test_proof_round_trip_never_exposes_secrets() -> None:
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'test-only-application-secret'
    with app.app_context():
        values = _values()
        proof = registration_proof.issue_github_registration_proof(user_id=7, values=values)
        assert values.private_key_pem not in proof
        assert values.webhook_secret not in proof
        assert str(values.installation_id) not in proof
        assert registration_proof.verify_github_registration_proof(token=proof, user_id=7, values=values) == (True, '')


def test_proof_requires_matching_user_and_all_submitted_fields() -> None:
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'test-only-application-secret'
    with app.app_context():
        values = _values()
        proof = registration_proof.issue_github_registration_proof(user_id=7, values=values)
        valid, error = registration_proof.verify_github_registration_proof(token=proof, user_id=8, values=values)
        assert not valid and 'another user' in error

        changes = {
            'name': 'Other GitHub',
            'environment': 'production',
            'description': 'New description',
            'app_id': '98765',
            'installation_id': '987654',
            'account_id': '11111',
            'private_key_pem': '-----BEGIN RSA PRIVATE KEY-----\\nrotated\\n-----END RSA PRIVATE KEY-----',
            'webhook_secret': 'another-different-secret',
            'enabled': False,
        }
        for field, value in changes.items():
            changed = replace(values, **{field: value})
            valid, error = registration_proof.verify_github_registration_proof(token=proof, user_id=7, values=changed)
            assert not valid and 'settings changed' in error, field


def test_proof_rejects_missing_tampered_and_expired_tokens(monkeypatch) -> None:
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'test-only-application-secret'
    with app.app_context():
        values = _values()
        proof = registration_proof.issue_github_registration_proof(user_id=7, values=values)
        valid, error = registration_proof.verify_github_registration_proof(token='', user_id=7, values=values)
        assert not valid and 'Run Test Connection' in error
        valid, error = registration_proof.verify_github_registration_proof(
            token=proof + '.tampered', user_id=7, values=values
        )
        assert not valid and 'invalid' in error

        class ExpiredSerializer:
            def loads(self, _token: str, *, max_age: int):
                assert max_age == 600
                raise SignatureExpired('expired')

        monkeypatch.setattr(registration_proof, '_serializer', lambda: ExpiredSerializer())
        valid, error = registration_proof.verify_github_registration_proof(token=proof, user_id=7, values=values)
        assert not valid and 'expired' in error


def test_multiline_line_endings_do_not_invalidate_identical_configuration() -> None:
    """HTMX and native form serialization may use different line endings."""
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'test-only-application-secret'
    with app.app_context():
        values = replace(
            _values(),
            description='Line one\nLine two',
            private_key_pem='-----BEGIN PRIVATE KEY-----\nexample\n-----END PRIVATE KEY-----\n',
        )
        token = registration_proof.issue_github_registration_proof(user_id=7, values=values)
        normalized = replace(
            values,
            description='Line one\r\nLine two',
            private_key_pem='-----BEGIN PRIVATE KEY-----\r\nexample\r\n-----END PRIVATE KEY-----\r\n',
        )
        assert registration_proof.verify_github_registration_proof(token=token, user_id=7, values=normalized) == (
            True,
            '',
        )
        assert (
            registration_proof.verify_github_registration_proof(
                token=token,
                user_id=7,
                values=replace(normalized, private_key_pem=normalized.private_key_pem + 'changed'),
            )[0]
            is False
        )
