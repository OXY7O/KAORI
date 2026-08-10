from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.analytics.common.base_service import AnalyticsBaseService
from app.analytics.common.coercion import as_dict, as_list
from app.analytics.common.context import build_analysis_utilization_context
from app.analytics.common.payloads import get_empty_storage_payload
from app.analytics.common.presentation import present_prometheus_status
from app.analytics.storage.domain import build_storage_payload
from app.analytics.storage.evidence import STORAGE_QUERY_CAPABILITIES, StorageEvidenceCollector
from app.analytics.utilization.service import UtilizationService
from app.common.dependencies import prometheus_capability_blocker
from app.integrations.prometheus.capabilities import definition as capability_definition
from app.intelligence.recommendation_engine import (
    build_storage_actionable_recommendations,
    count_actionable_recommendations,
    format_recommendation_cards,
)
from app.prometheus.consumer import PrometheusConsumer

_STORAGE_ADVISORY_CAPABILITIES = (
    'pvc_usage',
    'node_filesystem_identity',
)


def get_empty_storage_recommendation_context() -> dict[str, Any]:
    return {
        'actionable_recommendations': [],
        'recommendation_cards': [],
        'recommendation_count': 0,
    }


def build_storage_recommendation_context(
    storage_summary: dict[str, Any],
) -> dict[str, Any]:
    recommendations = build_storage_actionable_recommendations({'storage_summary': storage_summary})
    return {
        'actionable_recommendations': recommendations,
        'recommendation_cards': format_recommendation_cards(
            recommendations,
            include_presentation_classes=False,
        ),
        'recommendation_count': count_actionable_recommendations(recommendations),
    }


class StorageAnalysisService(AnalyticsBaseService):
    """Storage materialization facade with one canonical evidence collector."""

    REQUIRED_CAPABILITIES = STORAGE_QUERY_CAPABILITIES
    ADVISORY_CAPABILITIES = _STORAGE_ADVISORY_CAPABILITIES

    def __init__(
        self,
        utilization_service: UtilizationService,
        consumer: PrometheusConsumer,
    ) -> None:
        self.utilization_service = utilization_service
        self.consumer = consumer
        self.evidence_collector = StorageEvidenceCollector(consumer)

    def collect_storage_payload(self) -> dict[str, Any]:
        return build_storage_payload(self.evidence_collector.collect())

    def get_prometheus_status(self) -> dict[str, Any]:
        return present_prometheus_status(self.utilization_service.get_prometheus_status())


def get_storage_analysis_context(
    query_args: Mapping[str, Any],
) -> dict[str, Any]:
    _, cluster, utilization_service, context = build_analysis_utilization_context(
        query_args=query_args,
    )
    context.update(
        {
            'selected_namespace': '',
            'selected_time_range': 'current',
            'allowed_time_ranges': (),
            'selected_storage_node': '',
            'selected_storage_tab': 'capacity',
            'initial_tab': 'capacity',
            'selected_pvc_search': '',
            'selected_pvc_status': '',
            'selected_pvc_storage_class': '',
            'selected_pv_search': '',
            'selected_pv_status': '',
            'selected_pv_storage_class': '',
            'namespace_options': [],
        }
    )

    def apply_empty_payload() -> None:
        context.update(get_empty_storage_payload(selected_namespace=''))
        context.update(get_empty_storage_recommendation_context())

    if utilization_service is None or cluster is None:
        apply_empty_payload()
        return context

    consumer = PrometheusConsumer(cluster)
    required = consumer.requirements(StorageAnalysisService.REQUIRED_CAPABILITIES)
    if not required.ok:
        missing = list((required.payload or {}).get('missing_capabilities') or [])
        labels = [_capability_label(str(key)) for key in missing]
        context['dependency_blocker'] = prometheus_capability_blocker(
            cluster,
            feature_label='Storage Analytics Query Transport',
            missing_capabilities=labels,
        )
        context['storage_capability_contract'] = {
            'required': list(StorageAnalysisService.REQUIRED_CAPABILITIES),
            'advisory': list(StorageAnalysisService.ADVISORY_CAPABILITIES),
            'missing': missing,
            'source': required.source,
        }
        apply_empty_payload()
        return context

    service = StorageAnalysisService(utilization_service, consumer)
    payload = service.collect_storage_payload()
    evidence = payload.get('storage_evidence') or {}
    if not _has_observed_storage_query(evidence):
        errors = _storage_query_errors(evidence)
        blocker = prometheus_capability_blocker(
            cluster,
            feature_label='Storage Analytics Evidence',
            missing_capabilities=['Storage filesystem, PVC, and PV query evidence'],
        )
        blocker['diagnostic_detail'] = ' '.join(errors[:3]) or None
        context['dependency_blocker'] = blocker
        apply_empty_payload()
        context['storage_evidence'] = evidence
        return context

    advisory = consumer.requirements(StorageAnalysisService.ADVISORY_CAPABILITIES)
    advisory_missing = list((advisory.payload or {}).get('missing_capabilities') or [])
    context['storage_capability_contract'] = {
        'required': list(StorageAnalysisService.REQUIRED_CAPABILITIES),
        'advisory': list(StorageAnalysisService.ADVISORY_CAPABILITIES),
        'missing': advisory_missing,
        'missing_labels': [_capability_label(str(key)) for key in advisory_missing],
        'source': advisory.source,
        'degraded': bool(advisory_missing),
    }
    context.update(payload)
    context.update(build_storage_recommendation_context(as_dict(payload.get('storage_summary'))))
    return context


def get_storage_snapshot(cluster_id: str) -> dict[str, Any] | None:
    from app.analytics.materialization.service import read_snapshot

    result = read_snapshot(
        cluster_id=cluster_id,
        dataset_key='analytics.storage',
        parameters={'cluster_id': str(cluster_id)},
    )
    context = result.context or {}
    storage_summary = as_dict(context.get('storage_summary'))
    if not storage_summary:
        return None
    persistent = as_dict(storage_summary.get('persistent_storage'))
    pvc_summary = as_dict(persistent.get('pvc'))
    pvc_rows = as_list(persistent.get('pvc_all_rows') or persistent.get('pvc_rows') or [])
    used_percent = _optional_float(pvc_summary.get('used_percent'))
    free_percent = _optional_float(pvc_summary.get('free_percent'))
    actionable_recommendations = context.get('actionable_recommendations')
    return {
        'pvc_requested': str(pvc_summary.get('requested') or 'N/A'),
        'pvc_capacity': str(pvc_summary.get('capacity') or 'N/A'),
        'pvc_used': str(pvc_summary.get('used') or 'N/A'),
        'pvc_free': str(pvc_summary.get('free') or 'N/A'),
        'pvc_risk_count': _count_pvc_risks(pvc_rows),
        'used_percent': used_percent,
        'free_percent': free_percent,
        'top_namespace': _top_storage_namespace(pvc_rows),
        'recommendation_count': count_actionable_recommendations(
            actionable_recommendations if isinstance(actionable_recommendations, list) else []
        ),
    }


def _capability_label(key: str) -> str:
    capability = capability_definition(key)
    return capability.label if capability is not None else key


def _has_observed_storage_query(evidence: Any) -> bool:
    if not isinstance(evidence, dict):
        return False
    return any(int(item.get('observed_queries') or 0) > 0 for item in evidence.values() if isinstance(item, dict))


def _storage_query_errors(evidence: Any) -> list[str]:
    if not isinstance(evidence, dict):
        return []
    errors: list[str] = []
    for item in evidence.values():
        if not isinstance(item, dict):
            continue
        errors.extend(str(value) for value in item.get('errors', []) if value)
    return errors


def _count_pvc_risks(pvc_rows: list[Any]) -> int:
    count = 0
    for raw in pvc_rows:
        row = as_dict(raw)
        risk = as_dict(row.get('risk'))
        if str(risk.get('tone') or '') in {'critical', 'warning'}:
            count += 1
    return count


def _top_storage_namespace(pvc_rows: list[Any]) -> str:
    namespace_usage: dict[str, float] = {}
    for raw in pvc_rows:
        row = as_dict(raw)
        namespace = str(row.get('namespace') or '')
        used = _optional_float(row.get('used_bytes'))
        if namespace and used is not None:
            namespace_usage[namespace] = namespace_usage.get(namespace, 0.0) + used
    if not namespace_usage:
        return '-'
    return max(namespace_usage.items(), key=lambda item: item[1])[0]


def _optional_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
