from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from app.analytics.common.base_service import AnalyticsBaseService
from app.analytics.common.params import (
    ALLOWED_PER_PAGE_VALUES,
    get_per_page_arg,
    get_positive_int_arg,
    get_query_value,
)
from app.analytics.workload.domain import build_workload_posture
from app.analytics.workload.mapping import build_workload_scope_summary
from app.analytics.workload.quota import build_tenant_scope_summary
from app.intelligence.recommendation_engine import (
    build_workload_actionable_recommendations,
    count_actionable_recommendations,
    format_recommendation_cards,
)

_WORKLOAD_TABS = {'quotas', 'mapping', 'recommendations'}


def filter_tenant_quota_rows(
    rows: list[dict[str, Any]],
    selected_search: str = '',
    selected_quota_status: str = '',
    selected_risk: str = '',
) -> list[dict[str, Any]]:
    search = selected_search.casefold().strip()
    return [
        row
        for row in rows
        if (not search or search in str(row.get('namespace') or '').casefold())
        and (
            not selected_quota_status
            or str((row.get('quota_status') or {}).get('label') or '') == selected_quota_status
        )
        and (not selected_risk or str((row.get('risk') or {}).get('label') or '') == selected_risk)
    ]


def filter_workload_rows(
    rows: list[dict[str, Any]],
    selected_search: str = '',
    selected_type: str = '',
    selected_configuration: str = '',
    selected_qos: str = '',
    selected_risk: str = '',
) -> list[dict[str, Any]]:
    search = selected_search.casefold().strip()
    return [
        row
        for row in rows
        if (
            not search
            or search in str(row.get('workload') or '').casefold()
            or search in str(row.get('namespace') or '').casefold()
        )
        and (not selected_type or str(row.get('type') or '') == selected_type)
        and (
            not selected_configuration
            or str((row.get('configuration_status') or {}).get('label') or '') == selected_configuration
        )
        and (not selected_qos or str((row.get('qos') or {}).get('label') or '') == selected_qos)
        and (not selected_risk or str((row.get('risk') or {}).get('label') or '') == selected_risk)
    ]


def present_workload_materialized_context(
    context: dict[str, Any],
    query_args: Mapping[str, Any],
) -> dict[str, Any]:
    """Apply presentation-only scope, filters, active tab, and pagination."""
    presented = deepcopy(context)
    state = _selected_state(query_args)
    namespace_options = list(presented.get('namespace_options') or [])
    if state['selected_namespace'] not in namespace_options:
        state['selected_namespace'] = ''

    tenant_scope_rows = _scope_rows(
        list(presented.get('tenant_quota_rows') or []),
        state['selected_namespace'],
    )
    workload_scope_rows = _scope_rows(
        list(presented.get('workload_mapping_rows') or []),
        state['selected_namespace'],
    )
    tenant_filtered = filter_tenant_quota_rows(
        tenant_scope_rows,
        state['selected_tenant_search'],
        state['selected_tenant_quota_status'],
        state['selected_tenant_risk'],
    )
    workload_filtered = filter_workload_rows(
        workload_scope_rows,
        state['selected_workload_search'],
        state['selected_workload_type'],
        state['selected_workload_configuration'],
        state['selected_workload_qos'],
        state['selected_workload_risk'],
    )

    paginator = AnalyticsBaseService()
    tenant_page = paginator.paginate_rows_with_options(
        rows=tenant_filtered,
        page=get_positive_int_arg(query_args=query_args, name='quota_page', default=1),
        per_page=get_per_page_arg(query_args=query_args, name='quota_per_page', default=5),
        allowed_per_page=ALLOWED_PER_PAGE_VALUES,
    )
    workload_page = paginator.paginate_rows_with_options(
        rows=workload_filtered,
        page=get_positive_int_arg(query_args=query_args, name='workload_page', default=1),
        per_page=get_per_page_arg(query_args=query_args, name='workload_per_page', default=5),
        allowed_per_page=ALLOWED_PER_PAGE_VALUES,
    )

    governance_findings = _scope_findings(
        list(presented.get('governance_findings') or []),
        state['selected_namespace'],
    )
    tenant_summary = {
        **build_tenant_scope_summary(tenant_scope_rows),
        'rows': tenant_page['rows'],
        'pagination': tenant_page['pagination'],
    }
    workload_scope_summary = build_workload_scope_summary(workload_scope_rows)
    mapping_payload = {
        **deepcopy(presented.get('workload_mapping_payload') or {}),
        'rows': workload_page['rows'],
        'pagination': workload_page['pagination'],
        'scope_summary': workload_scope_summary,
        **_mapping_options(workload_scope_rows),
    }
    recommendations = build_workload_actionable_recommendations(
        {
            'tenant_quota_summary': {**tenant_summary, 'rows': tenant_scope_rows},
            'tenant_quota_rows': tenant_scope_rows,
            'workload_mapping_payload': {**mapping_payload, 'rows': workload_scope_rows},
            'workload_mapping_rows': workload_scope_rows,
            'governance_findings': governance_findings,
            'selected_namespace': state['selected_namespace'],
            'selected_time_range': presented.get('selected_time_range', '24h'),
        }
    )
    recommendation_cards = format_recommendation_cards(
        recommendations,
        default_title='Continue Workload Governance Monitoring',
        default_description=(
            'No actionable workload recommendation was generated from the current quota, '
            'request, limit, QoS, and right-sizing signals.'
        ),
        default_source='workload_baseline',
        default_action_type='workload_governance',
    )
    recommendation_count = count_actionable_recommendations(recommendations)
    presented.update(
        {
            **state,
            'tenant_quota_summary': tenant_summary,
            'tenant_quota_rows': tenant_scope_rows,
            'quota_status_options': _nested_label_options(tenant_scope_rows, 'quota_status'),
            'tenant_risk_options': _nested_label_options(tenant_scope_rows, 'risk'),
            'workload_mapping_payload': mapping_payload,
            'workload_mapping_rows': workload_scope_rows,
            'workload_scope_summary': workload_scope_summary,
            'governance_findings': governance_findings,
            'actionable_recommendations': recommendations,
            'recommendation_cards': recommendation_cards,
            'recommendation_count': recommendation_count,
            'workload_count_display': f'{len(workload_scope_rows)} Workloads',
            'recommendation_count_display': f'{recommendation_count} Actionable',
            'finding_count_display': f'{len(governance_findings)} Findings',
            'workload_posture': build_workload_posture(
                tenant_scope_rows,
                workload_scope_rows,
                governance_findings,
            ),
        }
    )
    return presented


def _selected_state(query_args: Mapping[str, Any]) -> dict[str, str]:
    initial_tab = get_query_value(query_args=query_args, name='tab', default='quotas')
    if initial_tab not in _WORKLOAD_TABS:
        initial_tab = 'quotas'
    return {
        'selected_namespace': get_query_value(query_args=query_args, name='namespace', default=''),
        'selected_tenant_search': get_query_value(query_args=query_args, name='tenant_search', default=''),
        'selected_tenant_quota_status': get_query_value(query_args=query_args, name='tenant_quota_status', default=''),
        'selected_tenant_risk': get_query_value(query_args=query_args, name='tenant_risk', default=''),
        'selected_workload_search': get_query_value(query_args=query_args, name='workload_search', default=''),
        'selected_workload_type': get_query_value(query_args=query_args, name='workload_type', default=''),
        'selected_workload_configuration': get_query_value(
            query_args=query_args, name='workload_configuration', default=''
        ),
        'selected_workload_qos': get_query_value(query_args=query_args, name='workload_qos', default=''),
        'selected_workload_risk': get_query_value(query_args=query_args, name='workload_risk', default=''),
        'initial_tab': initial_tab,
    }


def _scope_rows(rows: list[dict[str, Any]], selected_namespace: str) -> list[dict[str, Any]]:
    if not selected_namespace:
        return rows
    return [row for row in rows if str(row.get('namespace') or '') == selected_namespace]


def _scope_findings(findings: list[dict[str, Any]], selected_namespace: str) -> list[dict[str, Any]]:
    if not selected_namespace:
        return findings
    return [finding for finding in findings if str(finding.get('namespace') or '') in {'', selected_namespace}]


def _nested_label_options(rows: list[dict[str, Any]], field: str) -> list[str]:
    return sorted(
        {
            str((row.get(field) or {}).get('label') or '')
            for row in rows
            if str((row.get(field) or {}).get('label') or '')
        }
    )


def _mapping_options(rows: list[dict[str, Any]]) -> dict[str, list[str]]:
    return {
        'workload_type_options': sorted({str(row.get('type') or '') for row in rows if row.get('type')}),
        'configuration_options': _nested_label_options(rows, 'configuration_status'),
        'qos_options': _nested_label_options(rows, 'qos'),
        'risk_options': _nested_label_options(rows, 'risk'),
    }
