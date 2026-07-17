from __future__ import annotations

import hashlib
import os
import secrets
from dataclasses import dataclass
from urllib.parse import urlencode

import requests
from flask import current_app
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from app.models import IdentityProvider

GOOGLE_AUTHORIZE_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
GOOGLE_TOKEN_URL = 'https://oauth2.googleapis.com/token'
GITHUB_AUTHORIZE_URL = 'https://github.com/login/oauth/authorize'
GITHUB_TOKEN_URL = 'https://github.com/login/oauth/access_token'
GITHUB_USER_URL = 'https://api.github.com/user'
GITHUB_EMAILS_URL = 'https://api.github.com/user/emails'


class SsoProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class SsoIdentity:
    subject: str
    username: str
    email: str | None
    display_name: str | None
    avatar_url: str | None = None
    email_verified: bool = False


def generate_state() -> str:
    return secrets.token_urlsafe(32)


def generate_nonce() -> str:
    return secrets.token_urlsafe(32)


def state_fingerprint(state: str) -> str:
    return hashlib.sha256(state.encode('utf-8')).hexdigest()


def _client_secret(provider: IdentityProvider) -> str:
    env_name = (provider.oidc_client_secret_env or '').strip()
    if not env_name:
        raise SsoProviderError('Client secret environment-variable name is not configured.')
    value = os.getenv(env_name)
    if not value:
        raise SsoProviderError(f'The environment variable {env_name} is not available to KAORI.')
    return value


def _request_timeout(provider: IdentityProvider) -> int:
    return max(2, min(int(provider.connect_timeout_seconds or 5), 30))


def build_authorization_url(
    provider: IdentityProvider,
    *,
    redirect_uri: str,
    state: str,
    nonce: str | None,
) -> str:
    if not provider.oidc_client_id:
        raise SsoProviderError('Client ID is not configured.')

    if provider.provider_type == 'google_oidc':
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

    if provider.provider_type == 'github_oauth':
        params = {
            'client_id': provider.oidc_client_id,
            'redirect_uri': redirect_uri,
            'scope': 'read:user user:email',
            'state': state,
            'allow_signup': 'false',
        }
        return f'{GITHUB_AUTHORIZE_URL}?{urlencode(params)}'

    raise SsoProviderError('The selected provider does not support browser SSO.')


def exchange_code(
    provider: IdentityProvider,
    *,
    code: str,
    redirect_uri: str,
    expected_nonce: str | None,
) -> SsoIdentity:
    if provider.provider_type == 'google_oidc':
        return _exchange_google(provider, code=code, redirect_uri=redirect_uri, expected_nonce=expected_nonce)
    if provider.provider_type == 'github_oauth':
        return _exchange_github(provider, code=code, redirect_uri=redirect_uri)
    raise SsoProviderError('The selected provider does not support browser SSO.')


def validate_sso_provider(provider: IdentityProvider) -> str:
    if not provider.oidc_client_id:
        raise SsoProviderError('Client ID is required.')
    _client_secret(provider)

    timeout = _request_timeout(provider)
    try:
        if provider.provider_type == 'google_oidc':
            response = requests.get(
                'https://accounts.google.com/.well-known/openid-configuration',
                timeout=timeout,
            )
            response.raise_for_status()
            document = response.json()
            if document.get('issuer') not in {'https://accounts.google.com', 'accounts.google.com'}:
                raise SsoProviderError('Google discovery returned an unexpected issuer.')
            return 'Google OpenID Connect discovery and secret references are valid.'

        if provider.provider_type == 'github_oauth':
            response = requests.get(
                'https://api.github.com/meta',
                headers={
                    'Accept': 'application/vnd.github+json',
                    'X-GitHub-Api-Version': '2022-11-28',
                    'User-Agent': 'KAORI-Identity-Provider-Validation',
                },
                timeout=timeout,
            )
            response.raise_for_status()
            return 'GitHub OAuth endpoints and secret references are reachable.'
    except requests.RequestException as exc:
        current_app.logger.warning('SSO provider validation failed.', exc_info=True)
        raise SsoProviderError('The provider endpoint could not be reached or validated.') from exc

    raise SsoProviderError('The selected provider type cannot be validated as SSO.')


def _exchange_google(
    provider: IdentityProvider,
    *,
    code: str,
    redirect_uri: str,
    expected_nonce: str | None,
) -> SsoIdentity:
    try:
        response = requests.post(
            GOOGLE_TOKEN_URL,
            data={
                'code': code,
                'client_id': provider.oidc_client_id,
                'client_secret': _client_secret(provider),
                'redirect_uri': redirect_uri,
                'grant_type': 'authorization_code',
            },
            timeout=_request_timeout(provider),
        )
        response.raise_for_status()
        token_payload = response.json()
        raw_id_token = token_payload.get('id_token')
        if not raw_id_token:
            raise SsoProviderError('Google did not return an ID token.')
        claims = id_token.verify_oauth2_token(
            raw_id_token,
            google_requests.Request(),
            provider.oidc_client_id,
        )
    except (requests.RequestException, ValueError, KeyError) as exc:
        current_app.logger.warning('Google OIDC callback validation failed.', exc_info=True)
        raise SsoProviderError('Google sign-in could not be validated.') from exc

    if expected_nonce and claims.get('nonce') != expected_nonce:
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


def _exchange_github(provider: IdentityProvider, *, code: str, redirect_uri: str) -> SsoIdentity:
    headers = {
        'Accept': 'application/json',
        'User-Agent': 'KAORI-SSO',
    }
    try:
        token_response = requests.post(
            GITHUB_TOKEN_URL,
            data={
                'client_id': provider.oidc_client_id,
                'client_secret': _client_secret(provider),
                'code': code,
                'redirect_uri': redirect_uri,
            },
            headers=headers,
            timeout=_request_timeout(provider),
        )
        token_response.raise_for_status()
        token_payload = token_response.json()
        access_token = token_payload.get('access_token')
        if not access_token:
            raise SsoProviderError('GitHub did not return an access token.')

        api_headers = {
            'Accept': 'application/vnd.github+json',
            'Authorization': f'Bearer {access_token}',
            'X-GitHub-Api-Version': '2022-11-28',
            'User-Agent': 'KAORI-SSO',
        }
        user_response = requests.get(GITHUB_USER_URL, headers=api_headers, timeout=_request_timeout(provider))
        user_response.raise_for_status()
        profile = user_response.json()
        email = _github_primary_email(api_headers, provider) or profile.get('email')
    except (requests.RequestException, ValueError, KeyError) as exc:
        current_app.logger.warning('GitHub OAuth callback validation failed.', exc_info=True)
        raise SsoProviderError('GitHub sign-in could not be validated.') from exc

    subject = str(profile.get('id') or '').strip()
    username = str(profile.get('login') or '').strip()
    if not subject or not username:
        raise SsoProviderError('GitHub did not return a stable user identifier.')
    return SsoIdentity(
        subject=subject,
        username=username,
        email=str(email).strip().lower() if email else None,
        display_name=str(profile.get('name') or '').strip() or username,
        avatar_url=str(profile.get('avatar_url') or '').strip() or None,
        email_verified=bool(email),
    )


def _github_primary_email(headers: dict[str, str], provider: IdentityProvider) -> str | None:
    response = requests.get(GITHUB_EMAILS_URL, headers=headers, timeout=_request_timeout(provider))
    if response.status_code == 403:
        return None
    response.raise_for_status()
    emails = response.json()
    for item in emails:
        if item.get('primary') and item.get('verified') and item.get('email'):
            return str(item['email']).lower()
    for item in emails:
        if item.get('verified') and item.get('email'):
            return str(item['email']).lower()
    return None
