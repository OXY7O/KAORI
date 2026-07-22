from __future__ import annotations

from urllib.parse import urlencode

import requests
from flask import current_app
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from app.auth.providers.browser import (
    SsoIdentity,
    SsoProviderError,
    load_client_secret,
    request_timeout_seconds,
)
from app.auth.providers.catalog import AuthProviderType
from app.models import IdentityProvider

GOOGLE_AUTHORIZE_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
GOOGLE_TOKEN_URL = 'https://oauth2.googleapis.com/token'
GOOGLE_DISCOVERY_URL = 'https://accounts.google.com/.well-known/openid-configuration'


class GoogleOidcProvider:
    provider_type = AuthProviderType.GOOGLE_OIDC.value
    requires_nonce = True

    def build_authorization_url(
        self,
        provider: IdentityProvider,
        *,
        redirect_uri: str,
        state: str,
        nonce: str | None,
    ) -> str:
        if not provider.oidc_client_id:
            raise SsoProviderError('Client ID is not configured.')
        if not nonce:
            raise SsoProviderError('Google OpenID Connect requires a nonce.')
        params = {
            'client_id': provider.oidc_client_id,
            'redirect_uri': redirect_uri,
            'response_type': 'code',
            'scope': 'openid email profile',
            'state': state,
            'nonce': nonce or '',
            'prompt': 'select_account',
        }
        return f'{GOOGLE_AUTHORIZE_URL}?{urlencode(params)}'

    def exchange_code(
        self,
        provider: IdentityProvider,
        *,
        code: str,
        redirect_uri: str,
        expected_nonce: str | None,
    ) -> SsoIdentity:
        if not expected_nonce:
            raise SsoProviderError('Google OpenID Connect callback is missing the expected nonce.')
        try:
            response = requests.post(
                GOOGLE_TOKEN_URL,
                data={
                    'code': code,
                    'client_id': provider.oidc_client_id,
                    'client_secret': load_client_secret(provider),
                    'redirect_uri': redirect_uri,
                    'grant_type': 'authorization_code',
                },
                timeout=request_timeout_seconds(provider),
            )
            response.raise_for_status()
            raw_id_token = response.json().get('id_token')
            if not raw_id_token:
                raise SsoProviderError('Google did not return an ID token.')
            claims = id_token.verify_oauth2_token(
                raw_id_token,
                google_requests.Request(),
                provider.oidc_client_id,
            )
        except SsoProviderError:
            raise
        except (requests.RequestException, ValueError, KeyError) as exc:
            current_app.logger.warning('Google OIDC callback validation failed.', exc_info=True)
            raise SsoProviderError('Google sign-in could not be validated.') from exc

        if claims.get('nonce') != expected_nonce:
            raise SsoProviderError('Google sign-in nonce validation failed.')
        subject = str(claims.get('sub') or '').strip()
        email = str(claims.get('email') or '').strip().lower() or None
        if not subject:
            raise SsoProviderError('Google did not return a stable subject identifier.')
        username = (email.split('@', 1)[0] if email else f'google-{subject[-12:]}').strip()
        return SsoIdentity(
            subject=subject,
            username=username,
            email=email,
            display_name=str(claims.get('name') or '').strip() or None,
            avatar_url=str(claims.get('picture') or '').strip() or None,
            email_verified=bool(claims.get('email_verified')),
        )

    def validate_configuration(self, provider: IdentityProvider) -> str:
        if not provider.oidc_client_id:
            raise SsoProviderError('Client ID is required.')
        load_client_secret(provider)
        try:
            response = requests.get(GOOGLE_DISCOVERY_URL, timeout=request_timeout_seconds(provider))
            response.raise_for_status()
            issuer = response.json().get('issuer')
        except (requests.RequestException, ValueError, KeyError) as exc:
            current_app.logger.warning('Google OIDC provider validation failed.', exc_info=True)
            raise SsoProviderError('The provider endpoint could not be reached or validated.') from exc
        if issuer not in {'https://accounts.google.com', 'accounts.google.com'}:
            raise SsoProviderError('Google discovery returned an unexpected issuer.')
        return 'Google OpenID Connect discovery and secret references are valid.'
