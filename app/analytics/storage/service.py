# app/analytics/storage/service.py

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.analytics.common.base_service import AnalyticsBaseService, raw_percent, safe_round
from app.analytics.common.coercion import (
    as_dict as _as_dict,
)
from app.analytics.common.coercion import (
    as_list as _as_list,
)
from app.analytics.common.coercion import (
    safe_float as _safe_float,
)
from app.analytics.common.coercion import (
    safe_int as _safe_int,
)
from app.analytics.common.context import build_analysis_utilization_context
from app.analytics.common.params import (
    ALLOWED_PER_PAGE_VALUES,
    get_allowed_time_ranges,
    get_per_page_arg,
    get_positive_int_arg,
    get_query_value,
    get_selected_time_range,
)
from app.analytics.common.payloads import get_empty_storage_payload
from app.analytics.utilization.service import UtilizationService
from app.common.dependencies import prometheus_capability_blocker, prometheus_connection_blocker
from app.integrations.prometheus.capabilities import definition as capability_definition
from app.integrations.prometheus.exceptions import PrometheusError
from app.integrations.prometheus.query_profiles import get_query_expression
from app.intelligence.recommendation_engine import (
    build_storage_actionable_recommendations,
    count_actionable_recommendations,
    format_recommendation_cards,
)
from app.prometheus.consumer import PrometheusConsumer

NAMESPACE_ACTIVE_QUERY = get_query_expression('analytics.storage.queries.NAMESPACE_ACTIVE_QUERY')
NODE_ROOT_FILESYSTEM_AVAILABLE_QUERY = get_query_expression(
    'analytics.storage.queries.NODE_ROOT_FILESYSTEM_AVAILABLE_QUERY'
)
NODE_ROOT_FILESYSTEM_SIZE_QUERY = get_query_expression('analytics.storage.queries.NODE_ROOT_FILESYSTEM_SIZE_QUERY')
NODE_VAR_FILESYSTEM_AVAILABLE_QUERY = get_query_expression(
    'analytics.storage.queries.NODE_VAR_FILESYSTEM_AVAILABLE_QUERY'
)
NODE_VAR_FILESYSTEM_SIZE_QUERY = get_query_expression('analytics.storage.queries.NODE_VAR_FILESYSTEM_SIZE_QUERY')
PVC_AVAILABLE_BY_CLAIM_QUERY = get_query_expression('analytics.storage.queries.PVC_AVAILABLE_BY_CLAIM_QUERY')
PVC_AVAILABLE_TOTAL_QUERY = get_query_expression('analytics.storage.queries.PVC_AVAILABLE_TOTAL_QUERY')
PVC_COUNT_QUERY = get_query_expression('analytics.storage.queries.PVC_COUNT_QUERY')
PVC_INFO_QUERY = get_query_expression('analytics.storage.queries.PVC_INFO_QUERY')
PVC_REQUESTED_BY_CLAIM_QUERY = get_query_expression('analytics.storage.queries.PVC_REQUESTED_BY_CLAIM_QUERY')
PVC_REQUESTED_TOTAL_QUERY = get_query_expression('analytics.storage.queries.PVC_REQUESTED_TOTAL_QUERY')
PVC_STATUS_BY_CLAIM_QUERY = get_query_expression('analytics.storage.queries.PVC_STATUS_BY_CLAIM_QUERY')
PVC_USED_BY_CLAIM_QUERY = get_query_expression('analytics.storage.queries.PVC_USED_BY_CLAIM_QUERY')
PVC_USED_TOTAL_QUERY = get_query_expression('analytics.storage.queries.PVC_USED_TOTAL_QUERY')
PV_CAPACITY_BY_VOLUME_QUERY = get_query_expression('analytics.storage.queries.PV_CAPACITY_BY_VOLUME_QUERY')
PV_CAPACITY_QUERY = get_query_expression('analytics.storage.queries.PV_CAPACITY_QUERY')
PV_COUNT_QUERY = get_query_expression('analytics.storage.queries.PV_COUNT_QUERY')
PV_INFO_QUERY = get_query_expression('analytics.storage.queries.PV_INFO_QUERY')
PV_RECLAIM_POLICY_QUERY = get_query_expression('analytics.storage.queries.PV_RECLAIM_POLICY_QUERY')
PV_STATUS_BY_VOLUME_QUERY = get_query_expression('analytics.storage.queries.PV_STATUS_BY_VOLUME_QUERY')


def get_selected_storage_tab(
    query_args: Mapping[str, Any],
) -> str:
    selected_storage_tab = get_query_value(
        query_args=query_args,
        name='storage_tab',
        default='pvc',
    )

    if selected_storage_tab not in [
        'pvc',
        'pv',
    ]:
        return 'pvc'

    return selected_storage_tab


def get_empty_storage_recommendation_context() -> dict[str, Any]:
    return {
        'actionable_recommendations': [],
        'recommendation_cards': [],
        'recommendation_count': 0,
    }


def build_storage_recommendation_context(
    storage_summary: dict[str, Any],
) -> dict[str, Any]:
    actionable_recommendations = build_storage_actionable_recommendations(
        {
            'storage_summary': storage_summary,
        }
    )

    return {
        'actionable_recommendations': actionable_recommendations,
        'recommendation_cards': format_recommendation_cards(
            actionable_recommendations,
        ),
        'recommendation_count': count_actionable_recommendations(
            actionable_recommendations,
        ),
    }


class StorageAnalysisService(AnalyticsBaseService):
    REQUIRED_CAPABILITIES = (
        'instant_query',
        'kubernetes_identity',
        'pvc_usage',
        'node_filesystem_identity',
    )
    CANONICAL_NODE_LABELS = (
        'node',
        'nodename',
        'kubernetes_node',
    )

    def __init__(
        self,
        utilization_service: UtilizationService,
        consumer: PrometheusConsumer,
    ) -> None:
        self.utilization_service = utilization_service
        self.consumer = consumer

    def get_prometheus_result(
        self,
        query: str,
    ) -> list[dict[str, Any]]:
        response = self.consumer.query(
            query,
            required_capabilities=self.REQUIRED_CAPABILITIES,
        )
        data = response.get('data', {}) if isinstance(response, dict) else {}
        result = data.get('result', []) if isinstance(data, dict) else []
        return [item for item in result if isinstance(item, dict)]

    def get_filesystem_vector_map(
        self,
        query: str,
    ) -> dict[str, float]:
        values: dict[str, float] = {}
        for item in self.get_prometheus_result(query):
            metric = item.get('metric', {})
            if not isinstance(metric, dict):
                continue
            node = next(
                (
                    str(metric.get(label, '')).strip()
                    for label in self.CANONICAL_NODE_LABELS
                    if str(metric.get(label, '')).strip()
                ),
                '',
            )
            if not node:
                continue
            values[node] = values.get(node, 0.0) + self.extract_value(item)
        return values

    def paginate_rows(
        self,
        rows: list[dict[str, Any]],
        page: int,
        per_page: int,
    ) -> dict[str, Any]:
        return self.paginate_rows_with_options(
            rows=rows,
            page=page,
            per_page=per_page,
            allowed_per_page=ALLOWED_PER_PAGE_VALUES,
            default_per_page=5,
        )

    def get_storage_namespace_options(
        self,
    ) -> list[str]:
        active_namespaces = self.get_prometheus_vector_map(
            query=NAMESPACE_ACTIVE_QUERY,
            label='namespace',
        )

        pvc_requested = self.get_prometheus_vector_map(
            query=PVC_REQUESTED_BY_CLAIM_QUERY,
            label='persistentvolumeclaim',
            secondary_label='namespace',
        )

        namespaces = set(
            active_namespaces.keys(),
        )

        for key in pvc_requested:
            namespace, _ = self.split_composite_key(
                key,
            )

            if namespace:
                namespaces.add(
                    namespace,
                )

        return sorted(namespace for namespace in namespaces if namespace)

    def filter_storage_rows(
        self,
        rows: list[dict[str, Any]],
        selected_search: str = '',
        selected_status: str = '',
        selected_storage_class: str = '',
    ) -> list[dict[str, Any]]:
        filtered_rows: list[dict[str, Any]] = []

        for row in rows:
            if selected_search:
                haystack = ' '.join(
                    str(
                        row.get(
                            key,
                            '',
                        )
                    )
                    for key in [
                        'name',
                        'namespace',
                        'claim',
                    ]
                ).lower()

                if selected_search.lower() not in haystack:
                    continue

            if (
                selected_status
                and row.get(
                    'status',
                )
                != selected_status
            ):
                continue

            if (
                selected_storage_class
                and row.get(
                    'storage_class',
                )
                != selected_storage_class
            ):
                continue

            filtered_rows.append(
                row,
            )

        return filtered_rows

    def get_unique_options(
        self,
        rows: list[dict[str, Any]],
        key: str,
    ) -> list[str]:
        values = {
            str(
                row.get(
                    key,
                    '',
                )
            )
            for row in rows
            if row.get(
                key,
            )
        }

        return sorted(
            values,
        )

    def get_storage_capacity_summary(
        self,
        selected_namespace: str,
        selected_node: str,
        selected_pvc_search: str = '',
        selected_pvc_status: str = '',
        selected_pvc_storage_class: str = '',
        pvc_page: int = 1,
        pvc_per_page: int = 5,
        selected_pv_search: str = '',
        selected_pv_status: str = '',
        selected_pv_storage_class: str = '',
        pv_page: int = 1,
        pv_per_page: int = 5,
    ) -> dict[str, Any]:
        node_var_size = self.get_filesystem_vector_map(
            NODE_VAR_FILESYSTEM_SIZE_QUERY,
        )

        node_var_available = self.get_filesystem_vector_map(
            NODE_VAR_FILESYSTEM_AVAILABLE_QUERY,
        )

        node_root_size = self.get_filesystem_vector_map(
            NODE_ROOT_FILESYSTEM_SIZE_QUERY,
        )

        node_root_available = self.get_filesystem_vector_map(
            NODE_ROOT_FILESYSTEM_AVAILABLE_QUERY,
        )

        node_size: dict[str, float] = {}
        node_available: dict[str, float] = {}
        node_mountpoint: dict[str, str] = {}

        for node, size in node_root_size.items():
            node_size[node] = size
            node_available[node] = node_root_available.get(
                node,
                0,
            )
            node_mountpoint[node] = '/'

        for node, size in node_var_size.items():
            node_size[node] = size
            node_available[node] = node_var_available.get(
                node,
                0,
            )
            node_mountpoint[node] = '/var'

        node_rows: list[dict[str, Any]] = []

        for node, size in sorted(
            node_size.items(),
        ):
            if selected_node and node != selected_node:
                continue

            available = node_available.get(
                node,
                0,
            )

            used = max(
                _safe_float(size) - _safe_float(available),
                0.0,
            )

            usage_percent = raw_percent(
                used,
                size,
            )

            node_rows.append(
                {
                    'node': node,
                    'mountpoint': node_mountpoint.get(
                        node,
                        '/',
                    ),
                    'capacity': self.format_bytes(
                        size,
                    ),
                    'used': self.format_bytes(
                        used,
                    ),
                    'free': self.format_bytes(
                        available,
                    ),
                    'usage_percent': safe_round(
                        usage_percent,
                        1,
                    ),
                    'risk': self.get_usage_risk(
                        usage_percent,
                    ),
                    'capacity_bytes': size,
                    'used_bytes': used,
                    'free_bytes': available,
                }
            )

        total_capacity = sum(_safe_float(row.get('capacity_bytes', 0)) for row in node_rows)
        total_used = sum(_safe_float(row.get('used_bytes', 0)) for row in node_rows)
        total_free = sum(_safe_float(row.get('free_bytes', 0)) for row in node_rows)

        highest_row = max(
            node_rows,
            key=lambda row: _safe_float(row.get('usage_percent', 0)),
            default=None,
        )

        pvc_requested = self.get_prometheus_scalar(
            PVC_REQUESTED_TOTAL_QUERY,
        )

        pvc_used = self.get_prometheus_scalar(
            PVC_USED_TOTAL_QUERY,
        )

        pvc_free = self.get_prometheus_scalar(
            PVC_AVAILABLE_TOTAL_QUERY,
        )

        if selected_namespace:
            pvc_requested_by_claim = self.get_prometheus_vector_map(
                query=PVC_REQUESTED_BY_CLAIM_QUERY,
                label='persistentvolumeclaim',
                secondary_label='namespace',
            )

            pvc_used_by_claim = self.get_prometheus_vector_map(
                query=PVC_USED_BY_CLAIM_QUERY,
                label='persistentvolumeclaim',
                secondary_label='namespace',
            )

            pvc_available_by_claim = self.get_prometheus_vector_map(
                query=PVC_AVAILABLE_BY_CLAIM_QUERY,
                label='persistentvolumeclaim',
                secondary_label='namespace',
            )

            pvc_requested = sum(
                value
                for key, value in pvc_requested_by_claim.items()
                if key.startswith(
                    f'{selected_namespace}/',
                )
            )

            pvc_used = sum(
                value
                for key, value in pvc_used_by_claim.items()
                if key.startswith(
                    f'{selected_namespace}/',
                )
            )

            pvc_free = sum(
                value
                for key, value in pvc_available_by_claim.items()
                if key.startswith(
                    f'{selected_namespace}/',
                )
            )

        pv_capacity = self.get_prometheus_scalar(
            PV_CAPACITY_QUERY,
        )

        pv_count = self.get_prometheus_scalar(
            PV_COUNT_QUERY,
        )

        pvc_count = self.get_prometheus_scalar(
            PVC_COUNT_QUERY,
        )

        pvc_all_rows = self.get_pvc_detail_rows(
            selected_namespace=selected_namespace,
        )

        pvc_status_options = self.get_unique_options(
            rows=pvc_all_rows,
            key='status',
        )

        pvc_storage_class_options = self.get_unique_options(
            rows=pvc_all_rows,
            key='storage_class',
        )

        pvc_filtered_rows = self.filter_storage_rows(
            rows=pvc_all_rows,
            selected_search=selected_pvc_search,
            selected_status=selected_pvc_status,
            selected_storage_class=selected_pvc_storage_class,
        )

        pvc_page_payload = self.paginate_rows(
            rows=pvc_filtered_rows,
            page=pvc_page,
            per_page=pvc_per_page,
        )

        pv_all_rows = self.get_pv_detail_rows()

        pv_status_options = self.get_unique_options(
            rows=pv_all_rows,
            key='status',
        )

        pv_storage_class_options = self.get_unique_options(
            rows=pv_all_rows,
            key='storage_class',
        )

        pv_filtered_rows = self.filter_storage_rows(
            rows=pv_all_rows,
            selected_search=selected_pv_search,
            selected_status=selected_pv_status,
            selected_storage_class=selected_pv_storage_class,
        )

        pv_page_payload = self.paginate_rows(
            rows=pv_filtered_rows,
            page=pv_page,
            per_page=pv_per_page,
        )

        return {
            'node_filesystem': {
                'selected_node': selected_node,
                'available_nodes': sorted(
                    node_size.keys(),
                ),
                'summary': {
                    'capacity': self.format_bytes(
                        total_capacity,
                    ),
                    'used': self.format_bytes(
                        total_used,
                    ),
                    'free': self.format_bytes(
                        total_free,
                    ),
                    'usage_percent': safe_round(
                        raw_percent(
                            total_used,
                            total_capacity,
                        ),
                        1,
                    ),
                    'free_percent': safe_round(
                        raw_percent(
                            total_free,
                            total_capacity,
                        ),
                        1,
                    ),
                    'highest_usage': _safe_float(highest_row.get('usage_percent', 0)) if highest_row else 0.0,
                    'highest_node': str(highest_row.get('node', '-') or '-') if highest_row else '-',
                },
                'rows': node_rows,
            },
            'persistent_storage': {
                'pv': {
                    'count': int(
                        pv_count,
                    ),
                    'capacity': self.format_bytes(
                        pv_capacity,
                    ),
                    'used': self.format_bytes(
                        pvc_used,
                    ),
                    'free': self.format_bytes(
                        pvc_free,
                    ),
                    'used_percent': safe_round(
                        raw_percent(
                            pvc_used,
                            pv_capacity,
                        ),
                        1,
                    ),
                    'free_percent': safe_round(
                        raw_percent(
                            pvc_free,
                            pv_capacity,
                        ),
                        1,
                    ),
                },
                'pvc': {
                    'count': int(
                        pvc_count,
                    ),
                    'requested': self.format_bytes(
                        pvc_requested,
                    ),
                    'used': self.format_bytes(
                        pvc_used,
                    ),
                    'free': self.format_bytes(
                        pvc_free,
                    ),
                    'used_percent': safe_round(
                        raw_percent(
                            pvc_used,
                            pvc_requested,
                        ),
                        1,
                    ),
                    'free_percent': safe_round(
                        raw_percent(
                            pvc_free,
                            pvc_requested,
                        ),
                        1,
                    ),
                },
                'pvc_all_rows': pvc_all_rows,
                'pvc_rows': pvc_page_payload['rows'],
                'pvc_pagination': pvc_page_payload['pagination'],
                'pvc_selected_search': selected_pvc_search,
                'pvc_status_options': pvc_status_options,
                'pvc_storage_class_options': pvc_storage_class_options,
                'pvc_selected_status': selected_pvc_status,
                'pvc_selected_storage_class': selected_pvc_storage_class,
                'pv_all_rows': pv_all_rows,
                'pv_rows': pv_page_payload['rows'],
                'pv_pagination': pv_page_payload['pagination'],
                'pv_selected_search': selected_pv_search,
                'pv_status_options': pv_status_options,
                'pv_storage_class_options': pv_storage_class_options,
                'pv_selected_status': selected_pv_status,
                'pv_selected_storage_class': selected_pv_storage_class,
            },
        }

    def get_pv_reclaim_policy_map(
        self,
    ) -> dict[str, str]:
        result = self.get_prometheus_result(
            PV_RECLAIM_POLICY_QUERY,
        )

        values: dict[str, str] = {}

        for item in result:
            metric = item.get(
                'metric',
                {},
            )

            if not isinstance(
                metric,
                dict,
            ):
                continue

            volume = metric.get(
                'persistentvolume',
                '',
            )

            reclaim_policy = metric.get(
                'reclaim_policy',
                '',
            )

            if not reclaim_policy:
                reclaim_policy = metric.get(
                    'reclaimpolicy',
                    '',
                )

            if (
                not isinstance(
                    volume,
                    str,
                )
                or not volume
                or not isinstance(
                    reclaim_policy,
                    str,
                )
                or not reclaim_policy
            ):
                continue

            value = self.extract_value(
                item,
            )

            if value == 1:
                values[volume] = reclaim_policy

        return values

    def get_pv_claim_map(
        self,
    ) -> dict[str, str]:
        result = self.get_prometheus_result(
            PVC_INFO_QUERY,
        )

        values: dict[str, str] = {}

        for item in result:
            metric = item.get(
                'metric',
                {},
            )

            if not isinstance(
                metric,
                dict,
            ):
                continue

            namespace = metric.get(
                'namespace',
                '',
            )

            pvc_name = metric.get(
                'persistentvolumeclaim',
                '',
            )

            volume_name = metric.get(
                'volumename',
                '',
            )

            if (
                not isinstance(
                    namespace,
                    str,
                )
                or not namespace
                or not isinstance(
                    pvc_name,
                    str,
                )
                or not pvc_name
                or not isinstance(
                    volume_name,
                    str,
                )
                or not volume_name
            ):
                continue

            values[volume_name] = f'{namespace}/{pvc_name}'

        return values

    def get_pvc_risk(
        self,
        status: str,
        usage_percent: float,
    ) -> dict[str, str]:
        if status == 'Pending':
            return {
                'label': 'Warning',
                'class': 'bg-amber-100 text-amber-700',
            }

        if status == 'Lost':
            return {
                'label': 'Critical',
                'class': 'bg-red-100 text-red-700',
            }

        if usage_percent >= 90:
            return {
                'label': 'Critical',
                'class': 'bg-red-100 text-red-700',
            }

        if usage_percent >= 75:
            return {
                'label': 'High',
                'class': 'bg-orange-100 text-orange-700',
            }

        return {
            'label': 'Healthy',
            'class': 'bg-emerald-100 text-emerald-700',
        }

    def get_pvc_status_map(
        self,
    ) -> dict[str, str]:
        result = self.get_prometheus_result(
            PVC_STATUS_BY_CLAIM_QUERY,
        )

        values: dict[str, str] = {}

        for item in result:
            metric = item.get(
                'metric',
                {},
            )

            if not isinstance(
                metric,
                dict,
            ):
                continue

            namespace = metric.get(
                'namespace',
                '',
            )

            pvc_name = metric.get(
                'persistentvolumeclaim',
                '',
            )

            phase = metric.get(
                'phase',
                '',
            )

            if (
                not isinstance(
                    namespace,
                    str,
                )
                or not namespace
                or not isinstance(
                    pvc_name,
                    str,
                )
                or not pvc_name
                or not isinstance(
                    phase,
                    str,
                )
                or not phase
            ):
                continue

            value = self.extract_value(
                item,
            )

            if value == 1:
                values[f'{namespace}/{pvc_name}'] = phase

        return values

    def get_pvc_detail_rows(
        self,
        selected_namespace: str,
    ) -> list[dict[str, Any]]:
        requested = self.get_prometheus_vector_map(
            query=PVC_REQUESTED_BY_CLAIM_QUERY,
            label='persistentvolumeclaim',
            secondary_label='namespace',
        )

        used = self.get_prometheus_vector_map(
            query=PVC_USED_BY_CLAIM_QUERY,
            label='persistentvolumeclaim',
            secondary_label='namespace',
        )

        available = self.get_prometheus_vector_map(
            query=PVC_AVAILABLE_BY_CLAIM_QUERY,
            label='persistentvolumeclaim',
            secondary_label='namespace',
        )

        storage_classes = self.get_prometheus_label_map(
            query=PVC_INFO_QUERY,
            key_label='persistentvolumeclaim',
            value_label='storageclass',
            secondary_key_label='namespace',
        )

        status_map = self.get_pvc_status_map()

        keys = set(
            requested.keys(),
        )

        keys.update(
            used.keys(),
        )

        rows: list[dict[str, Any]] = []

        for key in sorted(
            keys,
        ):
            namespace, pvc_name = self.split_composite_key(
                key,
            )

            if selected_namespace and namespace != selected_namespace:
                continue

            requested_value = requested.get(
                key,
                0,
            )

            used_value = used.get(
                key,
                0,
            )

            free_value = available.get(
                key,
                0,
            )

            status = status_map.get(
                key,
                'Unknown',
            )

            usage_percent = raw_percent(
                used_value,
                requested_value,
            )

            rows.append(
                {
                    'name': pvc_name,
                    'namespace': namespace,
                    'status': status,
                    'storage_class': storage_classes.get(
                        key,
                        'No StorageClass',
                    ),
                    'requested': self.format_bytes(
                        requested_value,
                    ),
                    'used': self.format_bytes(
                        used_value,
                    ),
                    'free': self.format_bytes(
                        free_value,
                    ),
                    'requested_bytes': requested_value,
                    'used_bytes': used_value,
                    'free_bytes': free_value,
                    'usage_percent': safe_round(
                        usage_percent,
                        1,
                    ),
                    'risk': self.get_pvc_risk(
                        status=status,
                        usage_percent=usage_percent,
                    ),
                }
            )

        return rows

    def get_pv_detail_rows(
        self,
    ) -> list[dict[str, Any]]:
        capacities = self.get_prometheus_vector_map(
            query=PV_CAPACITY_BY_VOLUME_QUERY,
            label='persistentvolume',
        )

        storage_classes = self.get_prometheus_label_map(
            query=PV_INFO_QUERY,
            key_label='persistentvolume',
            value_label='storageclass',
        )

        claim_map = self.get_pv_claim_map()

        reclaim_policies = self.get_pv_reclaim_policy_map()

        status_map = self.get_pv_status_map()

        rows: list[dict[str, Any]] = []

        for volume, capacity in sorted(
            capacities.items(),
        ):
            status = status_map.get(
                volume,
                'Unknown',
            )

            rows.append(
                {
                    'name': volume,
                    'status': status,
                    'capacity': self.format_bytes(
                        capacity,
                    ),
                    'capacity_bytes': capacity,
                    'storage_class': storage_classes.get(
                        volume,
                        'No StorageClass',
                    ),
                    'claim': claim_map.get(
                        volume,
                        '-',
                    ),
                    'reclaim_policy': reclaim_policies.get(
                        volume,
                        '-',
                    ),
                    'risk': self.get_pv_risk(
                        status,
                    ),
                }
            )

        return rows

    def get_pv_risk(
        self,
        status: str,
    ) -> dict[str, str]:
        if status == 'Bound':
            return {
                'label': 'Healthy',
                'class': 'bg-emerald-100 text-emerald-700',
            }

        if status in [
            'Available',
            'Released',
        ]:
            return {
                'label': 'Watch',
                'class': 'bg-amber-100 text-amber-700',
            }

        if status == 'Failed':
            return {
                'label': 'Critical',
                'class': 'bg-red-100 text-red-700',
            }

        return {
            'label': 'Unknown',
            'class': 'bg-slate-100 text-slate-700',
        }

    def get_pv_status_map(
        self,
    ) -> dict[str, str]:
        result = self.get_prometheus_result(
            PV_STATUS_BY_VOLUME_QUERY,
        )

        values: dict[str, str] = {}

        for item in result:
            metric = item.get(
                'metric',
                {},
            )

            if not isinstance(
                metric,
                dict,
            ):
                continue

            volume = metric.get(
                'persistentvolume',
                '',
            )

            phase = metric.get(
                'phase',
                '',
            )

            if (
                not isinstance(
                    volume,
                    str,
                )
                or not volume
                or not isinstance(
                    phase,
                    str,
                )
                or not phase
            ):
                continue

            value = self.extract_value(
                item,
            )

            if value == 1:
                values[volume] = phase

        return values

    def get_usage_risk(
        self,
        percent: float,
    ) -> dict[str, str]:
        if percent >= 90:
            return {
                'label': 'Critical',
                'class': 'bg-red-100 text-red-700',
            }

        if percent >= 75:
            return {
                'label': 'High',
                'class': 'bg-orange-100 text-orange-700',
            }

        if percent >= 60:
            return {
                'label': 'Watch',
                'class': 'bg-amber-100 text-amber-700',
            }

        return {
            'label': 'Healthy',
            'class': 'bg-emerald-100 text-emerald-700',
        }


def get_storage_analysis_context(
    query_args: Mapping[str, Any],
) -> dict[str, Any]:
    _, cluster, utilization_service, context = build_analysis_utilization_context(
        query_args=query_args,
    )

    selected_namespace = get_query_value(
        query_args=query_args,
        name='namespace',
        default='',
    )
    selected_time_range = get_selected_time_range(
        query_args=query_args,
    )
    selected_storage_node = get_query_value(
        query_args=query_args,
        name='storage_node',
        default='',
    )
    selected_storage_tab = get_selected_storage_tab(
        query_args=query_args,
    )
    selected_pvc_search = get_query_value(
        query_args=query_args,
        name='pvc_search',
        default='',
    )
    selected_pvc_status = get_query_value(
        query_args=query_args,
        name='pvc_status',
        default='',
    )
    selected_pvc_storage_class = get_query_value(
        query_args=query_args,
        name='pvc_storage_class',
        default='',
    )
    selected_pv_search = get_query_value(
        query_args=query_args,
        name='pv_search',
        default='',
    )
    selected_pv_status = get_query_value(
        query_args=query_args,
        name='pv_status',
        default='',
    )
    selected_pv_storage_class = get_query_value(
        query_args=query_args,
        name='pv_storage_class',
        default='',
    )

    context.update(
        {
            'selected_namespace': selected_namespace,
            'selected_time_range': selected_time_range,
            'selected_storage_node': selected_storage_node,
            'selected_storage_tab': selected_storage_tab,
            'selected_pvc_search': selected_pvc_search,
            'selected_pvc_status': selected_pvc_status,
            'selected_pvc_storage_class': selected_pvc_storage_class,
            'selected_pv_search': selected_pv_search,
            'selected_pv_status': selected_pv_status,
            'selected_pv_storage_class': selected_pv_storage_class,
            'allowed_time_ranges': get_allowed_time_ranges(),
            'namespace_options': [],
        }
    )

    def apply_empty_payload() -> None:
        context.update(
            get_empty_storage_payload(
                selected_namespace=selected_namespace,
                selected_time_range=selected_time_range,
            )
        )
        context.update(
            get_empty_storage_recommendation_context(),
        )

    if utilization_service is None or cluster is None:
        apply_empty_payload()
        return context

    consumer = PrometheusConsumer(cluster)
    storage_service = StorageAnalysisService(
        utilization_service,
        consumer,
    )

    requirements = consumer.requirements(
        StorageAnalysisService.REQUIRED_CAPABILITIES,
    )
    if not requirements.ok:
        missing_keys = requirements.payload.get('missing_capabilities', [])
        capability_labels = []
        for key in missing_keys:
            item = capability_definition(str(key))
            capability_labels.append(item.label if item else str(key))
        context['dependency_blocker'] = prometheus_capability_blocker(
            cluster,
            capability_labels=capability_labels,
        )
        context['storage_capability_contract'] = {
            'required': list(StorageAnalysisService.REQUIRED_CAPABILITIES),
            'missing': list(missing_keys),
            'source': requirements.source,
        }
        apply_empty_payload()
        return context

    try:
        prometheus_status = storage_service.get_prometheus_status()
    except (PrometheusError, Exception) as exc:
        prometheus_status = {
            'connected': False,
            'label': 'Prometheus Unavailable',
            'response_time_ms': None,
            'description': str(exc),
            'error': str(exc),
        }

    context['prometheus_status'] = prometheus_status
    context['prometheus_connected'] = bool(
        prometheus_status.get(
            'connected',
            False,
        )
    )

    if not context['prometheus_connected']:
        context['dependency_blocker'] = prometheus_connection_blocker(
            cluster,
            detail=str(prometheus_status.get('error') or prometheus_status.get('description') or ''),
        )
        apply_empty_payload()
        return context

    try:
        storage_summary = storage_service.get_storage_capacity_summary(
            selected_namespace=selected_namespace,
            selected_node=selected_storage_node,
            selected_pvc_search=selected_pvc_search,
            selected_pvc_status=selected_pvc_status,
            selected_pvc_storage_class=selected_pvc_storage_class,
            pvc_page=get_positive_int_arg(
                query_args=query_args,
                name='pvc_page',
                default=1,
            ),
            pvc_per_page=get_per_page_arg(
                query_args=query_args,
                name='pvc_per_page',
                default=5,
            ),
            selected_pv_search=selected_pv_search,
            selected_pv_status=selected_pv_status,
            selected_pv_storage_class=selected_pv_storage_class,
            pv_page=get_positive_int_arg(
                query_args=query_args,
                name='pv_page',
                default=1,
            ),
            pv_per_page=get_per_page_arg(
                query_args=query_args,
                name='pv_per_page',
                default=5,
            ),
        )
        namespace_options = storage_service.get_storage_namespace_options()
    except (PrometheusError, Exception) as exc:
        context['dependency_blocker'] = prometheus_connection_blocker(
            cluster,
            detail=str(exc),
        )
        apply_empty_payload()
        return context

    context.update(
        {
            'storage_summary': storage_summary,
            'namespace_options': namespace_options,
        }
    )
    context.update(
        build_storage_recommendation_context(
            storage_summary,
        )
    )

    return context


def get_storage_snapshot(
    cluster_id: str,
) -> dict[str, Any]:
    from app.analytics.materialization.service import read_snapshot

    result = read_snapshot(
        cluster_id=cluster_id,
        dataset_key='analytics.storage',
        parameters={'cluster_id': str(cluster_id)},
    )
    context = result.context or {}
    storage_summary = _as_dict(context.get('storage_summary', {}))
    persistent_storage = _as_dict(storage_summary.get('persistent_storage', {}))
    pvc_summary = _as_dict(persistent_storage.get('pvc', {}))
    pvc_rows = _as_list(persistent_storage.get('pvc_all_rows') or persistent_storage.get('pvc_rows', []))
    if not storage_summary:
        return _empty_storage_snapshot()
    risk_count = _count_pvc_risks(pvc_rows)
    used_percent = _safe_int(pvc_summary.get('used_percent', 0))
    return {
        'pvc_requested': str(pvc_summary.get('requested', '0 GiB')),
        'pvc_used': str(pvc_summary.get('used', '0 GiB')),
        'pvc_free': str(pvc_summary.get('free', '0 GiB')),
        'pvc_risk_count': risk_count,
        'used_percent': used_percent,
        'free_percent': max(0, 100 - used_percent),
        'top_namespace': _get_top_storage_namespace(pvc_rows),
        'recommendation_count': count_actionable_recommendations(
            context.get('actionable_recommendations')
            if isinstance(context.get('actionable_recommendations'), list)
            else []
        ),
    }

def _empty_storage_snapshot() -> dict[str, Any]:
    return {
        'pvc_requested': '0 GiB',
        'pvc_used': '0 GiB',
        'pvc_free': '0 GiB',
        'pvc_risk_count': 0,
        'used_percent': 0,
        'free_percent': 0,
        'top_namespace': '-',
        'recommendation_count': 0,
    }


def _count_pvc_risks(
    pvc_rows: list[Any],
) -> int:
    risk_count = 0

    for row in pvc_rows:
        row_dict = _as_dict(
            row,
        )

        risk = _as_dict(
            row_dict.get(
                'risk',
                {},
            )
        )

        risk_label = str(
            risk.get(
                'label',
                '',
            )
        ).lower()

        usage_percent = _safe_float(
            row_dict.get(
                'usage_percent',
                0,
            )
        )

        status = str(
            row_dict.get(
                'status',
                '',
            )
        ).lower()

        if risk_label in [
            'high',
            'warning',
            'critical',
            'watch',
        ]:
            risk_count += 1
            continue

        if status in [
            'pending',
            'lost',
            'failed',
        ]:
            risk_count += 1
            continue

        if usage_percent >= 75:
            risk_count += 1

    return risk_count


def _get_top_storage_namespace(
    pvc_rows: list[Any],
) -> str:
    namespace_usage: dict[str, float] = {}

    for row in pvc_rows:
        row_dict = _as_dict(
            row,
        )

        namespace = str(
            row_dict.get(
                'namespace',
                '',
            )
        )

        if not namespace:
            continue

        used_value = _parse_storage_display_to_gib(
            row_dict.get(
                'used',
                '0 GiB',
            )
        )

        namespace_usage[namespace] = (
            namespace_usage.get(
                namespace,
                0.0,
            )
            + used_value
        )

    if not namespace_usage:
        return '-'

    return max(
        namespace_usage.items(),
        key=lambda item: item[1],
    )[0]


def _parse_storage_display_to_gib(
    value: Any,
) -> float:
    text = str(
        value or '',
    ).strip()

    if not text:
        return 0.0

    parts = text.split()

    if not parts:
        return 0.0

    number = _safe_float(
        parts[0],
    )

    unit = parts[1].lower() if len(parts) > 1 else 'gib'

    multiplier_map = {
        'b': 1 / 1024**3,
        'bytes': 1 / 1024**3,
        'kib': 1 / 1024**2,
        'kb': 1 / 1024**2,
        'mib': 1 / 1024,
        'mb': 1 / 1024,
        'gib': 1,
        'gb': 1,
        'tib': 1024,
        'tb': 1024,
    }

    return number * multiplier_map.get(
        unit,
        1,
    )


def present_storage_materialized_context(
    context: dict[str, Any],
    query_args: Mapping[str, Any],
) -> dict[str, Any]:
    """Apply storage table filters and pagination to a committed snapshot."""
    from copy import deepcopy

    presented = deepcopy(context)
    selected_namespace = get_query_value(query_args=query_args, name='namespace', default='')
    selected_storage_node = get_query_value(query_args=query_args, name='storage_node', default='')
    selected_storage_tab = get_selected_storage_tab(query_args)
    selected_pvc_search = get_query_value(query_args=query_args, name='pvc_search', default='')
    selected_pvc_status = get_query_value(query_args=query_args, name='pvc_status', default='')
    selected_pvc_storage_class = get_query_value(
        query_args=query_args,
        name='pvc_storage_class',
        default='',
    )
    selected_pv_search = get_query_value(query_args=query_args, name='pv_search', default='')
    selected_pv_status = get_query_value(query_args=query_args, name='pv_status', default='')
    selected_pv_storage_class = get_query_value(
        query_args=query_args,
        name='pv_storage_class',
        default='',
    )

    storage_summary = deepcopy(presented.get('storage_summary') or {})
    node_filesystem = deepcopy(storage_summary.get('node_filesystem') or {})
    available_nodes = list(node_filesystem.get('available_nodes') or [])
    if selected_storage_node and selected_storage_node not in available_nodes:
        selected_storage_node = ''
    node_rows = list(node_filesystem.get('rows') or [])
    if selected_storage_node:
        node_rows = [
            row for row in node_rows
            if str(row.get('node') or '') == selected_storage_node
        ]
    node_filesystem['rows'] = node_rows
    node_filesystem['selected_node'] = selected_storage_node
    node_capacity = sum(_safe_float(row.get('capacity_bytes')) for row in node_rows)
    node_used = sum(_safe_float(row.get('used_bytes')) for row in node_rows)
    node_free = sum(_safe_float(row.get('free_bytes')) for row in node_rows)
    highest_row = max(
        node_rows,
        key=lambda row: _safe_float(row.get('usage_percent')),
        default=None,
    )
    formatter = StorageAnalysisService.__new__(StorageAnalysisService)
    node_filesystem['summary'] = {
        'capacity': formatter.format_bytes(node_capacity),
        'used': formatter.format_bytes(node_used),
        'free': formatter.format_bytes(node_free),
        'usage_percent': safe_round(raw_percent(node_used, node_capacity), 1),
        'free_percent': safe_round(raw_percent(node_free, node_capacity), 1),
        'highest_usage': _safe_float(highest_row.get('usage_percent')) if highest_row else 0.0,
        'highest_node': str(highest_row.get('node') or '-') if highest_row else '-',
    }

    persistent = deepcopy(storage_summary.get('persistent_storage') or {})
    pvc_all_rows = list(persistent.get('pvc_all_rows') or persistent.get('pvc_rows') or [])
    pv_all_rows = list(persistent.get('pv_all_rows') or persistent.get('pv_rows') or [])
    if selected_namespace:
        pvc_all_rows = [
            row for row in pvc_all_rows
            if str(row.get('namespace') or '') == selected_namespace
        ]

    service = StorageAnalysisService.__new__(StorageAnalysisService)
    pvc_filtered = service.filter_storage_rows(
        pvc_all_rows,
        selected_search=selected_pvc_search,
        selected_status=selected_pvc_status,
        selected_storage_class=selected_pvc_storage_class,
    )
    pv_filtered = service.filter_storage_rows(
        pv_all_rows,
        selected_search=selected_pv_search,
        selected_status=selected_pv_status,
        selected_storage_class=selected_pv_storage_class,
    )
    paginator = AnalyticsBaseService()
    pvc_page = paginator.paginate_rows_with_options(
        rows=pvc_filtered,
        page=get_positive_int_arg(query_args=query_args, name='pvc_page', default=1),
        per_page=get_per_page_arg(query_args=query_args, name='pvc_per_page', default=5),
        allowed_per_page=ALLOWED_PER_PAGE_VALUES,
        default_per_page=5,
    )
    pv_page = paginator.paginate_rows_with_options(
        rows=pv_filtered,
        page=get_positive_int_arg(query_args=query_args, name='pv_page', default=1),
        per_page=get_per_page_arg(query_args=query_args, name='pv_per_page', default=5),
        allowed_per_page=ALLOWED_PER_PAGE_VALUES,
        default_per_page=5,
    )
    pvc_requested = sum(_safe_float(row.get('requested_bytes')) for row in pvc_all_rows)
    pvc_used = sum(_safe_float(row.get('used_bytes')) for row in pvc_all_rows)
    pvc_free = sum(_safe_float(row.get('free_bytes')) for row in pvc_all_rows)
    pv_capacity = sum(_safe_float(row.get('capacity_bytes')) for row in pv_all_rows)
    persistent.update(
        {
            'pv': {
                'count': len(pv_all_rows),
                'capacity': formatter.format_bytes(pv_capacity),
                'used': formatter.format_bytes(pvc_used),
                'free': formatter.format_bytes(pvc_free),
                'used_percent': safe_round(raw_percent(pvc_used, pv_capacity), 1),
                'free_percent': safe_round(raw_percent(pvc_free, pv_capacity), 1),
            },
            'pvc': {
                'count': len(pvc_all_rows),
                'requested': formatter.format_bytes(pvc_requested),
                'used': formatter.format_bytes(pvc_used),
                'free': formatter.format_bytes(pvc_free),
                'used_percent': safe_round(raw_percent(pvc_used, pvc_requested), 1),
                'free_percent': safe_round(raw_percent(pvc_free, pvc_requested), 1),
            },
            'pvc_all_rows': pvc_all_rows,
            'pvc_rows': pvc_page['rows'],
            'pvc_pagination': pvc_page['pagination'],
            'pvc_selected_search': selected_pvc_search,
            'pvc_selected_status': selected_pvc_status,
            'pvc_selected_storage_class': selected_pvc_storage_class,
            'pvc_status_options': service.get_unique_options(pvc_all_rows, 'status'),
            'pvc_storage_class_options': service.get_unique_options(pvc_all_rows, 'storage_class'),
            'pv_all_rows': pv_all_rows,
            'pv_rows': pv_page['rows'],
            'pv_pagination': pv_page['pagination'],
            'pv_selected_search': selected_pv_search,
            'pv_selected_status': selected_pv_status,
            'pv_selected_storage_class': selected_pv_storage_class,
            'pv_status_options': service.get_unique_options(pv_all_rows, 'status'),
            'pv_storage_class_options': service.get_unique_options(pv_all_rows, 'storage_class'),
        }
    )
    storage_summary['node_filesystem'] = node_filesystem
    storage_summary['persistent_storage'] = persistent
    recommendations = build_storage_actionable_recommendations({'storage_summary': storage_summary})
    presented.update(
        {
            'selected_namespace': selected_namespace,
            'selected_time_range': 'current',
            'allowed_time_ranges': (),
            'selected_storage_node': selected_storage_node,
            'selected_storage_tab': selected_storage_tab,
            'selected_pvc_search': selected_pvc_search,
            'selected_pvc_status': selected_pvc_status,
            'selected_pvc_storage_class': selected_pvc_storage_class,
            'selected_pv_search': selected_pv_search,
            'selected_pv_status': selected_pv_status,
            'selected_pv_storage_class': selected_pv_storage_class,
            'storage_summary': storage_summary,
            'actionable_recommendations': recommendations,
            'recommendation_cards': format_recommendation_cards(recommendations),
            'recommendation_count': count_actionable_recommendations(recommendations),
        }
    )
    return presented
