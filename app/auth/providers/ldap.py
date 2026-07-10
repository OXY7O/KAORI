from __future__ import annotations

from app.auth.results import AuthResult


class LdapAuthProvider:
    source = 'ldap'

    def authenticate(self, username: str, password: str) -> AuthResult:
        raise NotImplementedError('LDAP authentication provider is planned for a later MVP2 auth phase.')
