from __future__ import annotations

from flask import current_app

from app.platform_operations.kubernetes.read_model import administration_counts


def _administration_posture(
    *,
    cluster_count: int,
    ready_cluster_count: int,
    enabled_namespace_count: int,
    global_reveal_enabled: bool,
    eligible_policy_count: int = 0,
) -> tuple[str, str, str]:
    if cluster_count == 0:
        return (
            'Setup Required',
            'warning',
            'Register a Kubernetes connection before configuring protected administration.',
        )
    if not global_reveal_enabled:
        return (
            'Global Gate Disabled',
            'warning',
            'Protected Secret Reveal remains unavailable until the global feature gate is enabled.',
        )
    if ready_cluster_count == 0:
        return (
            'Readiness Review',
            'warning',
            'No connected cluster currently satisfies all Protected Secret Reveal prerequisites.',
        )
    if ready_cluster_count < cluster_count:
        return (
            'Partial Readiness',
            'warning',
            f'{ready_cluster_count} of {cluster_count} registered clusters have configured Reveal prerequisites.',
        )
    if enabled_namespace_count == 0:
        return (
            'Policy Required',
            'warning',
            'Cluster prerequisites are ready; enable at least one namespace policy to admit protected reveal.',
        )
    if eligible_policy_count == 0:
        return (
            'Policy Scope Review',
            'warning',
            'Enabled namespace policies are not attached to a cluster with configured Reveal prerequisites.',
        )
    return (
        'Verification Required',
        'warning',
        'Cluster prerequisites and eligible namespace policies are configured. Live Namespace presence, Kubernetes RBAC, and Secret identity are verified only at execution.',
    )


def build_kubernetes_administration_summary() -> dict[str, object]:
    """Return the lightweight Kubernetes Administration posture projection."""

    counts = administration_counts()
    global_reveal_enabled = bool(current_app.config.get('KUBERNETES_SECRET_REVEAL_ENABLED', False))
    status_label, status_tone, status_detail = _administration_posture(
        cluster_count=counts['cluster_count'],
        ready_cluster_count=counts['ready_cluster_count'],
        enabled_namespace_count=counts['enabled_namespace_count'],
        global_reveal_enabled=global_reveal_enabled,
        eligible_policy_count=counts['eligible_policy_count'],
    )
    # Capability-first overview: expose only controls actually implemented for
    # this permission-gated workspace. Additional approved domains append their
    # own source-owned posture here, not placeholder roadmap cards in Jinja.
    controls = (
        {
            'key': 'secret-reveal',
            'label': 'Protected Secret Reveal',
            'icon': 'scan-eye',
            'description': 'Govern one-time Secret access through cluster prerequisites and Namespace policy.',
            'status_label': status_label,
            'status_tone': status_tone,
            'status_detail': status_detail,
            'workspace_tab': 'secret-reveal',
            'action_label': 'Configure Secret Reveal',
            'metrics': (
                (
                    'badge-check',
                    'Cluster Prerequisites',
                    f'{counts["ready_cluster_count"]} / {counts["cluster_count"]}',
                ),
                (
                    'boxes',
                    'Configured Policy Scope',
                    f'{counts["eligible_policy_count"]} / {counts["enabled_namespace_count"]}',
                ),
            ),
            'evidence_label': 'Configured KAORI state; runtime authorization is verified at execution.',
        },
    )
    return {
        'cluster_count': counts['cluster_count'],
        'ready_cluster_count': counts['ready_cluster_count'],
        'enabled_namespace_count': counts['enabled_namespace_count'],
        'eligible_policy_count': counts['eligible_policy_count'],
        'global_reveal_enabled': global_reveal_enabled,
        'administration_status_label': status_label,
        'administration_status_tone': status_tone,
        'administration_status_detail': status_detail,
        'administration_controls': controls,
        'administration_control_count': len(controls),
    }
