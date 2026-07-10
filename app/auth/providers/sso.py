from __future__ import annotations

from app.auth.results import AuthResult


class SsoAuthProvider:
    source = 'sso'

    def authenticate(self, username: str, password: str) -> AuthResult:
        raise NotImplementedError('SSO authentication provider is planned for a later MVP2 auth phase.')
