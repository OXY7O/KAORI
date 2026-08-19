from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.common.job_execution_presentation import present_job_execution
from app.common.presentation import present_user_datetime
from app.models.job import JobExecution, JobPolicy
from app.platform_operations.jobs.constants import ACTIVE_JOB_STATUSES
from app.platform_operations.jobs.definitions.base import JobDefinition
from app.platform_operations.jobs.policies.presentation import present_interval
from app.platform_operations.jobs.policies.service import ensure_registered_job_policies
from app.platform_operations.jobs.registry import list_job_definitions

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


def _execution_presentation(definition: JobDefinition, selected_context: dict[str, Any]) -> dict[str, str]:
    presentation = {
        'kubernetes.inventory.sync': {
            'manual_action_label': 'Sync Kubernetes Inventory',
            'manual_action_icon': 'database-zap',
            'execution_scope_label': 'All Eligible Clusters',
            'execution_scope_detail': f'{selected_context.get("eligible_cluster_count", 0)} eligible cluster bindings',
        },
        'object_storage.inventory.sync': {
            'manual_action_label': 'Sync Object Storage Inventory',
            'manual_action_icon': 'database-zap',
            'execution_scope_label': 'All Eligible Storage Systems',
            'execution_scope_detail': f'{selected_context.get("eligible_system_count", 0)} Ready managed systems',
        },
        'governance.tls_certificates.sync': {
            'manual_action_label': 'Sync TLS',
            'manual_action_icon': 'refresh-cw',
            'execution_scope_label': 'Eligible TLS Clusters',
            'execution_scope_detail': f'{selected_context.get("eligible_cluster_count", 0)} eligible cluster bindings',
        },
        'analytics.materialize': {
            'manual_action_label': 'Refresh Analytics',
            'manual_action_icon': 'chart-no-axes-combined',
            'execution_scope_label': 'Configured Analytics Snapshots',
            'execution_scope_detail': (
                f'{selected_context.get("dataset_count", 0)} dataset families across '
                f'{selected_context.get("eligible_cluster_count", 0)} clusters'
            ),
        },
        'object_storage.analytics.materialize': {
            'manual_action_label': 'Refresh Object Storage Analytics',
            'manual_action_icon': 'chart-no-axes-combined',
            'execution_scope_label': 'Configured Object Storage Snapshots',
            'execution_scope_detail': (
                f'{selected_context.get("dataset_count", 0)} time ranges across '
                f'{selected_context.get("eligible_system_count", 0)} systems'
            ),
        },
        'reports.schedule.dispatch': {
            'manual_action_label': 'Process Due Reports',
            'manual_action_icon': 'file-clock',
            'execution_scope_label': 'Enabled Report Schedules',
            'execution_scope_detail': (
                f'{selected_context.get("active_schedule_count", 0)} enabled schedule definitions'
            ),
        },
        'analytics.forecast.materialize': {
            'manual_action_label': 'Refresh Forecast',
            'manual_action_icon': 'chart-spline',
            'execution_scope_label': 'Configured Forecast Snapshots',
            'execution_scope_detail': (
                f'{selected_context.get("dataset_count", 0)} forecast dataset across '
                f'{selected_context.get("eligible_cluster_count", 0)} clusters'
            ),
        },
        'object_storage.forecast.materialize': {
            'manual_action_label': 'Refresh Object Storage Forecast',
            'manual_action_icon': 'chart-spline',
            'execution_scope_label': 'Eligible Object Storage Forecasts',
            'execution_scope_detail': (
                f'{selected_context.get("dataset_count", 0)} history windows across '
                f'{selected_context.get("eligible_system_count", 0)} systems'
            ),
        },
    }
    return presentation.get(
        definition.key,
        {
            'manual_action_label': 'Run Now',
            'manual_action_icon': 'play',
            'execution_scope_label': definition.scope_key,
            'execution_scope_detail': definition.scope_type.replace('_', ' ').title(),
        },
    )


def _selected_job_context(definition: JobDefinition, policy: JobPolicy) -> dict[str, Any]:
    selected_context = {
        'definition': definition,
        'policy': policy,
        **definition.build_context(policy),
    }
    selected_context.update(_execution_presentation(definition, selected_context))
    eligible_target_count = selected_context.setdefault(
        'eligible_target_count', selected_context.get('eligible_cluster_count', 1)
    )
    selected_context['execution_disabled'] = not bool(eligible_target_count)
    return selected_context


def build_job_configuration_summary_context(*, active_execution_count: int | None = None) -> dict[str, Any]:
    """Return header-level configuration counters without invoking any domain context builder."""
    policies = ensure_registered_job_policies()
    definitions = list_job_definitions()
    enabled_count = sum(1 for policy in policies if policy.enabled)
    attention_count = sum(1 for policy in policies if policy.last_dispatch_status in _ATTENTION_DISPATCH_STATUSES)
    if active_execution_count is None:
        active_execution_count = JobExecution.query.filter(
            JobExecution.status.in_(ACTIVE_JOB_STATUSES),
            JobExecution.completed_at.is_(None),
        ).count()
    return {
        'configuration_stats': {
            'registered': len(definitions),
            'enabled': enabled_count,
            'active': int(active_execution_count or 0),
            'attention': attention_count,
        },
    }


def build_job_configuration_live_context(*, selected_job_key: str) -> dict[str, Any]:
    """Refresh one selected job without repeating domain eligibility work while it is active."""
    policies = ensure_registered_job_policies()
    definitions = list_job_definitions()
    policy_by_key = {policy.job_key: policy for policy in policies}
    definition_by_key = {definition.key: definition for definition in definitions}
    definition = definition_by_key.get(selected_job_key)
    if definition is None:
        raise LookupError(f'Unknown registered job: {selected_job_key}')
    policy = policy_by_key[definition.key]
    jobs = JobExecution.query.filter(
        JobExecution.job_type == definition.job_type,
        JobExecution.operation == definition.operation,
    )
    active = (
        jobs.filter(
            JobExecution.status.in_(ACTIVE_JOB_STATUSES),
            JobExecution.completed_at.is_(None),
        )
        .order_by(JobExecution.updated_at.desc(), JobExecution.id.desc())
        .first()
    )
    if active is None:
        selected_context = _selected_job_context(definition, policy)
        active_job_keys: set[tuple[str, str]] = set()
    else:
        recent_jobs = jobs.order_by(JobExecution.created_at.desc(), JobExecution.id.desc()).limit(5).all()
        selected_context = {
            'definition': definition,
            'policy': policy,
            'active_job': present_job_execution(active),
            'recent_jobs': [present_job_execution(job) for job in recent_jobs],
            'execution_state': {
                'label': 'Execution Active',
                'tone': 'pending',
                'icon': 'loader-circle',
                'description': 'The canonical worker execution is still active.',
            },
            'configuration_state': {
                'label': 'Execution Active',
                'tone': 'pending',
                'icon': 'loader-circle',
            },
            'execution_disabled': True,
            **_execution_presentation(definition, {}),
        }
        active_job_keys = {(definition.job_type, definition.operation)}
    return {
        'job_catalog': [_catalog_row(definition, policy, active_job_keys=active_job_keys)],
        'selected_job_key': definition.key,
        'selected_job': selected_context,
        'configuration_refreshed_at': present_user_datetime(datetime.now(UTC), empty='Just Now'),
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
    selected_context = _selected_job_context(selected_definition, selected_policy)
    summary = build_job_configuration_summary_context(active_execution_count=len(active_job_keys))
    return {
        'job_catalog': catalog,
        'selected_job_key': selected_key,
        'selected_job': selected_context,
        **summary,
        'configuration_refreshed_at': present_user_datetime(datetime.now(UTC), empty='Just Now'),
    }
