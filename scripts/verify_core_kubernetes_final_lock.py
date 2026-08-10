#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    errors: list[str] = []

    lock_doc = ROOT / 'docs/design/KAORI_CORE_KUBERNETES_LOCK_V1.md'
    audit_doc = ROOT / 'docs/design/audits/KAORI_CORE_KUBERNETES_FINAL_LOCK_AUDIT_2026_08_08.md'
    require(lock_doc.exists(), 'Missing KAORI Core Kubernetes final lock document.', errors)
    require(audit_doc.exists(), 'Missing KAORI Core Kubernetes final lock audit.', errors)

    if lock_doc.exists():
        lock = lock_doc.read_text(encoding='utf-8')
        for label in (
            'Welcome',
            'Kubernetes Dashboard',
            'Kubernetes Inventory',
            'Kubernetes Analytics',
            'Kubernetes Operations',
            'Kubernetes Governance',
        ):
            require(label in lock, f'Final lock document must include {label}.', errors)
        require('Status: Final Lock v1' in lock, 'Core Kubernetes lock document must declare Final Lock v1.', errors)
        require('Default table page size is 5' in lock, 'Final lock must freeze the canonical page-size rule.', errors)
        require('5 / 10 / 25 / 50' in lock, 'Final lock must freeze the canonical page-size options.', errors)
        require('Title Case' in lock, 'Final lock must freeze the Title Case contract.', errors)
        require('dark mode' in lock.lower(), 'Final lock must freeze dark-mode behavior.', errors)

    ui_lock = read('scripts/verify_core_workspace_ui_lock.py')
    require(
        "'app/templates/dashboards/kubernetes/'" in ui_lock,
        'Kubernetes Dashboard templates must be protected by the core UI lock.',
        errors,
    )

    quality_gate = read('scripts/quality_gate.sh')
    for verifier_name in (
        'verify_welcome_final_lock.py',
        'verify_core_kubernetes_final_lock.py',
        'verify_analytics_compact_label_standard.py',
        'verify_operational_dashboard_standard.py',
        'verify_inventory_final_lock.py',
        'verify_node_inventory_standard.py',
        'verify_namespace_inventory_standard.py',
        'verify_configuration_inventory_standard.py',
        'verify_workload_inventory_standard.py',
        'verify_pod_inventory_standard.py',
        'verify_service_inventory_standard.py',
        'verify_ingress_inventory_standard.py',
        'verify_storage_inventory_standard.py',
        'verify_tls_certificate_governance_standard.py',
        'verify_core_workspace_legacy_cleanup.py',
        'verify_core_workspace_ui_lock.py',
        'verify_dark_mode_standard.py',
    ):
        require(verifier_name in quality_gate, f'quality_gate.sh must run {verifier_name}.', errors)

    # Welcome: canonical shared hero and domain catalog, no legacy standalone shell.
    welcome = read('app/templates/welcome/index.html')
    require('components/page_hero.html' in welcome, 'Welcome must use shared page_hero.', errors)
    require(
        'WELCOME_WORKSPACE_CATALOG' not in welcome,
        'Welcome must not depend on a legacy inline catalog constant.',
        errors,
    )

    # Kubernetes Dashboard: canonical snapshot-only composition and no obsolete builder.
    dashboard = read('app/templates/dashboards/kubernetes/index.html')
    dashboard_content = read('app/templates/dashboards/kubernetes/partials/_content.html')
    require(
        'dashboards/kubernetes/partials/_content.html' in dashboard,
        'Kubernetes Dashboard must use the canonical content partial.',
        errors,
    )
    require(
        'id="dashboard-content"' in dashboard and 'Kubernetes Dashboard Sections' in dashboard_content,
        'Kubernetes Dashboard must expose its canonical content and section navigation boundary.',
        errors,
    )
    require(
        not (ROOT / 'app/dashboards/kubernetes/snapshot_builder.py').exists(),
        'Obsolete Kubernetes dashboard snapshot_builder.py must remain removed.',
        errors,
    )

    # Inventory: canonical workspaces, snapshot semantics, topology drawer contract, no compatibility scopes.
    for resource in ('nodes', 'namespaces', 'configuration', 'workloads', 'pods', 'services', 'ingresses', 'storage'):
        workspace = ROOT / f'app/templates/inventory/{resource}/partials/_page_workspace.html'
        require(workspace.exists(), f'Inventory {resource} canonical workspace is missing.', errors)
        legacy = ROOT / f'app/templates/inventory/{resource}/partials/_inventory_scope.html'
        require(not legacy.exists(), f'Inventory {resource} legacy _inventory_scope.html must remain removed.', errors)
    topology = read('app/templates/inventory/topology/partials/_workspace.html')
    require('visualization_workspace.render(' in topology, 'Topology must use shared visualization workspace.', errors)
    require(
        'topology-controls-panel' in topology and 'topology-details-panel' in topology,
        'Topology controls/details must remain on-demand drawers.',
        errors,
    )

    # Analytics: shared token scope, canonical guidance ownership, and obsolete local assets removed.
    for domain in ('overview', 'utilization', 'capacity', 'storage', 'workload', 'forecast', 'top_consumers', 'alerts'):
        index = read(f'app/templates/analytics/{domain}/index.html')
        require(
            'kaori-analytics-page' in index, f'Analytics {domain} must use the shared analytics token scope.', errors
        )
    require(
        not (ROOT / 'app/static/js/analytics_capacity.js').exists(),
        'Obsolete analytics_capacity.js must remain removed.',
        errors,
    )
    require(
        not (ROOT / 'app/static/js/analytics_forecast.js').exists(),
        'Obsolete analytics_forecast.js must remain removed.',
        errors,
    )
    surfaces = read('app/templates/analytics/components/_analysis_surfaces.html')
    require(
        'macro interpretation_callout' in surfaces and 'macro interpretation_content' in surfaces,
        'Analytics guidance must remain owned by shared analysis surfaces.',
        errors,
    )

    # Operations: live-operation feedback remains shared and legacy wrappers stay removed.
    for obsolete in (
        'app/templates/kubernetes_operations/_components.html',
        'app/templates/kubernetes_operations/configmaps/_operation_notification.html',
        'app/kubernetes_operations/secrets/routes.py',
    ):
        require(not (ROOT / obsolete).exists(), f'Obsolete Operations path must remain removed: {obsolete}', errors)
    configmap_create = read('app/templates/kubernetes_operations/configmaps/create.html')
    require(
        'data-operational-toast' in read('app/templates/components/operational_toast.html'),
        'Shared operational toast component must remain available.',
        errors,
    )
    require(
        '_validation_preview.html' in configmap_create,
        'ConfigMap create must preserve persistent validation evidence.',
        errors,
    )

    # Governance: canonical TLS workspace + guarded mutation and no legacy feedback wrappers.
    governance = read('app/templates/governance/tls_certificates/index.html')
    require('tls_certificates' in governance.lower(), 'TLS Governance canonical workspace is missing.', errors)
    for obsolete in (
        'app/templates/governance/tls_certificates/partials/_operation_feedback_oob.html',
        'app/templates/governance/tls_certificates/partials/_sync_toast_oob.html',
        'app/templates/governance/tls_certificates/partials/_inventory_scope.html',
        'app/governance/tls_certificates/toast.py',
    ):
        require(not (ROOT / obsolete).exists(), f'Obsolete Governance path must remain removed: {obsolete}', errors)

    cleanup = read('scripts/cleanup_obsolete_files.sh')
    for obsolete in (
        'app/dashboards/kubernetes/snapshot_builder.py',
        'app/static/js/analytics_capacity.js',
        'app/static/js/analytics_forecast.js',
        'app/templates/kubernetes_operations/_components.html',
        'app/templates/governance/tls_certificates/partials/_inventory_scope.html',
        'app/static/js/inventory/topology_bootstrap.js',
    ):
        require(f"'{obsolete}'" in cleanup, f'Cleanup script must retain obsolete-path guard: {obsolete}', errors)

    if errors:
        for error in errors:
            print(f'ERROR: {error}')
        return 1

    print(
        'KAORI Core Kubernetes Final Lock v1 passed: Welcome, Kubernetes Dashboard, Inventory, Analytics, '
        'Operations, and Governance are documented, verifier-protected, and legacy cleanup guardrails are active.'
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
