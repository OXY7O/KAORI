from __future__ import annotations

from time import perf_counter
from typing import Any

import requests
from requests import Response
from requests.auth import HTTPBasicAuth

from app.alertmanager.exceptions import (
    AlertmanagerAuthError,
    AlertmanagerConnectionError,
    AlertmanagerResponseError,
)


class AlertmanagerClient:
    def __init__(
        self,
        *,
        endpoint: str,
        auth_type: str = 'none',
        username: str | None = None,
        password: str | None = None,
        bearer_token: str | None = None,
        timeout: int = 5,
        verify_ssl: bool = True,
    ) -> None:
        self.endpoint = endpoint.rstrip(
            '/',
        )
        self.auth_type = auth_type
        self.username = username
        self.password = password
        self.bearer_token = bearer_token
        self.timeout = timeout
        self.verify_ssl = verify_ssl

    def get_status(
        self,
    ) -> dict[str, Any]:
        return self._request_json(
            path='/api/v2/status',
        )

    def get_alerts(
        self,
        *,
        active: bool = True,
        silenced: bool = True,
        inhibited: bool = True,
        unprocessed: bool = True,
        receiver: str | None = None,
        filters: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            'active': str(active).lower(),
            'silenced': str(silenced).lower(),
            'inhibited': str(inhibited).lower(),
            'unprocessed': str(unprocessed).lower(),
        }

        if receiver:
            params['receiver'] = receiver

        if filters:
            params['filter'] = filters

        response = self._request_json(
            path='/api/v2/alerts',
            params=params,
        )

        if not isinstance(
            response,
            list,
        ):
            raise AlertmanagerResponseError(
                'Alertmanager alerts response is not a list.',
            )

        normalized_response: list[dict[str, Any]] = []

        for item in response:
            if isinstance(
                item,
                dict,
            ):
                normalized_response.append(
                    item,
                )

        return normalized_response

    def get_silences(
        self,
        *,
        filters: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {}

        if filters:
            params['filter'] = filters

        response = self._request_json(
            path='/api/v2/silences',
            params=params,
        )

        if not isinstance(
            response,
            list,
        ):
            raise AlertmanagerResponseError(
                'Alertmanager silences response is not a list.',
            )

        normalized_response: list[dict[str, Any]] = []

        for item in response:
            if isinstance(
                item,
                dict,
            ):
                normalized_response.append(
                    item,
                )

        return normalized_response

    def test_connection(
        self,
    ) -> dict[str, Any]:
        started_at = perf_counter()
        status_payload = self.get_status()
        elapsed_ms = int((perf_counter() - started_at) * 1000)

        version_info = status_payload.get(
            'versionInfo',
            {},
        )

        if not isinstance(
            version_info,
            dict,
        ):
            version_info = {}

        cluster_info = status_payload.get(
            'cluster',
            {},
        )

        if not isinstance(
            cluster_info,
            dict,
        ):
            cluster_info = {}

        return {
            'connected': True,
            'response_time_ms': elapsed_ms,
            'version': version_info.get(
                'version',
                'unknown',
            ),
            'cluster_status': cluster_info.get(
                'status',
                'unknown',
            ),
            'payload': status_payload,
        }

    def _request_json(
        self,
        *,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        response = self._request(
            path=path,
            params=params,
        )

        try:
            return response.json()
        except ValueError as exc:
            raise AlertmanagerResponseError(
                'Alertmanager returned a non-JSON response.',
            ) from exc

    def _request(
        self,
        *,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> Response:
        url = f'{self.endpoint}{path}'

        try:
            response = requests.get(
                url,
                params=params,
                headers=self._headers(),
                auth=self._auth(),
                timeout=(2, min(max(int(self.timeout or 5), 1), 5)),
                verify=self.verify_ssl,
            )
        except requests.RequestException as exc:
            raise AlertmanagerConnectionError(
                str(
                    exc,
                )
            ) from exc

        if response.status_code in {
            401,
            403,
        }:
            raise AlertmanagerAuthError(
                f'Alertmanager authentication failed with status {response.status_code}.',
            )

        if response.status_code >= 400:
            raise AlertmanagerResponseError(
                f'Alertmanager returned status {response.status_code}: {response.text[:300]}',
            )

        return response

    def _headers(
        self,
    ) -> dict[str, str]:
        headers = {
            'Accept': 'application/json',
        }

        if self.auth_type == 'bearer' and self.bearer_token:
            headers['Authorization'] = f'Bearer {self.bearer_token}'

        return headers

    def _auth(
        self,
    ) -> HTTPBasicAuth | None:
        if self.auth_type == 'basic' and self.username and self.password:
            return HTTPBasicAuth(
                self.username,
                self.password,
            )

        return None
