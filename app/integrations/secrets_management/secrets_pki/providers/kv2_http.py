from __future__ import annotations

import os
from time import perf_counter
from typing import Any

import requests

from app.integrations.secrets_management.secrets_pki.providers.kv2_transport import (
    validate_auth_mount,
    validate_secret_endpoint,
)


class SecretProviderError(ValueError):
    """Sanitized provider failure; never holds raw response or credentials."""


_HEALTH_STATUS = {
    200: 'active',
    429: 'standby',
    472: 'dr_secondary',
    473: 'performance_standby',
    474: 'ha_unhealthy',
    501: 'uninitialized',
    503: 'sealed',
    530: 'removed',
}


class KV2HTTPTransport:
    """Shared HTTPS transport and unauthenticated status, independent of AppRole."""

    def __init__(
        self,
        *,
        endpoint: str,
        provider_label: str,
        allowed_origins_env: str,
        ca_bundle_env: str,
        namespace: str | None = None,
        timeout: int = 5,
    ) -> None:
        if not allowed_origins_env or not ca_bundle_env:
            raise SecretProviderError('A concrete provider transport policy is required.')
        self.provider_label = provider_label
        self.ca_bundle_env = ca_bundle_env
        self.endpoint = validate_secret_endpoint(
            endpoint, allowed_origins_env=allowed_origins_env, provider_label=provider_label
        )
        self.namespace = (namespace or '').strip('/')
        if any(ord(c) < 32 or ord(c) == 127 for c in self.namespace):
            raise SecretProviderError(f'{self.provider_label} namespace contains invalid control characters.')
        self.timeout = max(1, min(int(timeout), 30))

    def _request(
        self, path: str, *, method: str = 'GET', token: str | None = None, payload: dict[str, str] | None = None
    ) -> tuple[int, dict[str, Any]]:
        if not path.startswith('/v1/') or '//' in path or '?' in path:
            raise SecretProviderError(f'Unsupported {self.provider_label} API request.')
        headers = {'Accept': 'application/json'}
        if self.namespace:
            headers['X-Vault-Namespace'] = self.namespace
        if token is not None:
            headers['X-Vault-Token'] = token
        # Disable environment proxies/netrc, redirects and untrusted certificates.
        try:
            with requests.Session() as session:
                session.trust_env = False
                response = session.request(
                    method,
                    self.endpoint + path,
                    headers=headers,
                    json=payload,
                    timeout=self.timeout,
                    verify=os.getenv(self.ca_bundle_env, '').strip() or True,
                    allow_redirects=False,
                )
        except requests.RequestException as exc:
            raise SecretProviderError(
                f'{self.provider_label} TLS connection or request failed; verify approved egress and CA trust.'
            ) from exc
        if response.is_redirect or response.status_code in {301, 302, 303, 307, 308}:
            raise SecretProviderError(f'{self.provider_label} API redirects are not permitted.')
        # Never echo server error bodies: they can contain secret paths.
        if len(response.content) > 262_144:
            raise SecretProviderError(f'{self.provider_label} API response exceeded the bounded size.')
        try:
            data = response.json()
        except ValueError:
            data = {}
        if not isinstance(data, dict):
            raise SecretProviderError(f'Unexpected {self.provider_label} API response type.')
        return response.status_code, data

    def health(self) -> dict[str, Any]:
        # sys/health belongs to root namespace regardless of target namespace.
        original = self.namespace
        try:
            self.namespace = ''
            code, data = self._request('/v1/sys/health')
        finally:
            self.namespace = original
        if code not in _HEALTH_STATUS:
            raise SecretProviderError(f'{self.provider_label} health endpoint did not return a recognized state.')
        return {
            'status': _HEALTH_STATUS[code],
            'initialized': bool(data.get('initialized')),
            'sealed': bool(data.get('sealed')),
            'standby': bool(data.get('standby')),
            'performance_standby': bool(data.get('performance_standby')),
            'version': str(data.get('version') or '')[:64],
            'http_status': code,
        }

    def verify_active_version(self, *, expected_version: str) -> None:
        """Strict pre-bootstrap observation; never coerce absent or malformed health flags."""
        if self.namespace:
            raise SecretProviderError('Internal health verification requires the root namespace.')
        code, data = self._request('/v1/sys/health')
        if (
            code != 200
            or data.get('initialized') is not True
            or data.get('sealed') is not False
            or data.get('standby') is not False
            or ('performance_standby' in data and data['performance_standby'] is not False)
            or data.get('version') != expected_version
        ):
            raise SecretProviderError('Provider active health or approved version could not be verified.')


class KV2HTTPClient(KV2HTTPTransport):
    """Shared bounded AppRole observations; no material operation."""

    provider_label = 'Secrets provider'
    allowed_origins_env = ''
    ca_bundle_env = ''

    def __init__(
        self,
        *,
        endpoint: str,
        role_id: str,
        secret_id: str,
        namespace: str | None = None,
        auth_mount: str = 'approle',
        timeout: int = 5,
    ) -> None:
        super().__init__(
            endpoint=endpoint,
            provider_label=self.provider_label,
            allowed_origins_env=self.allowed_origins_env,
            ca_bundle_env=self.ca_bundle_env,
            namespace=namespace,
            timeout=timeout,
        )
        self.role_id = str(role_id)
        self.secret_id = str(secret_id)
        self.auth_mount = validate_auth_mount(auth_mount)
        if not self.role_id or not self.secret_id:
            raise SecretProviderError(f'{self.provider_label} AppRole RoleID and SecretID are required.')

    @classmethod
    def probe_health(cls, *, endpoint: str, timeout: int = 5) -> dict[str, Any]:
        """Read unauthenticated status through the concrete provider's TLS policy."""
        return KV2HTTPTransport(
            endpoint=endpoint,
            provider_label=cls.provider_label,
            allowed_origins_env=cls.allowed_origins_env,
            ca_bundle_env=cls.ca_bundle_env,
            timeout=timeout,
        ).health()

    def login(self) -> str:
        status, data = self._request(
            f'/v1/auth/{self.auth_mount}/login',
            method='POST',
            payload={'role_id': self.role_id, 'secret_id': self.secret_id},
        )
        auth = data.get('auth')
        token = auth.get('client_token') if isinstance(auth, dict) else None
        if status not in {200, 204} or not isinstance(token, str) or not token:
            raise SecretProviderError(
                f'{self.provider_label} AppRole authentication failed; verify RoleID, SecretID, mount and policy.'
            )
        return token

    def test_connection(self) -> dict[str, Any]:
        started = perf_counter()
        health = self.health()
        if health['status'] in {'sealed', 'uninitialized', 'removed', 'ha_unhealthy', 'dr_secondary'}:
            raise SecretProviderError(
                f'{self.provider_label} is not in a state that supports an AppRole connection test.'
            )
        token = self.login()
        status, data = self._request('/v1/auth/token/lookup-self', token=token)
        if status != 200 or not isinstance(data.get('data'), dict):
            raise SecretProviderError(f'{self.provider_label} AppRole token lookup-self is unavailable.')
        return {
            'connected': True,
            'version': health['version'],
            'health_status': health['status'],
            'response_time_ms': int((perf_counter() - started) * 1000),
        }

    def validate_capabilities(self) -> dict[str, Any]:
        """One AppRole login is used for token self-inspection and optional capability discovery."""
        started = perf_counter()
        health = self.health()
        if health['status'] not in {'active', 'standby', 'performance_standby'}:
            raise SecretProviderError(f'{self.provider_label} must be accessible and unsealed for Full Validation.')
        token = self.login()
        status, data = self._request('/v1/auth/token/lookup-self', token=token)
        if status != 200 or not isinstance(data.get('data'), dict):
            raise SecretProviderError(f'{self.provider_label} AppRole token lookup-self is unavailable.')
        mounts_status, mounts_data = self._request('/v1/sys/mounts', token=token)
        mounts = (
            'available'
            if mounts_status == 200 and isinstance(mounts_data.get('data'), dict)
            else ('permission_unavailable' if mounts_status in {403, 404} else 'unavailable')
        )
        return {
            'health': health,
            'mount_metadata': mounts,
            'response_time_ms': int((perf_counter() - started) * 1000),
        }
