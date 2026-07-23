from __future__ import annotations

from typing import Any

import requests
from requests.auth import HTTPBasicAuth

from app.integrations.binding_selectors import BindingSelectorError, apply_promql_scope
from app.integrations.prometheus.exceptions import (
    PrometheusAuthenticationError,
    PrometheusConnectionError,
    PrometheusQueryError,
)
from app.models.prometheus import PrometheusInstance


class PrometheusClient:
    def __init__(
        self,
        config: PrometheusInstance,
        *,
        scope_selector: dict[str, Any] | None = None,
        request_timeout_seconds: int | None = None,
    ) -> None:
        self.config = config
        self.scope_selector = scope_selector
        self.request_timeout_seconds = request_timeout_seconds
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
                timeout=self._request_timeout(),
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

    def _request_timeout(self) -> tuple[int, int]:
        read_timeout = min(
            max(int(self.request_timeout_seconds or self.config.timeout or 5), 1),
            120,
        )
        connect_timeout = min(max(read_timeout, 2), 5)
        return connect_timeout, read_timeout

    def query(
        self,
        query: str,
    ) -> dict[str, Any]:
        return self._get('/api/v1/query', {'query': self._scope_query(query)})

    def query_at(self, query: str, timestamp: float) -> dict[str, Any]:
        return self._get('/api/v1/query', {'query': self._scope_query(query), 'time': timestamp})

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
        params: list[tuple[str, Any]] = [('match[]', self._scope_query(metric)) for metric in metrics]
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
                'query': self._scope_query(query),
                'start': start,
                'end': end,
                'step': step,
            },
        )

    def _scope_query(self, query: str) -> str:
        try:
            return apply_promql_scope(query, self.scope_selector)
        except BindingSelectorError as exc:
            raise PrometheusQueryError(str(exc)) from exc

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
