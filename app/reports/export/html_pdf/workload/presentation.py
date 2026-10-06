from __future__ import annotations

from typing import Any

from .actions import (
    executive_body,
    executive_findings,
    executive_title,
    governance_analysis,
    inventory_register,
    recommendation_plan,
    source_rows,
)
from .context import WorkloadContext
from .model import (
    configuration_analysis,
    inventory_summary,
    mapping,
    mapping_analysis,
    metric,
    quota_analysis,
    reference,
    rows,
    text,
)

PAGE_COUNT = 9


def build_workload_presentation(context: WorkloadContext) -> dict[str, Any]:
    payload = context.payload
    cluster = mapping(payload.get('cluster'))
    quota_summary = mapping(payload.get('tenant_quota_summary'))
    quota_rows = rows(payload.get('tenant_quota_rows') or quota_summary.get('rows'))
    mapping_payload = mapping(payload.get('workload_mapping_payload'))
    mapping_rows = rows(payload.get('workload_mapping_rows') or mapping_payload.get('rows'))
    governance_findings = rows(payload.get('governance_findings'))
    actionable_recommendations = rows(payload.get('actionable_recommendations'))

    inventory = inventory_summary(payload, quota_rows, mapping_rows)
    quota = quota_analysis(quota_summary, quota_rows)
    mapping_state = mapping_analysis(mapping_payload, mapping_rows)
    configuration = configuration_analysis(mapping_payload, mapping_rows)
    governance = governance_analysis(governance_findings, mapping_rows, quota_rows)
    recommendations = recommendation_plan(
        actionable_recommendations,
        governance,
        quota,
        configuration,
    )
    sources = source_rows(payload, quota, mapping_state)
    findings = executive_findings(quota, configuration, governance)
    environment = text(cluster.get('environment'), 'Unknown')

    return {
        'presentation_version': 'v3.0-workload-analysis-publication',
        'page_count': PAGE_COUNT,
        'report_id': context.report_id,
        'report_name': context.report_name,
        'cluster_scope': context.cluster_scope,
        'namespace_scope': context.namespace_scope,
        'period_label': context.period_label,
        'data_cutoff': context.data_cutoff,
        'generated_at': context.generated_at,
        'generated_by': context.generated_by,
        'classification': context.classification,
        'cover': build_cover(environment),
        'executive': build_executive(inventory, quota, configuration, governance, findings),
        'inventory': build_inventory(inventory, governance),
        'quota': quota,
        'mapping': mapping_state,
        'configuration': configuration,
        'governance': governance,
        'recommendations': recommendations,
        'methodology': build_methodology(context, inventory, quota, sources),
    }


def build_cover(environment: str) -> dict[str, str]:
    return {
        'environment': environment,
        'purpose': (
            'Support application and platform review of workload inventory, tenant quota posture, '
            'resource configuration, QoS, right-sizing evidence, runtime risk, and accountable remediation.'
        ),
        'context': (
            'Quota, workload mapping, requests, limits, QoS, runtime metrics, and ownership remain separate '
            'evidence boundaries. Missing fields are never interpreted as compliant or as zero usage.'
        ),
    }


def build_executive(
    inventory: dict[str, Any],
    quota: dict[str, Any],
    configuration: dict[str, Any],
    governance: dict[str, Any],
    findings: tuple[dict[str, Any], ...],
) -> dict[str, Any]:
    return {
        'metrics': (
            metric('Workloads', inventory['workload_display'], inventory['status'], inventory['tone']),
            metric('Pods', inventory['pod_display'], inventory['status'], inventory['tone']),
            metric('Namespaces', inventory['namespace_display'], inventory['status'], inventory['tone']),
            metric(
                'Actionable Findings',
                str(governance['actionable_count']),
                'Requires Review' if governance['actionable_count'] else 'Clear',
                'warning' if governance['actionable_count'] else 'normal',
            ),
        ),
        'inventory': inventory,
        'quota': quota,
        'configuration': configuration,
        'interpretation_title': executive_title(quota, configuration, governance),
        'interpretation_body': executive_body(inventory, quota, configuration, governance),
        'interpretation_note': (
            'Runtime health, resource governance, and application ownership must be validated independently.'
        ),
        'findings': findings,
    }


def build_inventory(inventory: dict[str, Any], governance: dict[str, Any]) -> dict[str, Any]:
    return {
        'metrics': (
            metric('Workloads', inventory['workload_display'], inventory['status'], inventory['tone']),
            metric('Pods', inventory['pod_display'], inventory['status'], inventory['tone']),
            metric('Namespaces', inventory['namespace_display'], inventory['status'], inventory['tone']),
            metric('Inventory Coverage', inventory['coverage_display'], inventory['status'], inventory['tone']),
        ),
        'summary': inventory,
        'signals': governance['signals'][:3],
        'register': inventory_register(inventory, governance),
        'decision': (
            'Use workload and namespace scope to assign triage. Runtime findings do not prove quota, request, '
            'limit, QoS, or right-sizing compliance.'
        ),
    }


def build_methodology(
    context: WorkloadContext,
    inventory: dict[str, Any],
    quota: dict[str, Any],
    sources: tuple[dict[str, str], ...],
) -> dict[str, Any]:
    return {
        'metrics': (
            metric(
                'Data Sources',
                str(len(sources)),
                'Active' if sources else 'Not Available',
                'normal' if sources else 'warning',
            ),
            metric(
                'Workload Scope',
                inventory['workload_display'],
                'Committed' if inventory['available'] else 'Not Available',
                inventory['tone'],
            ),
            metric('Quota Scope', quota['coverage_display'], quota['status'], quota['tone']),
            metric('Observation Boundary', 'Snapshot', 'Committed', 'normal'),
        ),
        'sources': sources,
        'rules': (
            {'ref': 'M1', 'rule': 'Reporting Period', 'setting': context.period_label},
            {'ref': 'M2', 'rule': 'Data Cut-Off', 'setting': context.data_cutoff},
            {'ref': 'M3', 'rule': 'Quota Coverage', 'setting': 'Complete + Partial rows'},
            {'ref': 'M4', 'rule': 'Configuration Basis', 'setting': 'Requests, limits, QoS'},
            {'ref': 'M5', 'rule': 'Missing Evidence', 'setting': 'Explicit Not Available'},
        ),
        'references': (
            reference('M3', 'Quota Coverage', 'Coverage is derived only from committed namespace quota rows.'),
            reference(
                'M4',
                'Configuration Basis',
                'Workload configuration uses committed requests, limits, QoS, and metrics coverage.',
            ),
            reference(
                'M5',
                'Missing Evidence',
                'Unavailable evidence remains explicit and is never converted to compliant or zero.',
            ),
        ),
        'included': (
            'Committed workload, pod, and namespace scope derived from workload analysis rows.',
            'Committed ResourceQuota, request, limit, QoS, metrics coverage, and governance findings when available.',
            'Actionable recommendations generated from the committed workload payload.',
        ),
        'excluded': (
            'Live cluster state after the report cut-off.',
            'Application-owner identity when it is not committed in the source payload.',
            'Configuration changes, maintenance windows, and rollout approval not represented by evidence.',
        ),
        'limitations': (
            'Workload and pod counts inherit the selected Metrics Source and report scope.',
            'Quota absence and quota collection failure require separate operational validation.',
            'Validate every recommendation against live state before remediation.',
        ),
        'status_language': (
            reference('S1', 'Not Available', 'No evidence exists for the requested dimension.'),
            reference('S2', 'Not Collected', 'Collection was prevented by configuration or failure.'),
            reference('S3', 'Partial Coverage', 'Evidence exists but does not cover the full requested scope.'),
            reference('S4', 'Source Unavailable', 'The source was unreachable or not providing data at the cut-off.'),
        ),
    }
