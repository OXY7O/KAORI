from __future__ import annotations

from types import SimpleNamespace
from typing import cast

from sqlalchemy.exc import SQLAlchemyError

from app.auth import sso
from app.auth.providers.browser import SsoIdentity


class QueryStub:
    def __init__(self, *, value=None, error: Exception | None = None):
        self.value = value
        self.error = error

    def filter_by(self, **_kwargs):
        if self.error is not None:
            raise self.error
        return self

    def first(self):
        return self.value


class LinkModelStub:
    query = QueryStub()


class ColumnStub:
    def in_(self, values):
        return ('in', tuple(values))


class ProviderModelStub:
    query = QueryStub()
    provider_type = ColumnStub()


def _identity() -> SsoIdentity:
    return SsoIdentity(
        subject='subject-1',
        username='operator',
        email='operator@example.com',
        display_name='KAORI Operator',
        email_verified=True,
    )


def _provider(**overrides):
    values = {
        'id': 10,
        'key': 'google',
        'provider_type': 'google_oidc',
        'jit_enabled': False,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_find_enabled_sso_provider_normalizes_key(monkeypatch) -> None:
    provider = _provider()
    observed: dict[str, object] = {}

    class Query:
        def filter_by(self, **kwargs):
            observed.update(kwargs)
            return self

        def filter(self, expression):
            observed['provider_type_filter'] = expression
            return self

        def first(self):
            return provider

    ProviderModelStub.query = Query()
    monkeypatch.setattr(sso, 'IdentityProvider', ProviderModelStub)

    assert sso.find_enabled_sso_provider(' GOOGLE ') is provider
    assert observed['key'] == 'google'
    assert observed['enabled'] is True
    assert observed['provider_type_filter'] == ('in', ('google_oidc', 'github_oauth'))


def test_existing_sso_link_is_synchronized_and_committed(monkeypatch) -> None:
    user = SimpleNamespace(is_active=True, display_name=None)
    link = SimpleNamespace(
        user=user,
        external_username=None,
        email=None,
        display_name=None,
        last_synced_at=None,
    )
    LinkModelStub.query = QueryStub(value=link)
    commits: list[bool] = []
    rollbacks: list[bool] = []
    monkeypatch.setattr(sso, 'ExternalIdentityLink', LinkModelStub)
    monkeypatch.setattr(
        sso,
        'db',
        SimpleNamespace(
            session=SimpleNamespace(
                commit=lambda: commits.append(True),
                rollback=lambda: rollbacks.append(True),
            )
        ),
    )

    result = sso.resolve_sso_identity(_provider(), _identity())

    assert result.success is True
    assert result.user is user
    assert link.external_username == 'operator'
    assert link.email == 'operator@example.com'
    assert user.display_name == 'KAORI Operator'
    assert commits == [True]
    assert rollbacks == []


def test_sso_identity_lookup_database_error_is_normalized(monkeypatch) -> None:
    LinkModelStub.query = QueryStub(error=SQLAlchemyError('offline'))
    rollbacks: list[bool] = []
    monkeypatch.setattr(sso, 'ExternalIdentityLink', LinkModelStub)
    monkeypatch.setattr(sso, 'db', SimpleNamespace(session=SimpleNamespace(rollback=lambda: rollbacks.append(True))))

    result = sso.resolve_sso_identity(_provider(), _identity())

    assert result.reason == 'database_unavailable'
    assert rollbacks == [True]


def test_unprovisioned_identity_is_rejected_when_jit_is_disabled(monkeypatch) -> None:
    LinkModelStub.query = QueryStub(value=None)
    monkeypatch.setattr(sso, 'ExternalIdentityLink', LinkModelStub)

    result = sso.resolve_sso_identity(_provider(jit_enabled=False), _identity())

    assert result.reason == 'identity_not_provisioned'
    assert result.success is False


def test_google_jit_requires_verified_email_from_allowed_domain() -> None:
    provider = _provider(
        provider_type='google_oidc',
        allowed_domains_list=['example.com'],
    )

    sso._enforce_admission(provider, _identity())

    unverified = SsoIdentity(
        subject='subject-1',
        username='operator',
        email='operator@example.com',
        display_name='Operator',
        email_verified=False,
    )
    try:
        sso._enforce_admission(provider, unverified)
    except sso.SsoAdmissionError as exc:
        assert 'verified email' in str(exc)
    else:
        raise AssertionError('unverified Google identity should be rejected')


def test_github_jit_accepts_username_or_numeric_subject_allow_list() -> None:
    provider = _provider(
        provider_type='github_oauth',
        allowed_subjects_list=['operator', '999'],
    )
    identity = SsoIdentity(
        subject='999',
        username='different-login',
        email=None,
        display_name='Operator',
    )

    sso._enforce_admission(provider, identity)


def test_github_jit_handles_missing_username_without_weakening_subject_admission() -> None:
    provider = _provider(
        provider_type='github_oauth',
        allowed_subjects_list=['999'],
    )
    identity = cast(
        SsoIdentity,
        SimpleNamespace(
            subject='999',
            username=None,
            email=None,
            display_name='Operator',
        ),
    )

    sso._enforce_admission(provider, identity)


def test_unsupported_provider_cannot_use_jit_admission() -> None:
    provider = _provider(provider_type='future_sso')
    try:
        sso._enforce_admission(provider, _identity())
    except sso.SsoAdmissionError as exc:
        assert 'does not support JIT' in str(exc)
    else:
        raise AssertionError('unsupported SSO provider should fail closed')


def test_jit_account_uses_only_verified_external_email() -> None:
    provider = _provider(key='github')
    unverified = SsoIdentity(
        subject='99',
        username='operator',
        email='public@example.com',
        display_name='Operator',
        email_verified=False,
    )
    verified = SsoIdentity(
        subject='99',
        username='operator',
        email='Verified@Example.com',
        display_name='Operator',
        email_verified=True,
    )

    assert sso._jit_account_email(provider, unverified) == 'github-99@external.invalid'
    assert sso._jit_account_email(provider, verified) == 'verified@example.com'
