from __future__ import annotations

from urllib.parse import urlencode

import requests
from flask import current_app

from app.auth.providers.browser import (
    SsoIdentity,
    SsoProviderError,
    load_client_secret,
    request_timeout_seconds,
)
from app.auth.providers.catalog import AuthProviderType
from app.models import IdentityProvider

GITHUB_AUTHORIZE_URL = 'https://github.com/login/oauth/authorize'
GITHUB_TOKEN_URL = 'https://github.com/login/oauth/access_token'
GITHUB_USER_URL = 'https://api.github.com/user'
GITHUB_EMAILS_URL = 'https://api.github.com/user/emails'
GITHUB_META_URL = 'https://api.github.com/meta'


class GitHubOAuthProvider:
    provider_type = AuthProviderType.GITHUB_OAUTH.value
    requires_nonce = False

    def build_authorization_url(
        self,
        provider: IdentityProvider,
        *,
        redirect_uri: str,
        state: str,
        nonce: str | None,
    ) -> str:
        del nonce
        if not provider.oidc_client_id:
            raise SsoProviderError('Client ID is not configured.')
        params = {
            'client_id': provider.oidc_client_id,
            'redirect_uri': redirect_uri,
            'scope': 'read:user user:email',
            'state': state,
            'allow_signup': 'false',
        }
        return f'{GITHUB_AUTHORIZE_URL}?{urlencode(params)}'

    def exchange_code(
        self,
        provider: IdentityProvider,
        *,
        code: str,
        redirect_uri: str,
        expected_nonce: str | None,
    ) -> SsoIdentity:
        del expected_nonce
        headers = {'Accept': 'application/json', 'User-Agent': 'KAORI-SSO'}
        try:
            token_response = requests.post(
                GITHUB_TOKEN_URL,
                data={
                    'client_id': provider.oidc_client_id,
                    'client_secret': load_client_secret(provider),
                    'code': code,
                    'redirect_uri': redirect_uri,
                },
                headers=headers,
                timeout=request_timeout_seconds(provider),
            )
            token_response.raise_for_status()
            access_token = token_response.json().get('access_token')
            if not access_token:
                raise SsoProviderError('GitHub did not return an access token.')

            api_headers = {
                'Accept': 'application/vnd.github+json',
                'Authorization': f'Bearer {access_token}',
                'X-GitHub-Api-Version': '2022-11-28',
                'User-Agent': 'KAORI-SSO',
            }
            user_response = requests.get(
                GITHUB_USER_URL,
                headers=api_headers,
                timeout=request_timeout_seconds(provider),
            )
            user_response.raise_for_status()
            profile = user_response.json()
            email = self._primary_email(api_headers, provider) or profile.get('email')
        except SsoProviderError:
            raise
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

    def validate_configuration(self, provider: IdentityProvider) -> str:
        if not provider.oidc_client_id:
            raise SsoProviderError('Client ID is required.')
        load_client_secret(provider)
        try:
            response = requests.get(
                GITHUB_META_URL,
                headers={
                    'Accept': 'application/vnd.github+json',
                    'X-GitHub-Api-Version': '2022-11-28',
                    'User-Agent': 'KAORI-Identity-Provider-Validation',
                },
                timeout=request_timeout_seconds(provider),
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            current_app.logger.warning('GitHub OAuth provider validation failed.', exc_info=True)
            raise SsoProviderError('The provider endpoint could not be reached or validated.') from exc
        return 'GitHub OAuth endpoints and secret references are reachable.'

    @staticmethod
    def _primary_email(headers: dict[str, str], provider: IdentityProvider) -> str | None:
        response = requests.get(
            GITHUB_EMAILS_URL,
            headers=headers,
            timeout=request_timeout_seconds(provider),
        )
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
