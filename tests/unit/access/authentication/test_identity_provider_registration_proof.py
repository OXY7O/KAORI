"""Server-owned connection proof for new Identity Provider registration (#2921)."""

from __future__ import annotations

import pytest
from flask import Flask

from app.access.identity_providers.forms import IdentityProviderForm
from app.access.identity_providers.registration_proof import (
    issue_registration_proof,
    verify_registration_proof,
)


@pytest.fixture
def app():
    app = Flask(__name__)
    app.config.update(SECRET_KEY='unit-test-only', WTF_CSRF_ENABLED=False)
    return app


def _form() -> IdentityProviderForm:
    form = IdentityProviderForm()
    form.key.data = 'kaori-ad-uat'
    form.provider_key.data = 'ldap_directory'
    form.display_name.data = 'KAORI Active Directory'
    form.enabled.data = False
    form.server_uri.data = 'ldaps://adds.kaori.cloud:636'
    form.base_dn.data = 'OU=UAT Users,DC=kaori,DC=cloud'
    form.bind_dn.data = 'CN=svc-kaori,DC=kaori,DC=cloud'
    form.bind_password_env.data = 'KAORI_LDAP_BIND_PASSWORD'
    form.user_filter.data = '(sAMAccountName=*{query}*)'
    form.tls_mode.data = 'ldaps'
    form.username_attribute.data = 'sAMAccountName'
    form.email_attribute.data = 'mail'
    form.display_name_attribute.data = 'displayName'
    form.stable_id_attribute.data = 'objectGUID'
    return form


def test_successful_proof_allows_only_original_actor_and_payload(app) -> None:
    with app.test_request_context():
        form = _form()
        proof = issue_registration_proof(form=form, user_id=11)
        assert verify_registration_proof(token=proof, form=form, user_id=11) == (True, '')
        assert verify_registration_proof(token=proof, form=form, user_id=12)[0] is False


@pytest.mark.parametrize(
    ('field', 'value'),
    [
        ('server_uri', 'ldaps://other.kaori.cloud:636'),
        ('bind_dn', 'CN=other,DC=kaori,DC=cloud'),
        ('bind_password_env', 'OTHER_SECRET'),
        ('enabled', True),
        ('provider_key', 'google'),
        ('key', 'another-provider'),
        ('display_name', 'Changed Name'),
        ('tls_mode', 'starttls'),
        ('user_filter', '(sAMAccountName=other)'),
        ('default_role_id', 1),
        ('jit_enabled', True),
        ('admission_values', 'other.example'),
    ],
)
def test_any_sensitive_change_invalidates_proof(app, field: str, value: object) -> None:
    with app.test_request_context():
        form = _form()
        proof = issue_registration_proof(form=form, user_id=11)
        getattr(form, field).data = value
        valid, message = verify_registration_proof(token=proof, form=form, user_id=11)
        assert not valid
        assert 'changed' in message


def test_missing_and_tampered_proof_fail_closed(app) -> None:
    with app.test_request_context():
        form = _form()
        valid, message = verify_registration_proof(token='', form=form, user_id=11)
        assert not valid
        assert 'Test Connection' in message
        proof = issue_registration_proof(form=form, user_id=11)
        valid, message = verify_registration_proof(token=proof + 'corrupt', form=form, user_id=11)
        assert not valid
        assert 'invalid' in message


def test_expired_proof_requires_retest(app, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.access.identity_providers import registration_proof

    with app.test_request_context():
        form = _form()
        proof = issue_registration_proof(form=form, user_id=11)
        monkeypatch.setattr(registration_proof, 'REGISTRATION_PROOF_MAX_AGE_SECONDS', -1)
        valid, message = verify_registration_proof(token=proof, form=form, user_id=11)
        assert not valid
        assert 'expired' in message
