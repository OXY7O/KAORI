from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.common.presentation import present_user_datetime
from app.jobs.constants import ACTIVE_JOB_STATUSES
from app.jobs.definitions.base import JobDefinition
from app.jobs.policies.presentation import present_interval
from app.jobs.policies.service import ensure_registered_job_policies
from app.jobs.registry import list_job_definitions
from app.models.job import JobExecution, JobPolicy

_ATTENTION_DISPATCH_STATUSES = {'failed', 'partially_succeeded'}


def _policy_status(policy: JobPolicy) -> dict[str, str]:
    if not policy.enabled:
        return {'label': 'Disabled', 'tone': 'disabled', 'icon': 'circle-pause'}
    if policy.last_dispatch_status == 'failed':
        return {'label': 'Dispatch Failed', 'tone': 'critical', 'icon': 'circle-x'}
    return {'label': 'Enabled', 'tone': 'normal', 'icon': 'circle-check'}


def _catalog_row(
    definition: JobDefinition,
    policy: JobPolicy,
    *,
    active_job_keys: set[tuple[str, str]],
) -> dict[str, Any]:
    return {
        'key': definition.key,
        'name': definition.name,
        'domain': definition.domain,
        'description': definition.description,
        'icon': definition.icon,
        'queue_name': definition.queue_name,
        'scope_type': definition.scope_type,
        'scope_key': definition.scope_key,
        'status': (
            {'label': 'Execution Active', 'tone': 'pending', 'icon': 'loader-circle'}
            if (definition.job_type, definition.operation) in active_job_keys
            else _policy_status(policy)
        ),
        'enabled': policy.enabled,
        'interval_label': present_interval(policy.interval_minutes),
        'next_run_at': present_user_datetime(policy.next_run_at, empty='Not Scheduled'),
        'last_dispatched_at': present_user_datetime(policy.last_dispatched_at, empty='Never Dispatched'),
        'last_dispatch_status': (policy.last_dispatch_status or 'not_dispatched').replace('_', ' ').title(),
        'active': (definition.job_type, definition.operation) in active_job_keys,
    }


def build_job_configuration_context(*, selected_job_key: str | None = None) -> dict[str, Any]:
    policies = ensure_registered_job_policies()
    policy_by_key = {policy.job_key: policy for policy in policies}
    definitions = list_job_definitions()
    if not definitions:
        return {
            'job_catalog': [],
            'selected_job': None,
            'configuration_stats': {'registered': 0, 'enabled': 0, 'active': 0, 'attention': 0},
        }

    definition_by_key = {definition.key: definition for definition in definitions}
    selected_key = selected_job_key if selected_job_key in definition_by_key else definitions[0].key
    active_job_keys = {
        (job_type, operation)
        for job_type, operation in JobExecution.query.with_entities(
            JobExecution.job_type,
            JobExecution.operation,
        )
        .filter(
            JobExecution.status.in_(ACTIVE_JOB_STATUSES),
            JobExecution.completed_at.is_(None),
        )
        .distinct()
        .all()
    }
    catalog = [
        _catalog_row(
            definition,
            policy_by_key[definition.key],
            active_job_keys=active_job_keys,
        )
        for definition in definitions
    ]

    selected_definition = definition_by_key[selected_key]
    selected_policy = policy_by_key[selected_key]
    selected_context = {
        'definition': selected_definition,
        'policy': selected_policy,
        **selected_definition.build_context(selected_policy),
    }
    execution_presentation = {
        'kubernetes.inventory.sync': {
            'manual_action_label': 'Sync All Inventory',
            'manual_action_icon': 'database-zap',
            'execution_scope_label': 'All Eligible Clusters',
            'execution_scope_detail': (
                f"{selected_context.get('eligible_cluster_count', 0)} eligible cluster bindings"
            ),
        },
        'governance.tls_certificates.sync': {
            'manual_action_label': 'Sync TLS Now',
            'manual_action_icon': 'refresh-cw',
            'execution_scope_label': 'Eligible TLS Clusters',
            'execution_scope_detail': (
                f"{selected_context.get('eligible_cluster_count', 0)} eligible cluster bindings"
            ),
        },
        'analytics.materialize': {
            'manual_action_label': 'Run Analytics Refresh',
            'manual_action_icon': 'chart-no-axes-combined',
            'execution_scope_label': 'Configured Analytics Snapshots',
            'execution_scope_detail': (
                f"{selected_context.get('dataset_count', 0)} dataset families across "
                f"{selected_context.get('eligible_cluster_count', 0)} clusters"
            ),
        },
        'analytics.forecast.materialize': {
            'manual_action_label': 'Run Forecast Refresh',
            'manual_action_icon': 'chart-spline',
            'execution_scope_label': 'Configured Forecast Snapshots',
            'execution_scope_detail': (
                f"{selected_context.get('dataset_count', 0)} forecast dataset across "
                f"{selected_context.get('eligible_cluster_count', 0)} clusters"
            ),
        },
    }
    selected_context.update(
        execution_presentation.get(
            selected_definition.key,
            {
                'manual_action_label': 'Run Now',
                'manual_action_icon': 'play',
                'execution_scope_label': selected_definition.scope_key,
                'execution_scope_detail': selected_definition.scope_type.replace('_', ' ').title(),
            },
        )
    )
    selected_context['execution_disabled'] = not bool(
        selected_context.get('eligible_cluster_count', 1)
    )
    enabled_count = sum(1 for policy in policies if policy.enabled)
    attention_count = sum(
        1 for policy in policies if policy.last_dispatch_status in _ATTENTION_DISPATCH_STATUSES
    )
    active_executions = JobExecution.query.filter(
        JobExecution.status.in_(ACTIVE_JOB_STATUSES),
        JobExecution.completed_at.is_(None),
    ).count()
    return {
        'job_catalog': catalog,
        'selected_job_key': selected_key,
        'selected_job': selected_context,
        'configuration_stats': {
            'registered': len(definitions),
            'enabled': enabled_count,
            'active': active_executions,
            'attention': attention_count,
        },
        'configuration_refreshed_at': present_user_datetime(datetime.now(UTC), empty='Just Now'),
    }
