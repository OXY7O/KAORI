from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from app.analytics.kubernetes.common.clusters import get_selected_cluster as resolve_selected_cluster
from app.analytics.kubernetes.common.presentation import present_metrics_source_status
from app.analytics.shared.coercion import safe_float
from app.integrations.consumer.contracts import ConsumerResult
from app.integrations.observability.metrics_source.exceptions import MetricsSourceError
from app.integrations.observability.metrics_source.query_profiles import get_kubernetes_query_expression
from app.metrics_sources.consumer import MetricsConsumer
from app.metrics_sources.service import MetricsService
from app.models import Cluster

CPU_CAPACITY = get_kubernetes_query_expression('analytics.utilization.queries.CPU_CAPACITY')
CPU_CAPACITY_BY_NODE = get_kubernetes_query_expression('analytics.utilization.queries.CPU_CAPACITY_BY_NODE')
CPU_USAGE = get_kubernetes_query_expression('analytics.utilization.queries.CPU_USAGE')
CPU_USAGE_BY_NODE = get_kubernetes_query_expression('analytics.utilization.queries.CPU_USAGE_BY_NODE')
CPU_UTILIZATION = get_kubernetes_query_expression('analytics.utilization.queries.CPU_UTILIZATION')
CPU_UTILIZATION_BY_NODE = get_kubernetes_query_expression('analytics.utilization.queries.CPU_UTILIZATION_BY_NODE')
DISK_PRESSURE_NODES = get_kubernetes_query_expression('analytics.utilization.queries.DISK_PRESSURE_NODES')
DISK_PRESSURE_NODES_BY_NODE = get_kubernetes_query_expression(
    'analytics.utilization.queries.DISK_PRESSURE_NODES_BY_NODE'
)
KUBERNETES_VERSION = get_kubernetes_query_expression('analytics.utilization.queries.KUBERNETES_VERSION')
MASTER_NODES = get_kubernetes_query_expression('analytics.utilization.queries.MASTER_NODES')
MEMORY_CAPACITY = get_kubernetes_query_expression('analytics.utilization.queries.MEMORY_CAPACITY')
MEMORY_CAPACITY_BY_NODE = get_kubernetes_query_expression('analytics.utilization.queries.MEMORY_CAPACITY_BY_NODE')
MEMORY_PRESSURE_NODES = get_kubernetes_query_expression('analytics.utilization.queries.MEMORY_PRESSURE_NODES')
MEMORY_PRESSURE_NODES_BY_NODE = get_kubernetes_query_expression(
    'analytics.utilization.queries.MEMORY_PRESSURE_NODES_BY_NODE'
)
MEMORY_USAGE = get_kubernetes_query_expression('analytics.utilization.queries.MEMORY_USAGE')
MEMORY_USAGE_BY_NODE = get_kubernetes_query_expression('analytics.utilization.queries.MEMORY_USAGE_BY_NODE')
MEMORY_UTILIZATION = get_kubernetes_query_expression('analytics.utilization.queries.MEMORY_UTILIZATION')
MEMORY_UTILIZATION_BY_NODE = get_kubernetes_query_expression('analytics.utilization.queries.MEMORY_UTILIZATION_BY_NODE')
NODE_LIST = get_kubernetes_query_expression('analytics.utilization.queries.NODE_LIST')
NOT_READY_NODES = get_kubernetes_query_expression('analytics.utilization.queries.NOT_READY_NODES')
PID_PRESSURE_NODES = get_kubernetes_query_expression('analytics.utilization.queries.PID_PRESSURE_NODES')
PID_PRESSURE_NODES_BY_NODE = get_kubernetes_query_expression('analytics.utilization.queries.PID_PRESSURE_NODES_BY_NODE')
POD_CAPACITY = get_kubernetes_query_expression('analytics.utilization.queries.POD_CAPACITY')
POD_CAPACITY_BY_NODE = get_kubernetes_query_expression('analytics.utilization.queries.POD_CAPACITY_BY_NODE')
POD_COUNT = get_kubernetes_query_expression('analytics.utilization.queries.POD_COUNT')
POD_COUNT_BY_NODE = get_kubernetes_query_expression('analytics.utilization.queries.POD_COUNT_BY_NODE')
POD_UTILIZATION = get_kubernetes_query_expression('analytics.utilization.queries.POD_UTILIZATION')
POD_UTILIZATION_BY_NODE = get_kubernetes_query_expression('analytics.utilization.queries.POD_UTILIZATION_BY_NODE')
READY_NODES = get_kubernetes_query_expression('analytics.utilization.queries.READY_NODES')
STORAGE_AVAILABLE = get_kubernetes_query_expression('analytics.utilization.queries.STORAGE_AVAILABLE')
STORAGE_AVAILABLE_BY_NODE = get_kubernetes_query_expression('analytics.utilization.queries.STORAGE_AVAILABLE_BY_NODE')
STORAGE_CAPACITY = get_kubernetes_query_expression('analytics.utilization.queries.STORAGE_CAPACITY')
STORAGE_CAPACITY_BY_NODE = get_kubernetes_query_expression('analytics.utilization.queries.STORAGE_CAPACITY_BY_NODE')
STORAGE_USAGE = get_kubernetes_query_expression('analytics.utilization.queries.STORAGE_USAGE')
STORAGE_USAGE_BY_NODE = get_kubernetes_query_expression('analytics.utilization.queries.STORAGE_USAGE_BY_NODE')
STORAGE_UTILIZATION = get_kubernetes_query_expression('analytics.utilization.queries.STORAGE_UTILIZATION')
STORAGE_UTILIZATION_BY_NODE = get_kubernetes_query_expression(
    'analytics.utilization.queries.STORAGE_UTILIZATION_BY_NODE'
)
TOP_CPU_CONSUMERS = get_kubernetes_query_expression('analytics.utilization.queries.TOP_CPU_CONSUMERS')
TOP_MEMORY_CONSUMERS = get_kubernetes_query_expression('analytics.utilization.queries.TOP_MEMORY_CONSUMERS')
TOTAL_NODES = get_kubernetes_query_expression('analytics.utilization.queries.TOTAL_NODES')
WORKER_NODES = get_kubernetes_query_expression('analytics.utilization.queries.WORKER_NODES')
WORKER_NODE_LIST = get_kubernetes_query_expression('analytics.utilization.queries.WORKER_NODE_LIST')


def get_utilization_clusters() -> list[Cluster]:
    return Cluster.query.order_by(
        Cluster.created_at.asc(),
        Cluster.id.asc(),
    ).all()


class UtilizationService:
    REQUIRED_CAPABILITIES = (
        'instant_query',
        'range_query',
        'kubernetes_identity',
        'utilization_metrics',
        'node_filesystem_identity',
    )

    def __init__(
        self,
        metrics_source: MetricsService,
    ) -> None:
        self.metrics_source = metrics_source
        consumer = metrics_source.consumer
        if consumer is None:
            raise ValueError('Utilization analytics requires a cluster-scoped Metrics Source service.')
        self.consumer: MetricsConsumer = consumer

    def requirements(self) -> ConsumerResult[dict[str, Any]]:
        return self.consumer.requirements(self.REQUIRED_CAPABILITIES)

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
            TypeError,
            ValueError,
        ):
            return 0.0

    def get_metrics_source_status(
        self,
    ) -> dict[str, Any]:
        status = self.consumer.analytics_status()
        payload = status.payload if isinstance(status.payload, dict) else {}
        response_time_ms = payload.get('response_time_ms')
        observation_degraded = bool(payload.get('observation_degraded'))
        if not status.ok:
            detail = (
                status.diagnostics[0].detail
                if status.diagnostics and status.diagnostics[0].detail
                else (status.diagnostics[0].message if status.diagnostics else 'Metrics Source is unavailable.')
            )
            return present_metrics_source_status(
                {
                    'configured': bool(payload.get('configured', True)),
                    'connected': False,
                    'response_time_ms': response_time_ms,
                    'last_checked_at': payload.get('last_checked_at'),
                    'error': detail,
                }
            )
        return present_metrics_source_status(
            {
                'configured': True,
                'connected': True,
                'response_time_ms': response_time_ms,
                'last_checked_at': payload.get('last_checked_at'),
                'observation_degraded': observation_degraded,
                'last_error': payload.get('last_error'),
            }
        )

    @staticmethod
    def _extract_consumers(
        response: dict[str, Any],
    ) -> list[dict[str, str | float]]:
        results = response.get(
            'data',
            {},
        ).get(
            'result',
            [],
        )

        consumers: list[dict[str, str | float]] = []

        for item in results:
            metric = item.get(
                'metric',
                {},
            )

            try:
                value = float(item['value'][1])
            except (
                KeyError,
                IndexError,
                TypeError,
                ValueError,
            ):
                value = 0.0

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
                    'value': value,
                }
            )

        return consumers

    @staticmethod
    def _extract_label_values(
        response: dict[str, Any],
        label_name: str,
    ) -> list[str]:
        results = response.get(
            'data',
            {},
        ).get(
            'result',
            [],
        )

        values = {
            item.get(
                'metric',
                {},
            ).get(
                label_name,
            )
            for item in results
        }

        return sorted(value for value in values if value)

    @staticmethod
    def _extract_series(
        response: dict[str, Any],
    ) -> list[dict[str, float]]:
        try:
            results = response['data']['result']

            if not results:
                return []

            values = results[0]['values']

            return [
                {
                    'timestamp': float(item[0]),
                    'value': float(item[1]),
                }
                for item in values
            ]

        except (
            KeyError,
            IndexError,
            TypeError,
            ValueError,
        ):
            return []

    @staticmethod
    def _escape_label_value(
        value: str,
    ) -> str:
        return value.replace(
            '\\',
            '\\\\',
        ).replace(
            '"',
            '\\"',
        )

    def _format_node_query(
        self,
        query_template: str,
        node_name: str | None = None,
    ) -> str:
        if not node_name:
            return query_template

        return query_template.replace(
            '{node}',
            self._escape_label_value(
                node_name,
            ),
        )

    def _query_series(
        self,
        query: str,
        hours: int = 1,
        step: str = '5m',
    ) -> list[dict[str, float]]:
        end = datetime.now(
            UTC,
        )

        start = end - timedelta(
            hours=hours,
        )

        response = self.consumer.query_range(
            query,
            start.isoformat(),
            end.isoformat(),
            step,
            required_capabilities=self.REQUIRED_CAPABILITIES,
        )

        return self._extract_series(
            response,
        )

    def _query_scalar(
        self,
        query: str,
    ) -> float:
        response = self.consumer.query(
            query,
            required_capabilities=self.REQUIRED_CAPABILITIES,
        )

        return round(
            self._extract_scalar(response),
            2,
        )

    @staticmethod
    def bytes_to_gib(
        value: int | float,
    ) -> float:
        return round(
            float(value) / 1024**3,
            2,
        )

    def get_cpu_capacity(
        self,
        node_name: str | None = None,
    ) -> float:
        query = CPU_CAPACITY

        if node_name:
            query = self._format_node_query(
                CPU_CAPACITY_BY_NODE,
                node_name,
            )

        return self._query_scalar(
            query,
        )

    def get_cpu_usage(
        self,
        node_name: str | None = None,
    ) -> float:
        query = CPU_USAGE

        if node_name:
            query = self._format_node_query(
                CPU_USAGE_BY_NODE,
                node_name,
            )

        return self._query_scalar(
            query,
        )

    def get_cpu_utilization(
        self,
        node_name: str | None = None,
    ) -> float:
        query = CPU_UTILIZATION

        if node_name:
            query = self._format_node_query(
                CPU_UTILIZATION_BY_NODE,
                node_name,
            )

        return self._query_scalar(
            query,
        )

    def get_memory_capacity(
        self,
        node_name: str | None = None,
    ) -> float:
        query = MEMORY_CAPACITY

        if node_name:
            query = self._format_node_query(
                MEMORY_CAPACITY_BY_NODE,
                node_name,
            )

        return self._query_scalar(
            query,
        )

    def get_memory_usage(
        self,
        node_name: str | None = None,
    ) -> float:
        query = MEMORY_USAGE

        if node_name:
            query = self._format_node_query(
                MEMORY_USAGE_BY_NODE,
                node_name,
            )

        return self._query_scalar(
            query,
        )

    def get_memory_utilization(
        self,
        node_name: str | None = None,
    ) -> float:
        query = MEMORY_UTILIZATION

        if node_name:
            query = self._format_node_query(
                MEMORY_UTILIZATION_BY_NODE,
                node_name,
            )

        return self._query_scalar(
            query,
        )

    def get_storage_capacity(
        self,
        node_name: str | None = None,
    ) -> float:
        query = STORAGE_CAPACITY

        if node_name:
            query = self._format_node_query(
                STORAGE_CAPACITY_BY_NODE,
                node_name,
            )

        return self._query_scalar(
            query,
        )

    def get_storage_available(
        self,
        node_name: str | None = None,
    ) -> float:
        query = STORAGE_AVAILABLE

        if node_name:
            query = self._format_node_query(
                STORAGE_AVAILABLE_BY_NODE,
                node_name,
            )

        return self._query_scalar(
            query,
        )

    def get_storage_usage(
        self,
        node_name: str | None = None,
    ) -> float:
        query = STORAGE_USAGE

        if node_name:
            query = self._format_node_query(
                STORAGE_USAGE_BY_NODE,
                node_name,
            )

        return self._query_scalar(
            query,
        )

    def get_storage_utilization(
        self,
        node_name: str | None = None,
    ) -> float:
        query = STORAGE_UTILIZATION

        if node_name:
            query = self._format_node_query(
                STORAGE_UTILIZATION_BY_NODE,
                node_name,
            )

        return self._query_scalar(
            query,
        )

    def get_pod_count(
        self,
        node_name: str | None = None,
    ) -> int:
        query = POD_COUNT

        if node_name:
            query = self._format_node_query(
                POD_COUNT_BY_NODE,
                node_name,
            )

        return int(
            self._query_scalar(
                query,
            )
        )

    def get_pod_capacity(
        self,
        node_name: str | None = None,
    ) -> int:
        query = POD_CAPACITY

        if node_name:
            query = self._format_node_query(
                POD_CAPACITY_BY_NODE,
                node_name,
            )

        return int(
            self._query_scalar(
                query,
            )
        )

    def get_pod_utilization(
        self,
        node_name: str | None = None,
    ) -> float:
        query = POD_UTILIZATION

        if node_name:
            query = self._format_node_query(
                POD_UTILIZATION_BY_NODE,
                node_name,
            )

        return self._query_scalar(
            query,
        )

    def get_total_nodes(
        self,
    ) -> int:
        return int(
            self._query_scalar(
                TOTAL_NODES,
            )
        )

    def get_ready_nodes(
        self,
    ) -> int:
        return int(
            self._query_scalar(
                READY_NODES,
            )
        )

    def get_not_ready_nodes(
        self,
    ) -> int:
        return int(
            self._query_scalar(
                NOT_READY_NODES,
            )
        )

    def get_master_nodes(
        self,
    ) -> int:
        return int(
            self._query_scalar(
                MASTER_NODES,
            )
        )

    def get_worker_nodes(
        self,
    ) -> int:
        return int(
            self._query_scalar(
                WORKER_NODES,
            )
        )

    def get_node_names(
        self,
    ) -> list[str]:
        response = self.consumer.query(
            NODE_LIST,
            required_capabilities=self.REQUIRED_CAPABILITIES,
        )

        return self._extract_label_values(
            response,
            'node',
        )

    def get_worker_node_names(
        self,
    ) -> list[str]:
        response = self.consumer.query(
            WORKER_NODE_LIST,
            required_capabilities=self.REQUIRED_CAPABILITIES,
        )

        return self._extract_label_values(
            response,
            'node',
        )

    def get_kubernetes_version(
        self,
    ) -> str:
        response = self.consumer.query(
            KUBERNETES_VERSION,
            required_capabilities=self.REQUIRED_CAPABILITIES,
        )

        try:
            result = response['data']['result']

            if not result:
                return '-'

            return result[0]['metric'].get(
                'git_version',
                '-',
            )

        except (
            KeyError,
            IndexError,
            TypeError,
        ):
            return '-'

    def get_cpu_trend(
        self,
        hours: int = 1,
        step: str = '5m',
        node_name: str | None = None,
    ) -> list[dict[str, float]]:
        query = CPU_UTILIZATION

        if node_name:
            query = self._format_node_query(
                CPU_UTILIZATION_BY_NODE,
                node_name,
            )

        return self._query_series(
            query,
            hours,
            step,
        )

    def get_memory_trend(
        self,
        hours: int = 1,
        step: str = '5m',
        node_name: str | None = None,
    ) -> list[dict[str, float]]:
        query = MEMORY_UTILIZATION

        if node_name:
            query = self._format_node_query(
                MEMORY_UTILIZATION_BY_NODE,
                node_name,
            )

        return self._query_series(
            query,
            hours,
            step,
        )

    def get_pod_trend(
        self,
        hours: int = 1,
        step: str = '5m',
        node_name: str | None = None,
    ) -> list[dict[str, float]]:
        query = POD_UTILIZATION

        if node_name:
            query = self._format_node_query(
                POD_UTILIZATION_BY_NODE,
                node_name,
            )

        return self._query_series(
            query,
            hours,
            step,
        )

    def get_trends(
        self,
        hours: int = 1,
        step: str = '5m',
        node_name: str | None = None,
    ) -> dict[str, list[dict[str, float]]]:
        return {
            'cpu': self.get_cpu_trend(
                hours,
                step,
                node_name,
            ),
            'memory': self.get_memory_trend(
                hours,
                step,
                node_name,
            ),
            'pods': self.get_pod_trend(
                hours,
                step,
                node_name,
            ),
        }

    def get_summary(
        self,
    ) -> dict[str, int | float]:
        storage_capacity = self.get_storage_capacity()
        storage_usage = self.get_storage_usage()
        storage_available = self.get_storage_available()

        return {
            'cpu_capacity': self.get_cpu_capacity(),
            'cpu_usage': self.get_cpu_usage(),
            'cpu_utilization': self.get_cpu_utilization(),
            'memory_capacity': self.get_memory_capacity(),
            'memory_usage': self.get_memory_usage(),
            'memory_utilization': self.get_memory_utilization(),
            'storage_capacity': storage_capacity,
            'storage_usage': storage_usage,
            'storage_available': storage_available,
            'storage_utilization': self.get_storage_utilization(),
            'storage_capacity_gib': self.bytes_to_gib(
                storage_capacity,
            ),
            'storage_usage_gib': self.bytes_to_gib(
                storage_usage,
            ),
            'storage_available_gib': self.bytes_to_gib(
                storage_available,
            ),
            'pod_count': self.get_pod_count(),
            'pod_capacity': self.get_pod_capacity(),
            'pod_utilization': self.get_pod_utilization(),
        }

    def get_detail_summary(
        self,
        node_name: str | None = None,
    ) -> dict[str, int | float | str | None]:
        storage_capacity = self.get_storage_capacity(
            node_name,
        )
        storage_usage = self.get_storage_usage(
            node_name,
        )
        storage_available = self.get_storage_available(
            node_name,
        )
        storage_utilization = self.get_storage_utilization(node_name)

        return {
            'node_name': node_name,
            'storage_scope': node_name or 'All canonical nodes',
            'cpu_capacity': self.get_cpu_capacity(
                node_name,
            ),
            'cpu_usage': self.get_cpu_usage(
                node_name,
            ),
            'cpu_utilization': self.get_cpu_utilization(
                node_name,
            ),
            'memory_capacity': self.get_memory_capacity(
                node_name,
            ),
            'memory_usage': self.get_memory_usage(
                node_name,
            ),
            'memory_utilization': self.get_memory_utilization(
                node_name,
            ),
            'storage_capacity': storage_capacity,
            'storage_usage': storage_usage,
            'storage_available': storage_available,
            'storage_utilization': storage_utilization,
            'storage_utilization_display': f'{storage_utilization:.2f}%',
            'storage_utilization_width': max(0.0, min(100.0, storage_utilization)),
            'storage_usage_summary': (
                f'{self.bytes_to_gib(storage_usage):.2f} GiB used from '
                f'{self.bytes_to_gib(storage_capacity):.2f} GiB capacity.'
            ),
            'storage_capacity_gib': self.bytes_to_gib(
                storage_capacity,
            ),
            'storage_usage_gib': self.bytes_to_gib(
                storage_usage,
            ),
            'storage_available_gib': self.bytes_to_gib(
                storage_available,
            ),
            'pod_count': self.get_pod_count(
                node_name,
            ),
            'pod_capacity': self.get_pod_capacity(
                node_name,
            ),
            'pod_utilization': self.get_pod_utilization(
                node_name,
            ),
        }

    def get_summary_table(
        self,
        summary: dict[str, int | float],
    ) -> list[dict[str, str | float]]:
        return [
            {
                'resource': 'CPU',
                'capacity': summary['cpu_capacity'],
                'usage': summary['cpu_usage'],
                'utilization': summary['cpu_utilization'],
                'scope': 'Worker nodes',
            },
            {
                'resource': 'Memory',
                'capacity': summary['memory_capacity'],
                'usage': summary['memory_usage'],
                'utilization': summary['memory_utilization'],
                'scope': 'Worker nodes',
            },
            {
                'resource': 'Disk /var or /',
                'capacity': summary['storage_capacity'],
                'usage': summary['storage_usage'],
                'utilization': summary['storage_utilization'],
                'scope': 'node_filesystem mountpoint=/var when available, otherwise mountpoint=/ for scraped instances',
            },
            {
                'resource': 'Pods',
                'capacity': summary['pod_capacity'],
                'usage': summary['pod_count'],
                'utilization': summary['pod_utilization'],
                'scope': 'Worker nodes',
            },
        ]

    def get_memory_pressure_nodes(
        self,
        node_name: str | None = None,
    ) -> int:
        query = MEMORY_PRESSURE_NODES

        if node_name:
            query = self._format_node_query(
                MEMORY_PRESSURE_NODES_BY_NODE,
                node_name,
            )

        return int(
            self._query_scalar(
                query,
            )
        )

    def get_disk_pressure_nodes(
        self,
        node_name: str | None = None,
    ) -> int:
        query = DISK_PRESSURE_NODES

        if node_name:
            query = self._format_node_query(
                DISK_PRESSURE_NODES_BY_NODE,
                node_name,
            )

        return int(
            self._query_scalar(
                query,
            )
        )

    def get_pid_pressure_nodes(
        self,
        node_name: str | None = None,
    ) -> int:
        query = PID_PRESSURE_NODES

        if node_name:
            query = self._format_node_query(
                PID_PRESSURE_NODES_BY_NODE,
                node_name,
            )

        return int(
            self._query_scalar(
                query,
            )
        )

    @staticmethod
    def _risk_from_utilization(
        utilization: float,
        *,
        evidence_available: bool = True,
    ) -> str:
        if not evidence_available:
            return 'Unknown'
        if utilization > 90:
            return 'Critical'
        if utilization >= 75:
            return 'Warning'
        return 'Normal'

    @staticmethod
    def _utilization_reason(
        utilization: float,
        *,
        evidence_available: bool = True,
    ) -> str:
        if not evidence_available:
            return 'Capacity evidence unavailable'
        return f'Utilization {utilization:.2f}%'

    @staticmethod
    def _pressure_reason(
        condition: str,
        pressure_nodes: int,
        node_name: str | None = None,
    ) -> str:
        if node_name:
            return f'{condition} detected on selected node'

        return f'{condition} detected on {pressure_nodes} node(s)'

    def get_capacity_pressure_risk(
        self,
        summary: dict[str, int | float],
        node_name: str | None = None,
    ) -> dict[str, dict[str, int | float | str]]:
        cpu_utilization = float(
            summary.get(
                'cpu_utilization',
                0,
            )
        )

        memory_utilization = float(
            summary.get(
                'memory_utilization',
                0,
            )
        )

        storage_utilization = float(
            summary.get(
                'storage_utilization',
                0,
            )
        )

        pod_utilization = float(
            summary.get(
                'pod_utilization',
                0,
            )
        )

        cpu_evidence = float(summary.get('cpu_capacity', 0) or 0) > 0
        memory_evidence = float(summary.get('memory_capacity', 0) or 0) > 0
        storage_evidence = float(summary.get('storage_capacity', 0) or 0) > 0
        pod_evidence = float(summary.get('pod_capacity', 0) or 0) > 0

        memory_pressure_nodes = self.get_memory_pressure_nodes(
            node_name,
        )
        disk_pressure_nodes = self.get_disk_pressure_nodes(
            node_name,
        )
        pid_pressure_nodes = self.get_pid_pressure_nodes(
            node_name,
        )

        memory_status = self._risk_from_utilization(
            memory_utilization,
            evidence_available=memory_evidence,
        )
        memory_reason = self._utilization_reason(
            memory_utilization,
            evidence_available=memory_evidence,
        )

        if memory_pressure_nodes > 0:
            memory_status = 'Critical'
            memory_reason = self._pressure_reason(
                'MemoryPressure',
                memory_pressure_nodes,
                node_name,
            )

        storage_status = self._risk_from_utilization(
            storage_utilization,
            evidence_available=storage_evidence,
        )
        storage_reason = self._utilization_reason(
            storage_utilization,
            evidence_available=storage_evidence,
        )

        if disk_pressure_nodes > 0:
            storage_status = 'Critical'
            storage_reason = self._pressure_reason(
                'DiskPressure',
                disk_pressure_nodes,
                node_name,
            )

        pod_status = self._risk_from_utilization(
            pod_utilization,
            evidence_available=pod_evidence,
        )
        pod_reason = self._utilization_reason(
            pod_utilization,
            evidence_available=pod_evidence,
        )

        if pid_pressure_nodes > 0:
            pod_status = 'Critical'
            pod_reason = self._pressure_reason(
                'PIDPressure',
                pid_pressure_nodes,
                node_name,
            )

        return {
            'cpu': {
                'status': self._risk_from_utilization(
                    cpu_utilization,
                    evidence_available=cpu_evidence,
                ),
                'reason': self._utilization_reason(
                    cpu_utilization,
                    evidence_available=cpu_evidence,
                ),
                'pressure_nodes': 0,
                'utilization': cpu_utilization,
            },
            'memory': {
                'status': memory_status,
                'reason': memory_reason,
                'pressure_nodes': memory_pressure_nodes,
                'utilization': memory_utilization,
            },
            'storage': {
                'status': storage_status,
                'reason': storage_reason,
                'pressure_nodes': disk_pressure_nodes,
                'utilization': storage_utilization,
            },
            'pods': {
                'status': pod_status,
                'reason': pod_reason,
                'pressure_nodes': pid_pressure_nodes,
                'utilization': pod_utilization,
            },
        }

    def get_top_cpu_consumers(
        self,
    ) -> list[dict[str, str | float]]:
        response = self.metrics_source.instant_query(
            TOP_CPU_CONSUMERS,
        )

        return self._extract_consumers(
            response,
        )

    def get_top_memory_consumers(
        self,
    ) -> list[dict[str, str | float]]:
        response = self.metrics_source.instant_query(
            TOP_MEMORY_CONSUMERS,
        )

        return self._extract_consumers(
            response,
        )

    def get_cluster_info(
        self,
        summary: dict[str, int | float],
    ) -> dict[str, int | float | str]:
        return {
            'kubernetes_version': self.get_kubernetes_version(),
            'total_nodes': self.get_total_nodes(),
            'ready_nodes': self.get_ready_nodes(),
            'not_ready_nodes': self.get_not_ready_nodes(),
            'worker_nodes': self.get_worker_nodes(),
            'master_nodes': self.get_master_nodes(),
            'cpu_capacity': summary['cpu_capacity'],
            'memory_capacity': summary['memory_capacity'],
            'pod_capacity': summary['pod_capacity'],
        }


def get_metrics_source_status_snapshot(
    cluster_id: str,
) -> dict[str, Any]:
    clusters = get_utilization_clusters()
    cluster = resolve_selected_cluster(clusters, cluster_id or '')
    if not cluster:
        return present_metrics_source_status(
            {
                'configured': False,
                'connected': False,
                'label': 'Waiting for Cluster',
            }
        )
    try:
        consumer = MetricsConsumer(cluster)
        response = consumer.analytics_status()
    except MetricsSourceError as exc:
        return present_metrics_source_status(
            {
                'configured': False,
                'connected': False,
                'error': str(exc),
            }
        )

    payload = response.payload if isinstance(response.payload, dict) else {}
    detail = None
    if not response.ok:
        diagnostic = response.diagnostics[0] if response.diagnostics else None
        detail = (
            diagnostic.detail
            if diagnostic is not None and diagnostic.detail
            else (diagnostic.message if diagnostic is not None else 'Metrics Source is unavailable.')
        )
    return present_metrics_source_status(
        {
            'configured': bool(payload.get('configured', True)),
            'connected': response.ok,
            'endpoint': getattr(consumer.config, 'endpoint', ''),
            'response_time_ms': payload.get('response_time_ms'),
            'last_checked_at': payload.get('last_checked_at'),
            'observation_degraded': bool(payload.get('observation_degraded')),
            'last_error': payload.get('last_error'),
            'error': detail,
        }
    )


def get_utilization_snapshot(
    cluster_id: str,
    time_range: str = '24h',
) -> dict[str, float | None] | None:
    _ = time_range
    from app.analytics.kubernetes.materialization.service import read_snapshot

    result = read_snapshot(
        cluster_id=cluster_id,
        dataset_key='analytics.utilization.summary',
        parameters={'cluster_id': str(cluster_id)},
    )
    summary = (result.context or {}).get('summary') if result.available else None
    if not isinstance(summary, dict):
        return None

    def percent(utilization_key: str, capacity_key: str) -> float | None:
        if capacity_key not in summary or safe_float(summary.get(capacity_key)) <= 0:
            return None
        return round(safe_float(summary.get(utilization_key)), 2)

    return {
        'cpu_percent': percent('cpu_utilization', 'cpu_capacity'),
        'memory_percent': percent('memory_utilization', 'memory_capacity'),
        'storage_percent': percent('storage_utilization', 'storage_capacity'),
        'pod_percent': percent('pod_utilization', 'pod_capacity'),
    }
