"""Fail-closed signed GitHub inbox HTTP and SQL transaction boundaries."""

from __future__ import annotations

import inspect
from types import SimpleNamespace

import pytest
from flask import Flask
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import HTTPException

from app.integrations.source_control.source_control.providers.github.application import routes
from app.integrations.source_control.source_control.providers.github.webhook import GitHubWebhookError


class _InstallationQuery:
    def filter_by(self, **_kwargs: object) -> _InstallationQuery:
        return self

    def limit(self, _count: int) -> _InstallationQuery:
        return self

    def all(self) -> list[SimpleNamespace]:
        return [SimpleNamespace(id=7, native_installation_id='7')]


class _Session:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


def _invoke_signed_ingress(monkeypatch: pytest.MonkeyPatch, handler_error: Exception | None):
    session = _Session()
    monkeypatch.setattr(routes, 'SourceInstallation', SimpleNamespace(query=_InstallationQuery()))
    monkeypatch.setattr(routes, 'db', SimpleNamespace(session=session))
    monkeypatch.setattr(routes, '_available', lambda: True)

    def claim(**_kwargs: object) -> None:
        if handler_error is not None:
            raise handler_error

    monkeypatch.setattr(routes, 'claim_verified_delivery', claim)

    app = Flask(__name__)
    app.config['SOURCE_CONTROL_WEBHOOK_INGRESS_ENABLED'] = True
    payload = b'{"installation":{"id":7}}'
    with app.test_request_context(
        '/integrations/source-control/github/webhook',
        method='POST',
        data=payload,
        content_type='application/json',
    ):
        # Route-level request handling, independent of the actual rate-limiter
        # extension lifecycle; the production blueprint is not reconfigured.
        endpoint = inspect.unwrap(routes.receive_signed_webhook)
        if handler_error is None:
            response = endpoint()
            return response.status_code, session
        with pytest.raises(Exception) as raised:
            endpoint()
        return raised.value, session


def test_authenticated_delivery_returns_202_after_durable_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    status, session = _invoke_signed_ingress(monkeypatch, None)
    assert status == 202
    assert session.commits == 1
    assert session.rollbacks == 0


@pytest.mark.parametrize(
    ('error', 'http_status'),
    [
        (GitHubWebhookError('invalid signature'), 401),
        (SQLAlchemyError('backend offline'), 503),
        (RuntimeError('missing transactional context'), 503),
        (ValueError('malformed delivery state'), 503),
        (TypeError('malformed claim contract'), 503),
    ],
)
def test_rejected_or_unavailable_ingress_rolls_back(
    monkeypatch: pytest.MonkeyPatch, error: Exception, http_status: int
) -> None:
    raised, session = _invoke_signed_ingress(monkeypatch, error)
    assert isinstance(raised, HTTPException)
    assert raised.code == http_status
    assert session.commits == 0
    assert session.rollbacks == 1


def test_unexpected_claim_error_propagates_after_rollback(monkeypatch: pytest.MonkeyPatch) -> None:
    raised, session = _invoke_signed_ingress(monkeypatch, LookupError('unexpected ledger contract'))
    assert isinstance(raised, LookupError)
    assert session.commits == 0
    assert session.rollbacks == 1
