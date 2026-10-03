from __future__ import annotations

from time import perf_counter
from typing import Any
from urllib.parse import quote

import requests
from requests import Response
from requests.auth import HTTPBasicAuth

from app.integrations.registry.providers.harbor.exceptions import (
    HarborAuthError,
    HarborConnectionError,
    HarborResponseError,
)


class HarborClient:
    """Read-only Harbor API v2.0 client used by readiness and committed-evidence collectors."""

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

    def list_all_projects(self, *, page_size: int = 100) -> list[dict[str, Any]]:
        return self._paged(lambda page, size: self.list_projects(page=page, page_size=size), page_size=page_size)

    def list_repositories(
        self,
        *,
        project_name_or_id: str | int,
        page: int = 1,
        page_size: int = 1,
    ) -> list[dict[str, Any]]:
        project_scope = str(project_name_or_id).strip()
        if not project_scope:
            raise HarborResponseError('Harbor project name or id is required for repository discovery.')
        encoded_scope = quote(project_scope, safe='')
        payload = self._request_json(
            f'/api/v2.0/projects/{encoded_scope}/repositories',
            params={'page': page, 'page_size': page_size},
        )
        return self._object_list(payload, 'repositories')

    def list_all_repositories(
        self,
        *,
        project_name_or_id: str | int,
        page_size: int = 100,
    ) -> list[dict[str, Any]]:
        return self._paged(
            lambda page, size: self.list_repositories(
                project_name_or_id=project_name_or_id,
                page=page,
                page_size=size,
            ),
            page_size=page_size,
        )

    def list_artifacts(
        self,
        *,
        project_name_or_id: str | int,
        repository_name: str,
        page: int = 1,
        page_size: int = 100,
        with_scan_overview: bool = False,
        with_sbom_overview: bool = False,
        with_signature: bool = False,
        with_immutable_status: bool = False,
    ) -> list[dict[str, Any]]:
        project_scope = str(project_name_or_id).strip()
        repository_scope = str(repository_name).strip().strip('/')
        if not project_scope or not repository_scope:
            raise HarborResponseError('Harbor project and repository are required for artifact discovery.')
        encoded_project = quote(project_scope, safe='')
        encoded_repository = quote(quote(repository_scope, safe=''), safe='')
        payload = self._request_json(
            f'/api/v2.0/projects/{encoded_project}/repositories/{encoded_repository}/artifacts',
            params={
                'page': page,
                'page_size': page_size,
                'with_tag': 'true',
                'with_label': 'false',
                'with_scan_overview': str(bool(with_scan_overview)).lower(),
                'with_sbom_overview': str(bool(with_sbom_overview)).lower(),
                'with_signature': str(bool(with_signature)).lower(),
                'with_immutable_status': str(bool(with_immutable_status)).lower(),
            },
        )
        return self._object_list(payload, 'artifacts')

    def list_all_artifacts(
        self,
        *,
        project_name_or_id: str | int,
        repository_name: str,
        page_size: int = 100,
        with_scan_overview: bool = False,
        with_sbom_overview: bool = False,
        with_signature: bool = False,
        with_immutable_status: bool = False,
    ) -> list[dict[str, Any]]:
        return self._paged(
            lambda page, size: self.list_artifacts(
                project_name_or_id=project_name_or_id,
                repository_name=repository_name,
                page=page,
                page_size=size,
                with_scan_overview=with_scan_overview,
                with_sbom_overview=with_sbom_overview,
                with_signature=with_signature,
                with_immutable_status=with_immutable_status,
            ),
            page_size=page_size,
        )


    def get_vulnerability_report(
        self,
        *,
        project_name_or_id: str | int,
        repository_name: str,
        reference: str,
    ) -> dict[str, Any]:
        project_scope = quote(str(project_name_or_id).strip(), safe='')
        repository_scope = quote(quote(str(repository_name).strip().strip('/'), safe=''), safe='')
        artifact_reference = quote(str(reference).strip(), safe='')
        payload = self._request_json(
            f'/api/v2.0/projects/{project_scope}/repositories/{repository_scope}/artifacts/{artifact_reference}/additions/vulnerabilities',
            headers={
                'X-Accept-Vulnerabilities': (
                    'application/vnd.security.vulnerability.report; version=1.1, '
                    'application/vnd.scanner.adapter.vuln.report.harbor+json; version=1.0'
                )
            },
        )
        if not isinstance(payload, dict):
            raise HarborResponseError('Harbor vulnerability report response is not an object.')
        return payload

    @staticmethod
    def _paged(fetch_page, *, page_size: int) -> list[dict[str, Any]]:
        size = max(1, min(int(page_size or 100), 100))
        page = 1
        records: list[dict[str, Any]] = []
        while True:
            batch = list(fetch_page(page, size))
            records.extend(batch)
            if len(batch) < size:
                return records
            page += 1
            if page > 10000:
                raise HarborResponseError('Harbor pagination exceeded the safety limit.')

    @staticmethod
    def _object_list(payload: Any, label: str) -> list[dict[str, Any]]:
        if not isinstance(payload, list):
            raise HarborResponseError(f'Harbor {label} response is not a list.')
        return [item for item in payload if isinstance(item, dict)]

    def _request_json(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        response = self._request(path, params=params, headers=headers)
        try:
            return response.json()
        except ValueError as exc:
            raise HarborResponseError(
                f'Harbor returned a non-JSON response for {path}.',
                status=response.status_code,
            ) from exc

    def _request(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Response:
        auth = None
        if self.auth_type == 'basic' and self.username:
            auth = HTTPBasicAuth(self.username, self.password or '')
        request_headers = {'Accept': 'application/json'}
        request_headers.update(headers or {})
        try:
            response = requests.get(
                f'{self.endpoint}{path}',
                params=params,
                auth=auth,
                timeout=self.timeout,
                verify=self.verify_ssl,
                headers=request_headers,
            )
        except requests.RequestException as exc:
            raise HarborConnectionError(
                'Harbor API request failed before a response was received.'
            ) from exc

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
