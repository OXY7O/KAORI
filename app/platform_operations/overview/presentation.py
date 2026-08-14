from __future__ import annotations

from typing import Any

from app.jobs.presentation import build_job_execution_status_context
from app.platform_operations.data_lifecycle.presentation import build_data_lifecycle_overview_summary
from app.platform_operations.kubernetes.presentation import build_kubernetes_administration_summary


def _count_value(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return 0
    return 0


def build_platform_operations_overview_context(
    *,
    can_jobs: bool,
    can_data_lifecycle: bool,
    can_kubernetes_admin: bool,
) -> dict[str, Any]:
    """Build a read-only summary across Platform Operations control planes.

    Each domain remains authoritative for its own presentation semantics. The
    overview only composes compact posture projections and never performs a
    mutation or creates an alternate execution/lifecycle source of truth.
    """

    workspaces: list[dict[str, Any]] = []

    if can_jobs:
        job_context = build_job_execution_status_context()
        job_stats = job_context['job_stats']
        attention = _count_value(job_stats.get('attention', 0))
        active = _count_value(job_stats.get('active', 0))
        if attention:
            status_label, status_tone = 'Needs Attention', 'warning'
        elif active:
            status_label, status_tone = 'Active', 'info'
        else:
            status_label, status_tone = 'Ready', 'normal'
        workspaces.append(
            {
                'key': 'jobs',
                'label': 'Jobs & Executions',
                'icon': 'list-checks',
                'description': 'Canonical execution, retry, cancellation, queue, and worker evidence.',
                'status_label': status_label,
                'status_tone': status_tone,
                'metrics': (
                    ('activity', 'Active', active),
                    ('triangle-alert', 'Attention', attention),
                    ('circle-check', 'Completed · 24H', _count_value(job_stats.get('completed_24h', 0))),
                ),
                'action_endpoint': 'jobs.executions',
                'action_label': 'Open Jobs & Executions',
                'boundary_label': 'Canonical execution evidence',
            }
        )

    if can_data_lifecycle:
        lifecycle = build_data_lifecycle_overview_summary()
        if lifecycle['failed_archive_24h']:
            status_label, status_tone = 'Needs Attention', 'warning'
        elif lifecycle['active_archive_total'] or lifecycle['active_job_total']:
            status_label, status_tone = 'Active', 'info'
        elif lifecycle['enabled_domain_count']:
            status_label, status_tone = 'Ready', 'normal'
        else:
            status_label, status_tone = 'Policies Disabled', 'unknown'
        workspaces.append(
            {
                'key': 'data-lifecycle',
                'label': 'Data Lifecycle',
                'icon': 'archive-restore',
                'description': 'Retention policy, verified archive evidence, and safe cleanup boundaries.',
                'status_label': status_label,
                'status_tone': status_tone,
                'metrics': (
                    (
                        'shield-check',
                        'Policies Enabled',
                        f'{lifecycle["enabled_domain_count"]} / {lifecycle["managed_domain_count"]}',
                    ),
                    ('archive', 'Active Archives', lifecycle['active_archive_total']),
                    ('circle-x', 'Failed · 24H', lifecycle['failed_archive_24h']),
                ),
                'action_endpoint': 'platform_operations.data_lifecycle.index',
                'action_label': 'Open Data Lifecycle',
                'boundary_label': 'Archive-first governance',
            }
        )

    if can_kubernetes_admin:
        kubernetes = build_kubernetes_administration_summary()
        cluster_count = _count_value(kubernetes.get('cluster_count', 0))
        ready_count = _count_value(kubernetes.get('ready_cluster_count', 0))
        protected_namespaces = _count_value(kubernetes.get('enabled_namespace_count', 0))
        global_enabled = bool(kubernetes['global_reveal_enabled'])
        if cluster_count == 0:
            status_label, status_tone = 'No Clusters', 'unknown'
        elif protected_namespaces and not global_enabled:
            status_label, status_tone = 'Global Gate Disabled', 'warning'
        elif ready_count < cluster_count:
            status_label, status_tone = 'Readiness Review', 'warning'
        else:
            status_label, status_tone = 'Ready', 'normal'
        workspaces.append(
            {
                'key': 'kubernetes',
                'label': 'Kubernetes Administration',
                'icon': 'server-cog',
                'description': 'Protected Kubernetes controls with explicit readiness and authorization boundaries.',
                'status_label': status_label,
                'status_tone': status_tone,
                'metrics': (
                    ('badge-check', 'Ready Clusters', f'{ready_count} / {cluster_count}'),
                    ('boxes', 'Protected Namespaces', protected_namespaces),
                    ('shield', 'Global Reveal', 'Enabled' if global_enabled else 'Disabled'),
                ),
                'action_endpoint': 'platform_operations.kubernetes.index',
                'action_label': 'Open Kubernetes Administration',
                'boundary_label': 'Protected control boundary',
            }
        )

    attention_workspace_count = sum(
        1 for workspace in workspaces if workspace['status_tone'] in {'warning', 'critical'}
    )
    active_workspace_count = sum(1 for workspace in workspaces if workspace['status_tone'] == 'info')

    return {
        'workspaces': workspaces,
        'workspace_count': len(workspaces),
        'attention_workspace_count': attention_workspace_count,
        'active_workspace_count': active_workspace_count,
        'overall_status_label': (
            'Review Required' if attention_workspace_count else ('Active' if active_workspace_count else 'Ready')
        ),
        'overall_status_tone': (
            'warning' if attention_workspace_count else ('info' if active_workspace_count else 'normal')
        ),
        'can_jobs': can_jobs,
        'can_data_lifecycle': can_data_lifecycle,
        'can_kubernetes_admin': can_kubernetes_admin,
    }
