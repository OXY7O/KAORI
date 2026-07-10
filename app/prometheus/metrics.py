from __future__ import annotations

from typing import Any

from app.prometheus import queries
from app.prometheus.service import (
    PrometheusService,
)


class MetricsService:
    def __init__(
        self,
        prometheus_service: PrometheusService,
    ) -> None:
        self.prometheus = prometheus_service

    @staticmethod
    def _extract_consumers(
        response: dict,
    ) -> list[dict[str, str | float]]:
        results = response.get(
            'data',
            {},
        ).get(
            'result',
            [],
        )

        consumers = []

        for item in results:
            metric = item.get(
                'metric',
                {},
            )

            consumers.append(
                {
                    'namespace': metric.get(
                        'namespace',
                        '-',
                    ),
                    'pod': metric.get(
                        'pod',
                        '-',
                    ),
                    'value': float(item['value'][1]),
                }
            )

        return consumers

    @staticmethod
    def _extract_scalar(
        response: dict[str, Any],
    ) -> float:
        try:
            result = response['data']['result']

            if not result:
                return 0.0

            return float(result[0]['value'][1])

        except (
            KeyError,
            IndexError,
            ValueError,
            TypeError,
        ):
            return 0.0

    def get_cpu_utilization(
        self,
    ) -> float:
        response = self.prometheus.instant_query(queries.CLUSTER_CPU_UTILIZATION)

        return self._extract_scalar(response)

    def get_memory_utilization(
        self,
    ) -> float:
        response = self.prometheus.instant_query(queries.CLUSTER_MEMORY_UTILIZATION)

        return self._extract_scalar(response)

    def get_storage_utilization(
        self,
    ) -> float:
        response = self.prometheus.instant_query(queries.CLUSTER_STORAGE_UTILIZATION)

        return self._extract_scalar(response)

    def get_pod_count(
        self,
    ) -> int:
        response = self.prometheus.instant_query(queries.CLUSTER_POD_COUNT)

        return int(self._extract_scalar(response))

    def get_namespace_count(
        self,
    ) -> int:
        response = self.prometheus.instant_query(queries.CLUSTER_NAMESPACE_COUNT)

        return int(self._extract_scalar(response))

    def get_node_count(
        self,
    ) -> int:
        response = self.prometheus.instant_query(queries.CLUSTER_NODE_COUNT)

        return int(self._extract_scalar(response))

    def get_top_cpu_consumers(
        self,
    ) -> list[dict[str, str | float]]:
        response = self.prometheus.instant_query(
            queries.TOP_CPU_PODS,
        )

        return self._extract_consumers(
            response,
        )

    def get_cluster_summary(
        self,
    ) -> dict[str, int | float]:
        return {
            'nodes': self.get_node_count(),
            'namespaces': self.get_namespace_count(),
            'pods': self.get_pod_count(),
            'cpu_utilization': round(
                self.get_cpu_utilization(),
                2,
            ),
            'memory_utilization': round(
                self.get_memory_utilization(),
                2,
            ),
            'storage_utilization': round(
                self.get_storage_utilization(),
                2,
            ),
        }

    def get_top_memory_consumers(
        self,
    ) -> list[dict[str, str | float]]:
        response = self.prometheus.instant_query(
            queries.TOP_MEMORY_PODS,
        )

        return self._extract_consumers(
            response,
        )

    def get_cpu_capacity(
        self,
    ) -> float:
        response = self.prometheus.instant_query(queries.CLUSTER_CPU_CAPACITY)

        return self._extract_scalar(response)

    def get_memory_capacity(
        self,
    ) -> float:
        response = self.prometheus.instant_query(queries.CLUSTER_MEMORY_CAPACITY)

        return self._extract_scalar(response)

    def get_storage_capacity(
        self,
    ) -> float:
        response = self.prometheus.instant_query(queries.CLUSTER_STORAGE_CAPACITY)

        return self._extract_scalar(response)

    def get_cluster_capacity_summary(
        self,
    ) -> dict[str, float]:
        return {
            'cpu_capacity': self.get_cpu_capacity(),
            'memory_capacity': self.get_memory_capacity(),
            'storage_capacity': self.get_storage_capacity(),
        }
