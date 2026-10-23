"""Bounded GitHub.com App API transport and installation-readiness probe.

GitHub remains the permission/install authority. This transport never
caches installation tokens, logs responses, or mutates repository state.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Callable, Mapping

import requests

from app.integrations.source_control.source_control.providers.github.auth import (
    _positive_provider_id,
    build_app_jwt,
)

_API_ORIGIN = 'https://api.github.com'
_API_VERSION = '2026-03-10'
_MAX_RESPONSE_BYTES = 262_144
_READ_PERMISSIONS = frozenset({
    'metadata', 'contents', 'pull_requests', 'actions', 'checks',
    'deployments', 'issues', 'administration',
})


class GitHubProviderError(ValueError):
    """Fail closed with bounded error text; never attach HTTP bodies or tokens."""


@dataclass(frozen=True, slots=True)
class InstallationToken:
    token: str = field(repr=False)
    expires_at: datetime
    permissions: Mapping[str, str]
    repository_selection: str


@dataclass(frozen=True, slots=True)
class InstallationReadiness:
    app_id: int
    installation_id: int
    account_id: int
    account_type: str
    repository_selection: str
    granted_repository_count: int
    permission_names: tuple[str, ...]
    observed_at: datetime


def _id(value: str | int) -> int:
    try:
        return _positive_provider_id(value)
    except ValueError as exc:
        raise GitHubProviderError('GitHub provider native ID is invalid.') from exc


def _permissions(requested: Mapping[str, str]) -> dict[str, str]:
    if not requested or any(key not in _READ_PERMISSIONS or val != 'read' for key, val in requested.items()):
        raise GitHubProviderError('Only explicit, approved read-only GitHub App permissions are supported.')
    return dict(requested)


def _safe_json_request(
    method: str,
    path: str,
    *,
    bearer: str,
    payload: Mapping[str, Any] | None = None,
    session_factory: Callable[[], requests.Session] = requests.Session,
) -> tuple[int, dict[str, Any]]:
    """Only known API paths supplied by the provider service may be called."""
    if method not in {'GET', 'POST'} or not path.startswith('/') or (
        '?' in path and path != '/installation/repositories?per_page=1'
    ) or '//' in path or '\\' in path or '#' in path:
        raise GitHubProviderError('Unsupported GitHub provider API request.')
    if not bearer:
        raise GitHubProviderError('GitHub App authorization is unavailable.')
    session = session_factory()
    session.trust_env = False  # no ambient proxy, netrc or redirects
    response = None
    try:
        response = session.request(
            method,
            _API_ORIGIN + path,
            headers={
                'Accept': 'application/vnd.github+json',
                'Authorization': f'Bearer {bearer}',
                'X-GitHub-Api-Version': _API_VERSION,
            },
            json=dict(payload) if payload is not None else None,
            timeout=(3, 10),
            verify=True,
            allow_redirects=False,
            stream=True,
        )
        if response.status_code in {301, 302, 303, 307, 308}:
            raise GitHubProviderError('GitHub API redirects are not permitted.')
        if response.status_code not in {200, 201}:
            # Never echo response body: provider may include sensitive context.
            raise GitHubProviderError('GitHub installation API request was rejected or unavailable.')
        body = bytearray()
        for chunk in response.iter_content(chunk_size=16_384):
            body.extend(chunk)
            if len(body) > _MAX_RESPONSE_BYTES:
                raise GitHubProviderError('GitHub installation API response exceeds safe size.')
        try:
            data = json.loads(bytes(body))
        except (UnicodeDecodeError, ValueError) as exc:
            raise GitHubProviderError('GitHub API returned an invalid JSON response.') from exc
        if not isinstance(data, dict):
            raise GitHubProviderError('GitHub API response must be an object.')
        return response.status_code, data
    except requests.RequestException as exc:
        raise GitHubProviderError('GitHub API TLS, transport, or network request failed.') from exc
    finally:
        if response is not None:
            response.close()
        session.close()


class GitHubAppClient:
    """Installation-scoped read-only probe; not a GitHub repository collector."""

    def __init__(
        self,
        *,
        app_id: str | int,
        private_key_pem: str,
        session_factory: Callable[[], requests.Session] = requests.Session,
    ) -> None:
        self.app_id = _id(app_id)
        if not private_key_pem:
            raise GitHubProviderError('GitHub App signing credential is unavailable.')
        self._private_key_pem = private_key_pem
        self._session_factory = session_factory

    def _app_jwt(self) -> str:
        return build_app_jwt(self.app_id, self._private_key_pem)

    def _request(
        self, method: str, path: str, *, bearer: str, payload: Mapping[str, Any] | None = None
    ) -> tuple[int, dict[str, Any]]:
        return _safe_json_request(
            method, path, bearer=bearer, payload=payload, session_factory=self._session_factory
        )

    def installation_detail(self, installation_id: str | int, expected_account_id: str | int) -> dict[str, Any]:
        """Check App, installation, account, suspension and repository scope."""
        installation = _id(installation_id)
        account = _id(expected_account_id)
        status, data = self._request(
            'GET', f'/app/installations/{installation}', bearer=self._app_jwt()
        )
        native_account = data.get('account')
        if (
            status != 200 or data.get('id') != installation
            or data.get('app_id') != self.app_id
            or not isinstance(native_account, dict) or native_account.get('id') != account
            or data.get('suspended_at') is not None
        ):
            raise GitHubProviderError('GitHub installation or account authorization does not match.')
        if data.get('repository_selection') not in {'all', 'selected'}:
            raise GitHubProviderError('GitHub repository grant scope is unknown.')
        return data

    def mint_installation_token(
        self,
        installation_id: str | int,
        *,
        permissions: Mapping[str, str],
    ) -> InstallationToken:
        """Explicit read-only downscope; token retained in-memory only."""
        installation = _id(installation_id)
        requested = _permissions(permissions)
        status, data = self._request(
            'POST',
            f'/app/installations/{installation}/access_tokens',
            bearer=self._app_jwt(),
            payload={'permissions': requested},
        )
        token = data.get('token')
        expiry = data.get('expires_at')
        native_permissions = data.get('permissions')
        if status != 201 or not isinstance(token, str) or not token or not isinstance(expiry, str):
            raise GitHubProviderError('GitHub installation token was not issued.')
        if not isinstance(native_permissions, dict):
            raise GitHubProviderError('GitHub installation token permission evidence is absent.')
        if any(native_permissions.get(key) != 'read' for key in requested):
            raise GitHubProviderError('GitHub installation token lacks the requested read permissions.')
        try:
            expiration = datetime.fromisoformat(expiry.replace('Z', '+00:00'))
        except ValueError as exc:
            raise GitHubProviderError('GitHub installation token expiry is invalid.') from exc
        if expiration.tzinfo is None or expiration.astimezone(UTC) <= datetime.now(UTC) + timedelta(seconds=60):
            raise GitHubProviderError('GitHub installation token is expired or near expiration.')
        selection = data.get('repository_selection')
        if selection not in {'all', 'selected'}:
            raise GitHubProviderError('GitHub installation token repository scope is unknown.')
        return InstallationToken(
            token=token, expires_at=expiration, permissions=requested,
            repository_selection=selection,
        )

    def validate_installation(
        self, installation_id: str | int, expected_account_id: str | int
    ) -> InstallationReadiness:
        """Test a provider grant with one bounded metadata-only repository probe."""
        data = self.installation_detail(installation_id, expected_account_id)
        token = self.mint_installation_token(installation_id, permissions={'metadata': 'read'})
        status, page = self._request(
            'GET', '/installation/repositories?per_page=1', bearer=token.token
        )
        count = page.get('total_count')
        repositories = page.get('repositories')
        if status != 200 or isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise GitHubProviderError('GitHub installation repository coverage is unverified.')
        if not isinstance(repositories, list):
            raise GitHubProviderError('GitHub installation repository listing is unavailable.')
        permission_set = data.get('permissions')
        if not isinstance(permission_set, dict):
            raise GitHubProviderError('GitHub installation permission coverage is unknown.')
        return InstallationReadiness(
            app_id=self.app_id,
            installation_id=_id(installation_id),
            account_id=_id(expected_account_id),
            account_type=str(data['account'].get('type') or 'unknown')[:30],
            repository_selection=str(data['repository_selection']),
            granted_repository_count=count,
            permission_names=tuple(sorted(str(k) for k, v in permission_set.items() if v == 'read')),
            observed_at=datetime.now(UTC),
        )
