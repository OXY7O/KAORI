from __future__ import annotations

from typing import Any

from app.infrastructure_automation.workspace import automation_connection_count
from app.platform_operations.data_lifecycle.presentation import build_data_lifecycle_overview_summary
from app.platform_operations.jobs.configuration import build_job_configuration_attention_summary
from app.platform_operations.jobs.presentation import build_job_execution_status_context
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


def _overall_workspace_status(
    critical_count: int, warning_count: int, unknown_count: int, active_count: int
) -> tuple[str, str]:
    """Determine the aggregate badge from the authoritative workspace tones."""
    if critical_count:
        return 'Critical Review', 'critical'
    if warning_count:
        return 'Review Required', 'warning'
    if unknown_count:
        return 'Configuration Review', 'unknown'
    if active_count:
        return 'Active', 'info'
    return 'Ready', 'normal'


def build_platform_operations_overview_context(
    *,
    can_jobs: bool,
    can_data_lifecycle: bool,
    can_infrastructure_automation: bool = False,
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
        policy_attention = build_job_configuration_attention_summary()
        active = _count_value(job_stats.get('active', 0))
        if attention or policy_attention:
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
                'description': 'Canonical execution and worker evidence.',
                'status_label': status_label,
                'status_tone': status_tone,
                'metrics': (
                    ('activity', 'Active', active, 'Active'),
                    (
                        'triangle-alert',
                        'Exec / Policy',
                        f'{attention} / {policy_attention}',
                        'Execution / Policy Alerts',
                    ),
                    (
                        'circle-check',
                        'Completed · 24H',
                        _count_value(job_stats.get('completed_24h', 0)),
                        'Completed · 24H',
                    ),
                ),
                'action_endpoint': ('jobs.configuration' if policy_attention and not attention else 'jobs.executions'),
                'action_label': (
                    'Review Job Configuration' if policy_attention and not attention else 'Open Jobs & Executions'
                ),
                'boundary_label': 'Canonical execution evidence',
                'boundary_title': 'Execution Evidence',
                'boundary_description': 'Jobs owns queues, retries and execution evidence.',
            }
        )

    if can_infrastructure_automation:
        connections = automation_connection_count()
        workspaces.append(
            {
                'key': 'infrastructure-automation',
                'label': 'Infrastructure Automation',
                'icon': 'server-cog',
                'description': 'Read-only Ansible source, preflight, Plan and cluster evidence.',
                'status_label': 'Review Required' if connections else 'Not Configured',
                'status_tone': 'unknown',
                'metrics': (
                    ('blocks', 'Ansible Connections', connections, 'Canonical Connections'),
                    ('lock-keyhole', 'Mutation', 'Blocked', 'Execution Authority'),
                    ('clipboard-list', 'Pilot Profile', 'Kubespray', 'Registered Source Profile'),
                ),
                'action_endpoint': 'platform_operations.infrastructure_automation.index',
                'action_label': 'Open Infrastructure Automation',
                'boundary_label': 'Git-defined Ansible operations',
                'boundary_title': 'Committed Automation Evidence',
                'boundary_description': 'Infrastructure Automation orchestrates, never executes during page loads.',
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
                'description': 'Retention, verified archives, and safe cleanup.',
                'status_label': status_label,
                'status_tone': status_tone,
                'metrics': (
                    (
                        'shield-check',
                        'Policies Enabled',
                        f'{lifecycle["enabled_domain_count"]} / {lifecycle["managed_domain_count"]}',
                        'Policies Enabled',
                    ),
                    (
                        'archive',
                        'Archives / Jobs',
                        f'{lifecycle["active_archive_total"]} / {lifecycle["active_job_total"]}',
                        'Active Archives / Jobs',
                    ),
                    ('circle-x', 'Failed · 24H', lifecycle['failed_archive_24h'], 'Failed · 24H'),
                ),
                'action_endpoint': 'platform_operations.data_lifecycle.index',
                'action_label': 'Open Data Lifecycle',
                'boundary_label': 'Archive-first governance',
                'boundary_title': 'Lifecycle Governance',
                'boundary_description': 'Data Lifecycle owns retention and verified archives.',
            }
        )

    if can_kubernetes_admin:
        kubernetes = build_kubernetes_administration_summary()
        cluster_count = _count_value(kubernetes.get('cluster_count', 0))
        ready_count = _count_value(kubernetes.get('ready_cluster_count', 0))
        protected_namespaces = _count_value(kubernetes.get('enabled_namespace_count', 0))
        global_enabled = bool(kubernetes['global_reveal_enabled'])
        # Kubernetes Administration is authoritative for protected-reveal
        # prerequisites. Do not infer Ready from cluster counts alone.
        status_label = str(kubernetes['administration_status_label'])
        status_tone = str(kubernetes['administration_status_tone'])
        workspaces.append(
            {
                'key': 'kubernetes',
                'label': 'Kubernetes Administration',
                'icon': 'server-cog',
                'description': 'Readiness and protected access controls.',
                'status_label': status_label,
                'status_tone': status_tone,
                'metrics': (
                    ('badge-check', 'Ready Clusters', f'{ready_count} / {cluster_count}', 'Ready Clusters'),
                    ('boxes', 'Protected NS', protected_namespaces, 'Protected Namespaces'),
                    ('shield', 'Global Reveal', 'Enabled' if global_enabled else 'Disabled', 'Global Reveal'),
                ),
                'action_endpoint': 'platform_operations.kubernetes.index',
                'action_label': 'Open Kubernetes Administration',
                'boundary_label': 'Protected control boundary',
                'boundary_title': 'Protected Administration',
                'boundary_description': 'Kubernetes governs readiness and reveal access.',
            }
        )

    critical_workspace_count = sum(1 for workspace in workspaces if workspace['status_tone'] == 'critical')
    warning_workspace_count = sum(1 for workspace in workspaces if workspace['status_tone'] == 'warning')
    unknown_workspace_count = sum(1 for workspace in workspaces if workspace['status_tone'] == 'unknown')
    attention_workspace_count = critical_workspace_count + warning_workspace_count
    review_workspace_count = attention_workspace_count + unknown_workspace_count
    active_workspace_count = sum(1 for workspace in workspaces if workspace['status_tone'] == 'info')

    overall_status_label, overall_status_tone = _overall_workspace_status(
        critical_workspace_count, warning_workspace_count, unknown_workspace_count, active_workspace_count
    )

    return {
        'workspaces': workspaces,
        'workspace_count': len(workspaces),
        'attention_workspace_count': attention_workspace_count,
        'review_workspace_count': review_workspace_count,
        'active_workspace_count': active_workspace_count,
        'overall_status_label': overall_status_label,
        'overall_status_tone': overall_status_tone,
        'can_jobs': can_jobs,
        'can_data_lifecycle': can_data_lifecycle,
        'can_kubernetes_admin': can_kubernetes_admin,
    }
