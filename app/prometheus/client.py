from __future__ import annotations

from typing import Any

import requests
from requests.auth import HTTPBasicAuth

from app.models.prometheus import PrometheusInstance
from app.prometheus.exceptions import (
    PrometheusAuthenticationError,
    PrometheusConnectionError,
    PrometheusQueryError,
)


class PrometheusClient:
    def __init__(
        self,
        config: PrometheusInstance,
    ) -> None:
        self.config = config
        self.base_url = config.endpoint.rstrip('/')

    def _build_headers(
        self,
    ) -> dict[str, str]:
        headers: dict[str, str] = {}

        if self.config.auth_type == 'bearer' and self.config.bearer_token:
            headers['Authorization'] = f'Bearer {self.config.bearer_token}'

        return headers

    def _build_auth(
        self,
    ) -> HTTPBasicAuth | None:
        if self.config.auth_type == 'basic' and self.config.username and self.config.password:
            return HTTPBasicAuth(
                self.config.username,
                self.config.password,
            )

        return None

    def _get(
        self,
        path: str,
        params: dict[str, Any] | list[tuple[str, Any]] | None = None,
    ) -> dict[str, Any]:
        url = f'{self.base_url}{path}'

        try:
            response = requests.get(
                url,
                params=params,
                headers=self._build_headers(),
                auth=self._build_auth(),
                timeout=(2, min(max(int(self.config.timeout or 5), 1), 5)),
                verify=self.config.verify_ssl,
            )

            self._validate_response(response)

            return response.json()

        except requests.exceptions.ConnectionError as exc:
            raise PrometheusConnectionError(str(exc)) from exc

        except requests.exceptions.Timeout as exc:
            raise PrometheusConnectionError('Connection timeout') from exc

        except requests.exceptions.RequestException as exc:
            raise PrometheusConnectionError(str(exc)) from exc

    def query(
        self,
        query: str,
    ) -> dict[str, Any]:
        return self._get('/api/v1/query', {'query': query})

    def query_at(self, query: str, timestamp: float) -> dict[str, Any]:
        return self._get('/api/v1/query', {'query': query, 'time': timestamp})

    def label_values(self, label: str) -> dict[str, Any]:
        return self._get(f'/api/v1/label/{label}/values')

    def series(
        self,
        metrics: list[str],
        limit: int | None = None,
        *,
        start: float | None = None,
        end: float | None = None,
    ) -> dict[str, Any]:
        params: list[tuple[str, Any]] = [('match[]', metric) for metric in metrics]
        if limit is not None:
            params.append(('limit', limit))
        if start is not None:
            params.append(('start', start))
        if end is not None:
            params.append(('end', end))
        return self._get('/api/v1/series', params)

    def query_range(
        self,
        query: str,
        start: str,
        end: str,
        step: str,
    ) -> dict[str, Any]:
        return self._get(
            '/api/v1/query_range',
            {
                'query': query,
                'start': start,
                'end': end,
                'step': step,
            },
        )

    def get_build_info(
        self,
    ) -> dict[str, Any]:
        return self._get(
            '/api/v1/status/buildinfo',
        )

    @staticmethod
    def _validate_response(
        response: requests.Response,
    ) -> None:
        if response.status_code in (
            401,
            403,
        ):
            raise PrometheusAuthenticationError('Authentication failed')

        if response.status_code >= 400:
            detail = PrometheusClient._response_error_detail(response)
            message = f'HTTP {response.status_code}'
            if detail:
                message = f'{message}: {detail}'
            raise PrometheusQueryError(message)

    @staticmethod
    def _response_error_detail(response: requests.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            payload = None

        if isinstance(payload, dict):
            error_type = str(payload.get('errorType') or '').strip()
            error = str(payload.get('error') or '').strip()
            detail = ': '.join(part for part in (error_type, error) if part)
            if detail:
                return detail[:1000]

        return (response.text or '').strip()[:1000]

