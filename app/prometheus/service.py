from __future__ import annotations

import time
from typing import Any

from app.extensions.db import db
from app.models import Cluster, PrometheusConfig
from app.prometheus.client import PrometheusClient
from app.prometheus.exceptions import (
    PrometheusError,
)
from app.prometheus.forms import PrometheusConfigForm


class PrometheusService:
    def __init__(
        self,
        cluster: Cluster,
    ) -> None:
        self.cluster = cluster

        config = PrometheusConfig.query.filter_by(
            cluster_id=cluster.id,
        ).first()

        if not config:
            raise PrometheusError('Prometheus configuration not found')

        self.client = PrometheusClient(config)

    def instant_query(
        self,
        query: str,
    ) -> dict[str, Any]:
        return self.client.query(query)

    def range_query(
        self,
        query: str,
        start: str,
        end: str,
        step: str,
    ) -> dict[str, Any]:
        return self.client.query_range(
            query=query,
            start=start,
            end=end,
            step=step,
        )

    def test_connection(
        self,
    ) -> dict[str, Any]:
        started = time.perf_counter()

        result = self.client.query('vector(1)')

        if result.get('status') != 'success':
            raise PrometheusError('Prometheus query failed')

        build_info = self.client.get_build_info()

        elapsed = time.perf_counter() - started

        version = build_info.get('data', {}).get('version', 'unknown')

        return {
            'success': True,
            'version': version,
            'response_time': round(
                elapsed,
                3,
            ),
        }

    @staticmethod
    def save_config(
        cluster: Cluster,
        form: PrometheusConfigForm,
    ) -> PrometheusConfig:
        config = cluster.prometheus_config

        endpoint = form.endpoint.data
        auth_type = form.auth_type.data
        timeout = form.timeout.data
        verify_ssl = form.verify_ssl.data

        if not endpoint:
            raise PrometheusError('Endpoint is required')

        endpoint = endpoint.strip()

        if not endpoint.startswith(
            (
                'http://',
                'https://',
            )
        ):
            endpoint = f'http://{endpoint}'

        if not auth_type:
            raise PrometheusError('Authentication type is required')

        if timeout is None:
            raise PrometheusError('Timeout is required')

        if not config:
            config = PrometheusConfig()

            config.cluster_id = cluster.id
            config.endpoint = endpoint
            config.auth_type = auth_type
            config.timeout = timeout
            config.verify_ssl = verify_ssl

            db.session.add(config)

        else:
            config.endpoint = endpoint
            config.auth_type = auth_type
            config.timeout = timeout
            config.verify_ssl = verify_ssl

        if auth_type == 'none':
            config.username = None
            config.password = None
            config.bearer_token = None

        elif auth_type == 'basic':
            config.username = form.username.data
            config.password = form.password.data
            config.bearer_token = None

        elif auth_type == 'bearer':
            config.username = None
            config.password = None
            config.bearer_token = form.bearer_token.data

        db.session.commit()

        return config
