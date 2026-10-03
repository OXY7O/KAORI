from __future__ import annotations

from time import perf_counter
from typing import Any

import requests
from requests import Response
from requests.auth import HTTPBasicAuth

from app.integrations.registry.providers.harbor.exceptions import (
    HarborAuthError,
    HarborConnectionError,
    HarborResponseError,
)


class HarborClient:
    """Read-only Harbor API v2.0 client used by provider readiness flows."""

    def __init__(
        self,
        *,
        endpoint: str,
        auth_type: str = 'basic',
        username: str | None = None,
        password: str | None = None,
        timeout: int = 5,
        verify_ssl: bool = True,
    ) -> None:
        self.endpoint = endpoint.rstrip('/')
        self.auth_type = auth_type
        self.username = username
        self.password = password
        self.timeout = max(1, min(int(timeout or 5), 30))
        self.verify_ssl = bool(verify_ssl)

    def test_connection(self) -> dict[str, Any]:
        started = perf_counter()
        system_info = self.get_system_info()
        elapsed_ms = int((perf_counter() - started) * 1000)
        version = str(system_info.get('harbor_version') or '').strip()
        if not version:
            raise HarborResponseError('Harbor system info did not include harbor_version.')
        return {
            'connected': True,
            'response_time_ms': elapsed_ms,
            'version': version,
            'registry_url': system_info.get('registry_url'),
            'external_url': system_info.get('external_url'),
        }

    def get_health(self) -> dict[str, Any]:
        payload = self._request_json('/api/v2.0/health')
        if not isinstance(payload, dict):
            raise HarborResponseError('Harbor health response is not an object.')
        return payload

    def get_system_info(self) -> dict[str, Any]:
        payload = self._request_json('/api/v2.0/systeminfo')
        if not isinstance(payload, dict):
            raise HarborResponseError('Harbor system info response is not an object.')
        return payload

    def list_projects(self, *, page: int = 1, page_size: int = 1) -> list[dict[str, Any]]:
        payload = self._request_json('/api/v2.0/projects', params={'page': page, 'page_size': page_size})
        return self._object_list(payload, 'projects')

    def list_repositories(self, *, page: int = 1, page_size: int = 1) -> list[dict[str, Any]]:
        payload = self._request_json('/api/v2.0/repositories', params={'page': page, 'page_size': page_size})
        return self._object_list(payload, 'repositories')

    @staticmethod
    def _object_list(payload: Any, label: str) -> list[dict[str, Any]]:
        if not isinstance(payload, list):
            raise HarborResponseError(f'Harbor {label} response is not a list.')
        return [item for item in payload if isinstance(item, dict)]

    def _request_json(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        response = self._request(path, params=params)
        try:
            return response.json()
        except ValueError as exc:
            raise HarborResponseError(
                f'Harbor returned a non-JSON response for {path}.',
                status=response.status_code,
            ) from exc

    def _request(self, path: str, *, params: dict[str, Any] | None = None) -> Response:
        auth = None
        if self.auth_type == 'basic' and self.username:
            auth = HTTPBasicAuth(self.username, self.password or '')
        try:
            response = requests.get(
                f'{self.endpoint}{path}',
                params=params,
                auth=auth,
                timeout=self.timeout,
                verify=self.verify_ssl,
                headers={'Accept': 'application/json'},
            )
        except requests.RequestException as exc:
            raise HarborConnectionError(str(exc)) from exc

        if response.status_code in {401, 403}:
            raise HarborAuthError(
                f'Harbor authentication or authorization failed with HTTP {response.status_code}.',
                status=response.status_code,
            )
        if response.status_code >= 400:
            raise HarborResponseError(
                f'Harbor returned HTTP {response.status_code} for {path}.',
                status=response.status_code,
            )
        return response
