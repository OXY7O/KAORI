"""Minimal SC-02 form checks; no real provider/network or browser SSO."""

from __future__ import annotations

from flask import Flask

from app.integrations.source_control.source_control.providers.github.application.forms import (
    GitHubAppConnectionForm,
)


def test_app_form_clears_private_key_and_webhook_secret_after_post() -> None:
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'unit-test-only'
    app.config['WTF_CSRF_ENABLED'] = False
    with app.test_request_context('/'):
        form = GitHubAppConnectionForm()
        form.private_key_pem.data = '-----BEGIN PRIVATE KEY----- test-not-real'
        form.webhook_secret.data = 'example-webhook-secret'
        form.clear_sensitive_fields()
        assert not form.private_key_pem.data
        assert not form.webhook_secret.data


def test_to_input_does_not_replace_existing_kaori_environment_taxonomy() -> None:
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'unit-test-only'
    app.config['WTF_CSRF_ENABLED'] = False
    with app.test_request_context('/'):
        form = GitHubAppConnectionForm()
        assert ('production', 'Production') in form.environment.choices
        form.name.data = 'Production'
        form.environment.data = 'production'
        form.app_id.data = '123'
        form.installation_id.data = '456'
        form.account_id.data = '789'
        form.private_key_pem.data = '-----BEGIN PRIVATE KEY----- test'
        form.webhook_secret.data = 'long-enough-webhook-secret'
        values = form.to_input()
        assert values.environment == 'production'
        assert values.app_id == '123'
        assert values.installation_id == '456'
        assert values.account_id == '789'
        assert 'long-enough-webhook-secret' not in repr(values)
