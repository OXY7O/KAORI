from __future__ import annotations

from types import SimpleNamespace

import pytest
from flask import Flask
from wtforms.validators import ValidationError

from app.users.forms import IdentityProviderForm


def _form(*, server_uri: str, provider_type: str = 'ldap'):
    return SimpleNamespace(
        provider_type=SimpleNamespace(data=provider_type),
        server_uri=SimpleNamespace(data=server_uri),
    )


def test_provider_form_rejects_plain_ldap_by_default() -> None:
    app = Flask(__name__)
    app.config['AUTH_LDAP_ALLOW_PLAINTEXT'] = False

    with app.app_context():
        with pytest.raises(ValidationError, match='disabled by KAORI'):
            IdentityProviderForm.validate_tls_mode(
                _form(server_uri='ldap://directory.example.com'),
                SimpleNamespace(data='plain'),
            )


def test_provider_form_rejects_uri_and_tls_mode_mismatch() -> None:
    app = Flask(__name__)
    app.config['AUTH_LDAP_ALLOW_PLAINTEXT'] = False

    with app.app_context():
        with pytest.raises(ValidationError, match='requires an ldaps://'):
            IdentityProviderForm.validate_tls_mode(
                _form(server_uri='ldap://directory.example.com'),
                SimpleNamespace(data='ldaps'),
            )


def test_provider_form_allows_plain_ldap_only_when_explicitly_enabled() -> None:
    app = Flask(__name__)
    app.config['AUTH_LDAP_ALLOW_PLAINTEXT'] = True

    with app.app_context():
        IdentityProviderForm.validate_tls_mode(
            _form(server_uri='ldap://directory.example.com'),
            SimpleNamespace(data='plain'),
        )
