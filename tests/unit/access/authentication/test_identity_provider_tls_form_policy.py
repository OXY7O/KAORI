"""LDAP administrative form disallows plaintext even under legacy dev override (#2908)."""

import pytest
from flask import Flask
from wtforms.validators import ValidationError

from app.access.identity_providers.forms import IdentityProviderForm


@pytest.mark.parametrize(
    ('tls_mode', 'server_uri'),
    [('ldaps', 'ldaps://adds.kaori.cloud:636'), ('starttls', 'ldap://adds.kaori.cloud:389')],
)
def test_encrypted_modes_are_accepted(tls_mode: str, server_uri: str) -> None:
    app = Flask(__name__)
    app.config.update(SECRET_KEY='test-only', WTF_CSRF_ENABLED=False)
    with app.test_request_context():
        form = IdentityProviderForm()
        form.provider_key.data = 'ldap_directory'
        form.server_uri.data = server_uri
        form.tls_mode.data = tls_mode
        form.validate_tls_mode(form.tls_mode)


def test_plaintext_mode_rejected_even_with_development_override() -> None:
    app = Flask(__name__)
    app.config.update(SECRET_KEY='test-only', WTF_CSRF_ENABLED=False, AUTH_LDAP_ALLOW_PLAINTEXT=True)
    with app.test_request_context():
        form = IdentityProviderForm()
        form.provider_key.data = 'ldap_directory'
        form.server_uri.data = 'ldap://adds.kaori.cloud:389'
        form.tls_mode.data = 'plain'
        with pytest.raises(ValidationError, match='supported LDAP TLS mode'):
            form.validate_tls_mode(form.tls_mode)
