"""Service boundaries for consolidated issuer authority; no live provider."""

from datetime import UTC, datetime, timedelta

import pytest
from flask import Flask

from app.access.scope_policy import CredentialIssuerScope
from app.extensions.db import db
from app.secrets_pki import issuer_lifecycle

_SCOPE = CredentialIssuerScope(1, 'openbao', '', 'kv', 'a' * 64)


@pytest.fixture
def sqlite_app():
    app = Flask(__name__)
    app.config.update(SQLALCHEMY_DATABASE_URI='sqlite://', SQLALCHEMY_TRACK_MODIFICATIONS=False)
    db.init_app(app)
    with app.app_context():
        yield
        db.session.remove()


def test_sqlite_issuer_mutation_is_denied(sqlite_app):
    with pytest.raises(issuer_lifecycle.IssuerLifecycleDenied):
        issuer_lifecycle.revoke_issuer_enrollment(actor_id=1, scope=_SCOPE, expected_revision=1)


def test_missing_access_never_calls_native_provider(sqlite_app, monkeypatch):
    def unexpected(*_args, **_kwargs):
        pytest.fail('Provider observation must not be reached without Access.')

    monkeypatch.setattr(issuer_lifecycle, 'observe_transit_issuer', unexpected)
    intent = issuer_lifecycle.IssuerEnrollmentIntent(_SCOPE, 0, datetime.now(UTC) + timedelta(minutes=10))
    with pytest.raises(issuer_lifecycle.IssuerLifecycleDenied):
        issuer_lifecycle.request_issuer_enrollment(actor_id=1, intent=intent, inspection_token='fixture-only')


@pytest.mark.parametrize('digest', ['', 'a' * 63, 'A' * 64])
def test_invalid_challenge_digest_denied_before_provider(sqlite_app, monkeypatch, digest):
    def unexpected(*_args, **_kwargs):
        pytest.fail('Malformed challenge must not reach native provider.')

    monkeypatch.setattr(issuer_lifecycle, 'observe_transit_issuer', unexpected)
    intent = issuer_lifecycle.IssuerApprovalIntent(_SCOPE, digest, 1, 'invalid')
    with pytest.raises(issuer_lifecycle.IssuerLifecycleDenied):
        issuer_lifecycle.approve_issuer_enrollment(actor_id=2, intent=intent, inspection_token='fixture-only')
