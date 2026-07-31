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
    get_query_value,
    get_selected_time_range,
)
from app.analytics.common.payloads import get_empty_storage_payload
from app.analytics.storage.pagination import resolve_storage_pagination
from app.analytics.utilization.service import UtilizationService
from app.common.dependencies import prometheus_capability_blocker, prometheus_connection_blocker
from app.integrations.prometheus.capabilities import definition as capability_definition
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


STORAGE_TABS = ('capacity', 'filesystem', 'pvc', 'pv', 'recommendations')


def get_selected_storage_tab(
    query_args: Mapping[str, Any],
    *,
    default: str = 'capacity',
) -> str:
    selected_storage_tab = get_query_value(
        query_args=query_args,
        name='tab',
        default=default,
    )
    return selected_storage_tab if selected_storage_tab in STORAGE_TABS else default


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
            include_presentation_classes=False,
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
        filesystem_page: int = 1,
        filesystem_per_page: int = 5,
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
        node_var_size = self.get_filesystem_vector_map(NODE_VAR_FILESYSTEM_SIZE_QUERY)
        node_var_available = self.get_filesystem_vector_map(NODE_VAR_FILESYSTEM_AVAILABLE_QUERY)
        node_root_size = self.get_filesystem_vector_map(NODE_ROOT_FILESYSTEM_SIZE_QUERY)
        node_root_available = self.get_filesystem_vector_map(NODE_ROOT_FILESYSTEM_AVAILABLE_QUERY)

        node_size: dict[str, float] = {}
        node_available: dict[str, float] = {}
        node_mountpoint: dict[str, str] = {}

        for node, size in node_root_size.items():
            node_size[node] = size
            node_available[node] = node_root_available.get(node, 0)
            node_mountpoint[node] = '/'

        for node, size in node_var_size.items():
            node_size[node] = size
            node_available[node] = node_var_available.get(node, 0)
            node_mountpoint[node] = '/var'

        all_node_rows: list[dict[str, Any]] = []
        for node, size in sorted(node_size.items()):
            available = node_available.get(node, 0)
            used = max(_safe_float(size) - _safe_float(available), 0.0)
            evidence_available = _safe_float(size) > 0
            usage_percent = raw_percent(used, size) if evidence_available else None
            all_node_rows.append(
                {
                    'node': node,
                    'mountpoint': node_mountpoint.get(node, '/'),
                    'capacity': self.format_bytes(size) if evidence_available else 'N/A',
                    'used': self.format_bytes(used) if evidence_available else 'N/A',
                    'free': self.format_bytes(available) if evidence_available else 'N/A',
                    'usage_percent': safe_round(usage_percent, 1) if usage_percent is not None else None,
                    'risk': self.get_usage_risk(usage_percent),
                    'evidence_available': evidence_available,
                    'capacity_bytes': size if evidence_available else None,
                    'used_bytes': used if evidence_available else None,
                    'free_bytes': available if evidence_available else None,
                }
            )

        scoped_node_rows = [
            row for row in all_node_rows
            if not selected_node or str(row.get('node') or '') == selected_node
        ]
        filesystem_page_payload = self.paginate_rows(
            rows=scoped_node_rows,
            page=filesystem_page,
            per_page=filesystem_per_page,
        )
        filesystem_summary = self.build_filesystem_summary(scoped_node_rows)

        pvc_requested_total = self.get_prometheus_scalar(PVC_REQUESTED_TOTAL_QUERY)
        pvc_used_total = self.get_prometheus_scalar(PVC_USED_TOTAL_QUERY)
        pvc_available_total = self.get_prometheus_scalar(PVC_AVAILABLE_TOTAL_QUERY)
        pv_capacity_total = self.get_prometheus_scalar(PV_CAPACITY_QUERY)
        pv_count_total = self.get_prometheus_scalar(PV_COUNT_QUERY)
        pvc_count_total = self.get_prometheus_scalar(PVC_COUNT_QUERY)

        pvc_cluster_rows = self.get_pvc_detail_rows(selected_namespace='')
        pvc_scope_rows = [
            row for row in pvc_cluster_rows
            if not selected_namespace or str(row.get('namespace') or '') == selected_namespace
        ]
        pv_all_rows = self.get_pv_detail_rows()

        pvc_requested = sum(_safe_float(row.get('requested_bytes')) for row in pvc_scope_rows)
        pvc_used = sum(_safe_float(row.get('used_bytes')) for row in pvc_scope_rows)
        pvc_free = sum(_safe_float(row.get('free_bytes')) for row in pvc_scope_rows)
        if not pvc_cluster_rows and not selected_namespace:
            pvc_requested = pvc_requested_total
            pvc_used = pvc_used_total
            pvc_free = pvc_available_total

        cluster_pvc_requested = sum(_safe_float(row.get('requested_bytes')) for row in pvc_cluster_rows)
        cluster_pvc_used = sum(_safe_float(row.get('used_bytes')) for row in pvc_cluster_rows)
        if not pvc_cluster_rows:
            cluster_pvc_requested = pvc_requested_total
            cluster_pvc_used = pvc_used_total

        pv_capacity = sum(_safe_float(row.get('capacity_bytes')) for row in pv_all_rows)
        if not pv_all_rows:
            pv_capacity = pv_capacity_total

        pvc_evidence_available = bool(pvc_scope_rows) or (not selected_namespace and pvc_requested_total > 0)
        pv_evidence_available = bool(pv_all_rows) or pv_capacity_total > 0
        pvc_used_percent = raw_percent(pvc_used, pvc_requested) if pvc_evidence_available and pvc_requested > 0 else None
        pvc_free_percent = raw_percent(pvc_free, pvc_requested) if pvc_evidence_available and pvc_requested > 0 else None
        claim_usage_vs_provisioned = (
            raw_percent(cluster_pvc_used, pv_capacity)
            if pv_evidence_available and pv_capacity > 0 and cluster_pvc_used >= 0
            else None
        )
        requested_vs_provisioned = (
            raw_percent(cluster_pvc_requested, pv_capacity)
            if pv_evidence_available and pv_capacity > 0 and cluster_pvc_requested >= 0
            else None
        )
        unallocated_difference = max(pv_capacity - cluster_pvc_requested, 0.0)

        pvc_status_options = self.get_unique_options(rows=pvc_scope_rows, key='status')
        pvc_storage_class_options = self.get_unique_options(rows=pvc_scope_rows, key='storage_class')
        pvc_filtered_rows = self.filter_storage_rows(
            rows=pvc_scope_rows,
            selected_search=selected_pvc_search,
            selected_status=selected_pvc_status,
            selected_storage_class=selected_pvc_storage_class,
        )
        pvc_page_payload = self.paginate_rows(
            rows=pvc_filtered_rows,
            page=pvc_page,
            per_page=pvc_per_page,
        )

        pv_status_options = self.get_unique_options(rows=pv_all_rows, key='status')
        pv_storage_class_options = self.get_unique_options(rows=pv_all_rows, key='storage_class')
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
                'available_nodes': sorted(node_size.keys()),
                'scope_label': selected_node or 'All Nodes',
                'summary': filesystem_summary,
                'all_rows': all_node_rows,
                'rows': filesystem_page_payload['rows'],
                'pagination': filesystem_page_payload['pagination'],
            },
            'persistent_storage': {
                'pv': {
                    'evidence_available': pv_evidence_available,
                    'count': len(pv_all_rows) if pv_all_rows else int(pv_count_total),
                    'capacity': self.format_bytes(pv_capacity) if pv_evidence_available else 'N/A',
                    'observed_claim_usage': self.format_bytes(cluster_pvc_used) if pvc_cluster_rows or pvc_used_total > 0 else 'N/A',
                    'requested_claim_capacity': self.format_bytes(cluster_pvc_requested) if pvc_cluster_rows or pvc_requested_total > 0 else 'N/A',
                    'unallocated_provisioned_difference': self.format_bytes(unallocated_difference) if pv_evidence_available else 'N/A',
                    'claim_usage_vs_provisioned_percent': safe_round(claim_usage_vs_provisioned, 1) if claim_usage_vs_provisioned is not None else None,
                    'requested_vs_provisioned_percent': safe_round(requested_vs_provisioned, 1) if requested_vs_provisioned is not None else None,
                    'scope_label': 'Cluster',
                },
                'pvc': {
                    'evidence_available': pvc_evidence_available,
                    'count': len(pvc_scope_rows) if pvc_cluster_rows else int(pvc_count_total),
                    'requested': self.format_bytes(pvc_requested) if pvc_evidence_available else 'N/A',
                    'used': self.format_bytes(pvc_used) if pvc_evidence_available else 'N/A',
                    'free': self.format_bytes(pvc_free) if pvc_evidence_available else 'N/A',
                    'used_percent': safe_round(pvc_used_percent, 1) if pvc_used_percent is not None else None,
                    'free_percent': safe_round(pvc_free_percent, 1) if pvc_free_percent is not None else None,
                    'scope_label': f'Namespace · {selected_namespace}' if selected_namespace else 'All Namespaces',
                },
                'pvc_all_rows': pvc_scope_rows,
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

    def build_filesystem_summary(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        available_rows = [row for row in rows if row.get('evidence_available')]
        total_capacity = sum(_safe_float(row.get('capacity_bytes')) for row in available_rows)
        total_used = sum(_safe_float(row.get('used_bytes')) for row in available_rows)
        total_free = sum(_safe_float(row.get('free_bytes')) for row in available_rows)
        highest_row = max(
            available_rows,
            key=lambda row: _safe_float(row.get('usage_percent')),
            default=None,
        )
        evidence_available = bool(available_rows) and total_capacity > 0
        usage_percent = raw_percent(total_used, total_capacity) if evidence_available else None
        free_percent = raw_percent(total_free, total_capacity) if evidence_available else None
        return {
            'evidence_available': evidence_available,
            'capacity': self.format_bytes(total_capacity) if evidence_available else 'N/A',
            'used': self.format_bytes(total_used) if evidence_available else 'N/A',
            'free': self.format_bytes(total_free) if evidence_available else 'N/A',
            'usage_percent': safe_round(usage_percent, 1) if usage_percent is not None else None,
            'free_percent': safe_round(free_percent, 1) if free_percent is not None else None,
            'highest_usage': _safe_float(highest_row.get('usage_percent')) if highest_row else None,
            'highest_node': str(highest_row.get('node') or '-') if highest_row else '-',
            'risk': self.get_usage_risk(_safe_float(highest_row.get('usage_percent')) if highest_row else None),
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

    def get_pvc_status_tone(self, status: str) -> str:
        return {
            'Bound': 'normal',
            'Pending': 'warning',
            'Lost': 'critical',
        }.get(status, 'unknown')

    def get_pvc_risk(
        self,
        status: str,
        usage_percent: float | None,
        *,
        evidence_available: bool,
    ) -> dict[str, str]:
        if status == 'Lost':
            return {'label': 'Critical', 'tone': 'critical'}
        if status == 'Pending':
            return {'label': 'Watch', 'tone': 'warning'}
        if not evidence_available or usage_percent is None:
            return {'label': 'Unknown', 'tone': 'unknown'}
        if usage_percent >= 90:
            return {'label': 'Critical', 'tone': 'critical'}
        if usage_percent >= 75:
            return {'label': 'Watch', 'tone': 'warning'}
        return {'label': 'Healthy', 'tone': 'normal'}

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
        keys = set(requested) | set(used) | set(available) | set(storage_classes) | set(status_map)
        rows: list[dict[str, Any]] = []

        for key in sorted(keys):
            namespace, pvc_name = self.split_composite_key(key)
            if selected_namespace and namespace != selected_namespace:
                continue

            requested_known = key in requested
            used_known = key in used
            available_known = key in available
            requested_value = requested.get(key, 0)
            used_value = used.get(key, 0)
            free_value = available.get(key, 0)
            denominator_available = requested_known and _safe_float(requested_value) > 0
            usage_evidence_available = denominator_available and used_known
            usage_percent = raw_percent(used_value, requested_value) if usage_evidence_available else None
            status = status_map.get(key, 'Unknown')

            rows.append(
                {
                    'name': pvc_name,
                    'namespace': namespace,
                    'status': status,
                    'status_tone': self.get_pvc_status_tone(status),
                    'storage_class': storage_classes.get(key, 'No StorageClass'),
                    'requested': self.format_bytes(requested_value) if requested_known else 'N/A',
                    'used': self.format_bytes(used_value) if used_known else 'N/A',
                    'free': self.format_bytes(free_value) if available_known else 'N/A',
                    'requested_bytes': requested_value if requested_known else None,
                    'used_bytes': used_value if used_known else None,
                    'free_bytes': free_value if available_known else None,
                    'usage_percent': safe_round(usage_percent, 1) if usage_percent is not None else None,
                    'evidence_available': usage_evidence_available,
                    'risk': self.get_pvc_risk(
                        status=status,
                        usage_percent=usage_percent,
                        evidence_available=usage_evidence_available,
                    ),
                }
            )

        return rows

    def get_pv_detail_rows(self) -> list[dict[str, Any]]:
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
        volumes = set(capacities) | set(storage_classes) | set(claim_map) | set(reclaim_policies) | set(status_map)
        rows: list[dict[str, Any]] = []

        for volume in sorted(volumes):
            status = status_map.get(volume, 'Unknown')
            capacity_known = volume in capacities and _safe_float(capacities.get(volume)) > 0
            capacity = capacities.get(volume, 0)
            rows.append(
                {
                    'name': volume,
                    'status': status,
                    'status_tone': self.get_pv_status_tone(status),
                    'capacity': self.format_bytes(capacity) if capacity_known else 'N/A',
                    'capacity_bytes': capacity if capacity_known else None,
                    'evidence_available': capacity_known,
                    'storage_class': storage_classes.get(volume, 'No StorageClass'),
                    'claim': claim_map.get(volume, '-'),
                    'reclaim_policy': reclaim_policies.get(volume, '-'),
                    'risk': self.get_pv_risk(status),
                }
            )

        return rows

    def get_pv_status_tone(self, status: str) -> str:
        return {
            'Bound': 'normal',
            'Available': 'info',
            'Released': 'warning',
            'Failed': 'critical',
        }.get(status, 'unknown')

    def get_pv_risk(self, status: str) -> dict[str, str]:
        if status == 'Bound':
            return {'label': 'Healthy', 'tone': 'normal'}
        if status == 'Available':
            return {'label': 'Available', 'tone': 'info'}
        if status == 'Released':
            return {'label': 'Watch', 'tone': 'warning'}
        if status == 'Failed':
            return {'label': 'Critical', 'tone': 'critical'}
        return {'label': 'Unknown', 'tone': 'unknown'}

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

    def get_usage_risk(self, percent: float | None) -> dict[str, str]:
        if percent is None:
            return {'label': 'Unknown', 'tone': 'unknown'}
        if percent >= 90:
            return {'label': 'Critical', 'tone': 'critical'}
        if percent >= 75:
            return {'label': 'Watch', 'tone': 'warning'}
        return {'label': 'Healthy', 'tone': 'normal'}


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
    except Exception as exc:
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
        pagination_state = resolve_storage_pagination(
            query_args,
            allowed_per_page=ALLOWED_PER_PAGE_VALUES,
            default_per_page=5,
        )
        storage_summary = storage_service.get_storage_capacity_summary(
            selected_namespace=selected_namespace,
            selected_node=selected_storage_node,
            filesystem_page=pagination_state['filesystem']['page'],
            filesystem_per_page=pagination_state['filesystem']['per_page'],
            selected_pvc_search=selected_pvc_search,
            selected_pvc_status=selected_pvc_status,
            selected_pvc_storage_class=selected_pvc_storage_class,
            pvc_page=pagination_state['pvc']['page'],
            pvc_per_page=pagination_state['pvc']['per_page'],
            selected_pv_search=selected_pv_search,
            selected_pv_status=selected_pv_status,
            selected_pv_storage_class=selected_pv_storage_class,
            pv_page=pagination_state['pv']['page'],
            pv_per_page=pagination_state['pv']['per_page'],
        )
        namespace_options = storage_service.get_storage_namespace_options()
    except Exception as exc:
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
    """Apply storage presentation filters and pagination to one committed snapshot."""
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
    pagination_state = resolve_storage_pagination(
        query_args,
        allowed_per_page=ALLOWED_PER_PAGE_VALUES,
        default_per_page=5,
    )

    storage_summary = deepcopy(presented.get('storage_summary') or {})
    service = StorageAnalysisService.__new__(StorageAnalysisService)
    paginator = AnalyticsBaseService()

    node_filesystem = deepcopy(storage_summary.get('node_filesystem') or {})
    all_node_rows = list(node_filesystem.get('all_rows') or node_filesystem.get('rows') or [])
    available_nodes = sorted(
        {str(row.get('node') or '') for row in all_node_rows if str(row.get('node') or '')}
        | set(node_filesystem.get('available_nodes') or [])
    )
    if selected_storage_node and selected_storage_node not in available_nodes:
        selected_storage_node = ''
    scoped_node_rows = [
        row for row in all_node_rows
        if not selected_storage_node or str(row.get('node') or '') == selected_storage_node
    ]
    filesystem_page = paginator.paginate_rows_with_options(
        rows=scoped_node_rows,
        page=pagination_state['filesystem']['page'],
        per_page=pagination_state['filesystem']['per_page'],
        allowed_per_page=ALLOWED_PER_PAGE_VALUES,
        default_per_page=5,
    )
    node_filesystem.update(
        {
            'all_rows': all_node_rows,
            'available_nodes': available_nodes,
            'selected_node': selected_storage_node,
            'scope_label': selected_storage_node or 'All Nodes',
            'summary': service.build_filesystem_summary(scoped_node_rows),
            'rows': filesystem_page['rows'],
            'pagination': filesystem_page['pagination'],
        }
    )

    persistent = deepcopy(storage_summary.get('persistent_storage') or {})
    cluster_pvc_rows = list(persistent.get('pvc_all_rows') or persistent.get('pvc_rows') or [])
    pv_all_rows = list(persistent.get('pv_all_rows') or persistent.get('pv_rows') or [])
    scoped_pvc_rows = [
        row for row in cluster_pvc_rows
        if not selected_namespace or str(row.get('namespace') or '') == selected_namespace
    ]

    pvc_filtered = service.filter_storage_rows(
        scoped_pvc_rows,
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
    pvc_page = paginator.paginate_rows_with_options(
        rows=pvc_filtered,
        page=pagination_state['pvc']['page'],
        per_page=pagination_state['pvc']['per_page'],
        allowed_per_page=ALLOWED_PER_PAGE_VALUES,
        default_per_page=5,
    )
    pv_page = paginator.paginate_rows_with_options(
        rows=pv_filtered,
        page=pagination_state['pv']['page'],
        per_page=pagination_state['pv']['per_page'],
        allowed_per_page=ALLOWED_PER_PAGE_VALUES,
        default_per_page=5,
    )

    pvc_requested = sum(_safe_float(row.get('requested_bytes')) for row in scoped_pvc_rows)
    pvc_used = sum(_safe_float(row.get('used_bytes')) for row in scoped_pvc_rows)
    pvc_free = sum(_safe_float(row.get('free_bytes')) for row in scoped_pvc_rows)
    cluster_pvc_requested = sum(_safe_float(row.get('requested_bytes')) for row in cluster_pvc_rows)
    cluster_pvc_used = sum(_safe_float(row.get('used_bytes')) for row in cluster_pvc_rows)
    pv_capacity = sum(_safe_float(row.get('capacity_bytes')) for row in pv_all_rows)

    pvc_evidence_available = bool(scoped_pvc_rows) and any(
        row.get('requested_bytes') is not None for row in scoped_pvc_rows
    )
    pv_evidence_available = bool(pv_all_rows) and any(
        row.get('capacity_bytes') is not None for row in pv_all_rows
    )
    pvc_used_percent = raw_percent(pvc_used, pvc_requested) if pvc_evidence_available and pvc_requested > 0 else None
    pvc_free_percent = raw_percent(pvc_free, pvc_requested) if pvc_evidence_available and pvc_requested > 0 else None
    claim_usage_vs_provisioned = (
        raw_percent(cluster_pvc_used, pv_capacity)
        if pv_evidence_available and pv_capacity > 0
        else None
    )
    requested_vs_provisioned = (
        raw_percent(cluster_pvc_requested, pv_capacity)
        if pv_evidence_available and pv_capacity > 0
        else None
    )
    unallocated_difference = max(pv_capacity - cluster_pvc_requested, 0.0)

    persistent.update(
        {
            'pv': {
                'evidence_available': pv_evidence_available,
                'count': len(pv_all_rows),
                'capacity': service.format_bytes(pv_capacity) if pv_evidence_available else 'N/A',
                'observed_claim_usage': service.format_bytes(cluster_pvc_used) if cluster_pvc_rows else 'N/A',
                'requested_claim_capacity': service.format_bytes(cluster_pvc_requested) if cluster_pvc_rows else 'N/A',
                'unallocated_provisioned_difference': service.format_bytes(unallocated_difference) if pv_evidence_available else 'N/A',
                'claim_usage_vs_provisioned_percent': safe_round(claim_usage_vs_provisioned, 1) if claim_usage_vs_provisioned is not None else None,
                'requested_vs_provisioned_percent': safe_round(requested_vs_provisioned, 1) if requested_vs_provisioned is not None else None,
                'scope_label': 'Cluster',
            },
            'pvc': {
                'evidence_available': pvc_evidence_available,
                'count': len(scoped_pvc_rows),
                'requested': service.format_bytes(pvc_requested) if pvc_evidence_available else 'N/A',
                'used': service.format_bytes(pvc_used) if pvc_evidence_available else 'N/A',
                'free': service.format_bytes(pvc_free) if pvc_evidence_available else 'N/A',
                'used_percent': safe_round(pvc_used_percent, 1) if pvc_used_percent is not None else None,
                'free_percent': safe_round(pvc_free_percent, 1) if pvc_free_percent is not None else None,
                'scope_label': f'Namespace · {selected_namespace}' if selected_namespace else 'All Namespaces',
            },
            'pvc_all_rows': scoped_pvc_rows,
            'pvc_rows': pvc_page['rows'],
            'pvc_pagination': pvc_page['pagination'],
            'pvc_selected_search': selected_pvc_search,
            'pvc_selected_status': selected_pvc_status,
            'pvc_selected_storage_class': selected_pvc_storage_class,
            'pvc_status_options': service.get_unique_options(scoped_pvc_rows, 'status'),
            'pvc_storage_class_options': service.get_unique_options(scoped_pvc_rows, 'storage_class'),
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
            'initial_tab': selected_storage_tab,
            'selected_pvc_search': selected_pvc_search,
            'selected_pvc_status': selected_pvc_status,
            'selected_pvc_storage_class': selected_pvc_storage_class,
            'selected_pv_search': selected_pv_search,
            'selected_pv_status': selected_pv_status,
            'selected_pv_storage_class': selected_pv_storage_class,
            'storage_summary': storage_summary,
            'actionable_recommendations': recommendations,
            'recommendation_cards': format_recommendation_cards(
                recommendations,
                include_presentation_classes=False,
            ),
            'recommendation_count': count_actionable_recommendations(recommendations),
        }
    )
    return presented

