"""Opt-in signed webhook route must fail closed and never dispatch inline."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from flask import Flask

from app.extensions.limiter import limiter
from app.integrations.source_control.source_control.providers.github.application import routes
from app.integrations.source_control.source_control.providers.github import webhook_inbox
from app.integrations.source_control.source_control.providers.github.webhook import GitHubWebhookError


@pytest.fixture
def client(monkeypatch):
    app = Flask(__name__)
    app.config.update(TESTING=True, SOURCE_CONTROL_WEBHOOK_INGRESS_ENABLED=False)
    limiter.init_app(app)
    app.register_blueprint(routes.github_source_bp)
    return app.test_client(), app


def test_default_ingress_returns_404_before_parsing_payload(client, monkeypatch):
    http, app = client
    monkeypatch.setattr(
        routes,
        '_available',
        lambda: pytest.fail('disabled ingress must not inspect provider'),
    )
    response = http.post(
        '/integrations/source-control/github/webhook',
        data='private-secret',
        content_type='application/json',
    )
    assert response.status_code == 404
    assert b'private-secret' not in response.data


def test_provider_planned_blocks_even_explicitly_enabled_flag(client, monkeypatch):
    http, app = client
    app.config['SOURCE_CONTROL_WEBHOOK_INGRESS_ENABLED'] = True
    monkeypatch.setattr(routes, '_available', lambda: False)
    response = http.post(
        '/integrations/source-control/github/webhook',
        data='{}',
        content_type='application/json',
    )
    assert response.status_code == 404


def test_oversized_ingress_denied_before_decryption(client, monkeypatch):
    http, app = client
    app.config['SOURCE_CONTROL_WEBHOOK_INGRESS_ENABLED'] = True
    monkeypatch.setattr(routes, '_available', lambda: True)
    response = http.post(
        '/integrations/source-control/github/webhook',
        data=b'A' * 262_145,
        content_type='application/json',
    )
    assert response.status_code == 413


def test_untrusted_missing_installation_rejected(client, monkeypatch):
    http, app = client
    app.config['SOURCE_CONTROL_WEBHOOK_INGRESS_ENABLED'] = True
    monkeypatch.setattr(routes, '_available', lambda: True)
    response = http.post(
        '/integrations/source-control/github/webhook',
        data='{"installation":{"id":true}}',
        content_type='application/json',
    )
    assert response.status_code == 400


def test_authenticated_claim_only_commits_metadata_and_returns_202(client, monkeypatch):
    http, app = client
    app.config['SOURCE_CONTROL_WEBHOOK_INGRESS_ENABLED'] = True
    monkeypatch.setattr(routes, '_available', lambda: True)
    events = []

    class Query:
        def filter_by(self, **criteria):
            assert criteria['native_installation_id'] == '17'
            return self

        def limit(self, limit):
            assert limit == 2
            return self

        def all(self):
            return [SimpleNamespace(id=1)]

    monkeypatch.setattr(webhook_inbox, 'SourceInstallation', SimpleNamespace(query=Query()))
    fake_db = SimpleNamespace(
        session=SimpleNamespace(
            commit=lambda: events.append('commit'),
            rollback=lambda: events.append('rollback'),
        )
    )
    monkeypatch.setattr(webhook_inbox, 'db', fake_db)
    monkeypatch.setattr(
        webhook_inbox,
        'claim_verified_delivery',
        lambda **kwargs: events.append(('verified', kwargs['payload'])) or None,
    )
    body = json.dumps({'installation': {'id': 17}}).encode()
    response = http.post(
        '/integrations/source-control/github/webhook',
        data=body,
        content_type='application/json',
    )
    assert response.status_code == 202
    assert events == [('verified', body), 'commit']
    assert response.headers['Cache-Control'].startswith('no-store')


def test_hmac_error_does_not_leak_verification_exception(client, monkeypatch):
    http, app = client
    app.config['SOURCE_CONTROL_WEBHOOK_INGRESS_ENABLED'] = True
    monkeypatch.setattr(routes, '_available', lambda: True)

    class Query:
        def filter_by(self, **_):
            return self

        def limit(self, _):
            return self

        def all(self):
            return [SimpleNamespace(id=1)]

    monkeypatch.setattr(webhook_inbox, 'SourceInstallation', SimpleNamespace(query=Query()))
    monkeypatch.setattr(
        webhook_inbox,
        'db',
        SimpleNamespace(
            session=SimpleNamespace(commit=lambda: None, rollback=lambda: None),
        ),
    )
    monkeypatch.setattr(
        webhook_inbox,
        'claim_verified_delivery',
        lambda **_: (_ for _ in ()).throw(GitHubWebhookError('private-key-test')),
    )
    response = http.post(
        '/integrations/source-control/github/webhook',
        data='{"installation":{"id":17}}',
        content_type='application/json',
    )
    assert response.status_code == 401
    assert b'private-key-test' not in response.data


def test_route_never_dispatches_provider_job_inline():
    path = (
        Path(__file__).resolve().parents[2]
        / 'app/integrations/source_control/source_control/providers/github/application/routes.py'
    )
    source = path.read_text()
    inbox_path = (
        Path(__file__).resolve().parents[2]
        / 'app/integrations/source_control/source_control/providers/github/webhook_inbox.py'
    )
    inbox = inbox_path.read_text()
    webhook_section = source.split('def receive_signed_webhook()')[1]
    assert "current_app.config.get('SOURCE_CONTROL_WEBHOOK_INGRESS_ENABLED', False)" in webhook_section
    assert 'stage_signed_github_webhook_delivery(' in webhook_section
    assert 'claim_verified_delivery(' in inbox
    assert 'db.session.commit()' in inbox
    assert 'db.session.rollback()' in inbox
    assert 'enqueue_source_repository_sync(' not in webhook_section
    assert 'enqueue_source_repository_sync(' not in inbox
    assert 'apply_async(' not in webhook_section
    assert 'apply_async(' not in inbox
