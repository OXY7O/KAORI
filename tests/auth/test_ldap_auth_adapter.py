from __future__ import annotations

from types import SimpleNamespace

from app.auth.providers import ldap


class ColumnStub:
    def __eq__(self, _other):
        return self

    def is_(self, _other):
        return self

    def asc(self):
        return self


class QueryStub:
    def __init__(self, links):
        self.links = links

    def join(self, *_args):
        return self

    def filter(self, *_args):
        return self

    def order_by(self, *_args):
        return self

    def all(self):
        return self.links


class UserStub:
    id = ColumnStub()
    auth_source = ColumnStub()
    deleted_at = ColumnStub()

    def __init__(self, *, active=True):
        self.is_active = active


class LinkModelStub:
    user_id = ColumnStub()
    provider_id = ColumnStub()
    external_username = ColumnStub()
    id = ColumnStub()
    query = QueryStub([])


class ProviderModelStub:
    id = ColumnStub()
    provider_type = ColumnStub()
    enabled = ColumnStub()


def _install_models(monkeypatch, links) -> None:
    LinkModelStub.query = QueryStub(links)
    monkeypatch.setattr(ldap, 'ExternalIdentityLink', LinkModelStub)
    monkeypatch.setattr(ldap, 'IdentityProvider', ProviderModelStub)
    monkeypatch.setattr(ldap, 'User', UserStub)
    monkeypatch.setattr(ldap, 'func', SimpleNamespace(lower=lambda value: value))


def test_ldap_adapter_tries_matching_enabled_links_until_one_succeeds(monkeypatch) -> None:
    first_user = UserStub()
    second_user = UserStub()
    first_provider = SimpleNamespace(id=1, provider_type='ldap')
    second_provider = SimpleNamespace(id=2, provider_type='ldap')
    links = [
        SimpleNamespace(user=first_user, provider=first_provider, distinguished_name='CN=First'),
        SimpleNamespace(user=second_user, provider=second_provider, distinguished_name='CN=Second'),
    ]
    _install_models(monkeypatch, links)

    attempts: list[str] = []

    class Client:
        def __init__(self, provider):
            self.provider = provider

        def authenticate(self, distinguished_name, _password):
            attempts.append(distinguished_name)
            return self.provider.id == 2

    monkeypatch.setattr(ldap, 'LdapDirectoryClient', Client)

    result = ldap.LdapAuthProvider().authenticate('Operator', 'secret')

    assert result.success is True
    assert result.user is second_user
    assert attempts == ['CN=First', 'CN=Second']


def test_ldap_adapter_normalizes_provider_outage(monkeypatch) -> None:
    user = UserStub()
    provider = SimpleNamespace(id=1, provider_type='ldap')
    _install_models(
        monkeypatch,
        [SimpleNamespace(user=user, provider=provider, distinguished_name='CN=Operator')],
    )

    class Client:
        def __init__(self, _provider):
            pass

        def authenticate(self, _distinguished_name, _password):
            raise ldap.ExternalProviderError('offline')

    monkeypatch.setattr(ldap, 'LdapDirectoryClient', Client)

    result = ldap.LdapAuthProvider().authenticate('operator', 'secret')

    assert result.reason == 'provider_unavailable'
    assert result.user is user


def test_inactive_ldap_identity_is_rejected_without_directory_bind(monkeypatch) -> None:
    user = UserStub(active=False)
    provider = SimpleNamespace(id=1, provider_type='ldap')
    _install_models(
        monkeypatch,
        [SimpleNamespace(user=user, provider=provider, distinguished_name='CN=Operator')],
    )
    monkeypatch.setattr(
        ldap,
        'LdapDirectoryClient',
        lambda _provider: (_ for _ in ()).throw(AssertionError('directory bind should not run')),
    )

    result = ldap.LdapAuthProvider().authenticate('operator', 'secret')

    assert result.reason == 'user_inactive'
    assert result.user is user
