#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

INTEGRATION_TEMPLATE_ROOTS = (
    Path('app/templates/integrations'),
    Path('app/templates/integrations/observability/metrics_source'),
    Path('app/templates/integrations/observability/alert_source/providers/alertmanager'),
)

RAW_HEX = re.compile(r'(?<![\w-])#[0-9a-fA-F]{3,8}\b')
RAW_PALETTE = re.compile(
    r'\b(?:bg|text|border|ring|shadow|fill|stroke)-'
    r'(?:red|green|blue|amber|yellow|gray|slate|zinc|neutral|stone|indigo|purple|violet|pink|rose|cyan|teal|emerald|lime|orange|sky)-'
    r'\d{2,3}(?:/\d{1,3})?\b'
)
INLINE_STYLE = re.compile(r'\bstyle\s*=', re.I)
INLINE_HANDLER = re.compile(r'\bon(?:click|change|input|submit|load|error|keyup|keydown)\s*=', re.I)


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def integration_templates() -> list[Path]:
    paths: list[Path] = []
    for relative in INTEGRATION_TEMPLATE_ROOTS:
        base = ROOT / relative
        if base.exists():
            paths.extend(base.rglob('*.html'))
    return sorted(set(paths))


def main() -> int:
    errors: list[str] = []
    checked_templates = 0

    # Locked Integration templates must stay tokenized and free from inline UI debt.
    for path in integration_templates():
        checked_templates += 1
        relative = path.relative_to(ROOT).as_posix()
        source = path.read_text(encoding='utf-8')
        require(not RAW_HEX.search(source), f'{relative}: raw hex color is forbidden', errors)
        require(not RAW_PALETTE.search(source), f'{relative}: raw Tailwind palette utility is forbidden', errors)
        require(not INLINE_STYLE.search(source), f'{relative}: inline style is forbidden', errors)
        require(not INLINE_HANDLER.search(source), f'{relative}: inline DOM event handler is forbidden', errors)

    # Capability readiness is one shared presentation contract across all providers.
    readiness = read('app/templates/integrations/components/_capability_readiness.html')
    require('data-kaori-capability-readiness' in readiness, 'Shared capability readiness marker is missing', errors)
    require('progress_bar.bar(' in readiness, 'Capability readiness must use the shared progress bar', errors)
    readiness_templates = []
    for path in integration_templates():
        relative = path.relative_to(ROOT).as_posix()
        source = path.read_text(encoding='utf-8')
        if 'capability_readiness.render(' not in source:
            continue
        readiness_templates.append(relative)
        require(
            'integrations/components/_capability_readiness.html' in source,
            f'{relative}: must import shared capability readiness',
            errors,
        )
        require(
            'capability_readiness.render(' in source, f'{relative}: must render shared capability readiness', errors
        )
        metadata = source.split('{% set capability_metadata = [', 1)[1].split('] %}', 1)[0]
        require(
            'Profile · ' in metadata,
            f'{relative}: readiness metadata must expose one concise Profile identity',
            errors,
        )
        for retired_label in ('Compatibility · ', 'Core Profile · ', 'Core profile · ', 'Product · '):
            require(
                retired_label not in metadata,
                f'{relative}: readiness metadata must not expose redundant {retired_label.strip()} identity',
                errors,
            )
    require(
        len(readiness_templates) >= 4,
        'Shared provider capability readiness must remain wired across the registered provider families',
        errors,
    )

    # Metrics Source setup guidance reuses the canonical modal + integrated-tab hierarchy.
    metrics_configuration = read(
        'app/templates/integrations/observability/metrics_source/partials/_detail_configuration.html'
    )
    provider_configuration_contract = read(
        'app/templates/integrations/components/_provider_configuration_contract.html'
    )
    metrics_presentation = read('app/integrations/observability/metrics_source/application/presentation.py')
    metrics_validation = read(
        'app/templates/integrations/observability/metrics_source/partials/_detail_validation_content.html'
    )
    metrics_scope = read('app/templates/integrations/observability/metrics_source/partials/_detail_scope.html')
    metrics_examples = read(
        'app/templates/integrations/observability/metrics_source/partials/_minimum_validation_metrics.html'
    )
    metrics_registry = read(
        'app/templates/integrations/observability/metrics_source/partials/_capability_registry.html'
    )
    metrics_binding_registry = read(
        'app/templates/integrations/observability/metrics_source/partials/_binding_registry.html'
    )
    kubernetes_binding_validator = read(
        'app/integrations/observability/metrics_source/binding_validators/kubernetes.py'
    )
    feature_contracts = read('app/integrations/observability/metrics_source/query_profiles/feature_contracts.py')
    storage_parsing = read('app/kubernetes/analytics/storage/parsing.py')
    for token in (
        'Minimum Metrics Validation Example',
        'Open Metrics Examples',
        'components/workspace_tabs.html',
        "('identity', 'Prometheus / Thanos Identity', 'fingerprint')",
        "('filesystem', 'Node Filesystem Relabel', 'hard-drive')",
        'externalLabels:',
        'targetLabel: cluster',
        'replacement: k8s-production',
        'cluster: k8s-production',
        'targetLabel: node',
        '__meta_kubernetes_pod_node_name',
        'instance</code> label may remain for scrape diagnostics',
    ):
        require(token in metrics_examples, f'Metrics validation setup example missing canonical token: {token}', errors)
    require(
        'setup_reference_template="integrations/observability/metrics_source/partials/_minimum_validation_metrics.html"'
        in metrics_configuration
        and '<div class="mt-4">' not in metrics_configuration
        and '_minimum_validation_metrics.html' not in metrics_validation,
        'Metrics Source setup reference must use the shared in-contract Configuration slot rather than a detached card',
        errors,
    )
    setup_reference_index = provider_configuration_contract.find('{% include setup_reference_template %}')
    operational_context_index = provider_configuration_contract.find('operational_context.render')
    configuration_footer_index = provider_configuration_contract.find('<footer')
    require(
        'setup_reference_template=""' in provider_configuration_contract
        and 0 <= operational_context_index < setup_reference_index < configuration_footer_index,
        'Shared provider Configuration must place setup references after Operational Context and before the footer',
        errors,
    )
    binding_result = read('app/templates/integrations/components/_binding_validation_result.html')
    require(
        'Provider Core Capability' in metrics_registry
        and 'Consumer Contract Evidence' not in metrics_registry
        and 'capability_rows = provider_capability_rows' in metrics_presentation
        and '_consumer_validation_rows' not in metrics_presentation,
        'Metrics Source General Validation must remain provider-core only',
        errors,
    )
    require(
        '_binding_validation_result.html' in metrics_binding_registry
        and 'View More' in metrics_binding_registry
        and 'data-kaori-binding-view-more' in metrics_binding_registry
        and 'data-kaori-binding-actions' in metrics_binding_registry
        and 'Binding Validation Result' in binding_result
        and 'Consumer Capability Evidence' in binding_result,
        'Binding-specific capability evidence must remain owned by Bindings & Consumers',
        errors,
    )
    require(
        'Open Bindings & Consumers → View More on the affected binding for exact missing capability evidence and remediation.'
        in metrics_scope
        and 'Missing technical capability:' not in metrics_scope
        and 'Binding coverage missing:' not in metrics_scope,
        'Metrics Source Scope must show binding posture only; exact missing capability detail belongs to Validation',
        errors,
    )
    require(
        "next((matcher for matcher in matchers if matcher.label == 'cluster'), None)" in kubernetes_binding_validator,
        'Kubernetes Metrics binding validation must require the canonical cluster selector label',
        errors,
    )
    require(
        'client.label_values(cluster_matcher.label)' in kubernetes_binding_validator,
        'Kubernetes Metrics binding validation must verify the source cluster label against live evidence',
        errors,
    )
    require(
        'query-visible target label' in kubernetes_binding_validator
        and "provider_key == 'thanos'" in kubernetes_binding_validator,
        'Kubernetes Metrics binding remediation must distinguish direct-Prometheus query labels from Thanos external identity',
        errors,
    )
    require(
        "required_labels=('node',)" in feature_contracts,
        'Storage filesystem validation must require the canonical node label',
        errors,
    )
    require(
        'count by (node, mountpoint)' in feature_contracts,
        'Storage filesystem validation must pair evidence by canonical node + mountpoint',
        errors,
    )
    require(
        "metric.get('node')" in storage_parsing
        and 'nodename' not in storage_parsing
        and 'kubernetes_node' not in storage_parsing,
        'Storage Analytics parsing must consume only the canonical node label after validation',
        errors,
    )

    connection_header = read('app/templates/components/connection_validation_header.html')
    provider_configuration = read('app/templates/integrations/components/_provider_configuration_contract.html')
    alert_scope = read(
        'app/templates/integrations/observability/alert_source/providers/alertmanager/partials/_detail_scope.html'
    )
    minio_scope = read('app/templates/integrations/storage/object_storage/providers/minio/partials/_detail_scope.html')
    kubernetes_connection = read(
        'app/templates/integrations/orchestration/container_orchestrator/providers/kubernetes/partials/_connection_contract.html'
    )
    kubernetes_inventory = read(
        'app/templates/integrations/orchestration/container_orchestrator/providers/kubernetes/partials/_inventory_lifecycle.html'
    )
    primary_title = 'text-base font-semibold text-content-primary'
    primary_description = 'text-sm leading-6 text-content-secondary'
    require(
        primary_title in connection_header
        and 'mt-1 max-w-3xl text-sm leading-6 text-content-secondary' in connection_header
        and primary_title in provider_configuration
        and 'mt-1 max-w-3xl text-sm leading-6 text-content-secondary' in provider_configuration
        and primary_title in metrics_scope
        and primary_description in metrics_scope
        and primary_title in alert_scope
        and primary_description in alert_scope
        and primary_title in minio_scope
        and primary_description in minio_scope
        and primary_title in kubernetes_connection
        and primary_description in kubernetes_connection
        and primary_title in kubernetes_inventory
        and primary_description in kubernetes_inventory,
        'Integration primary workspace typography must keep one title/description hierarchy across providers and tabs',
        errors,
    )
    require(
        'mt-0.5 max-w-2xl text-xs leading-5 text-content-muted' not in connection_header,
        'Integration primary workspace descriptions must not regress to secondary helper typography',
        errors,
    )

    # Capability registries use real HTMX interaction + one shared loading bar.
    registry_contracts = (
        (
            'app/templates/integrations/orchestration/container_orchestrator/providers/kubernetes/partials/_capability_registry.html',
            'kubernetes-capability-loading',
            False,
        ),
        (
            'app/templates/integrations/observability/metrics_source/partials/_capability_registry.html',
            'metrics-source-capability-loading',
            True,
        ),
        (
            'app/templates/integrations/observability/alert_source/providers/alertmanager/partials/_capability_registry.html',
            'alertmanager-capability-loading',
            True,
        ),
    )
    fake_loading_tokens = (
        'registryLoading:',
        'showRegistryLoading()',
        'loadingTimer:',
        'setTimeout(() => { registryLoading',
        'x-show="registryLoading"',
    )
    provider_registry_backend = read('app/integrations/capability_registry.py')
    common_pagination = read('app/common/pagination.py')
    require(
        'allowed_per_page=PER_PAGE_OPTIONS' in provider_registry_backend,
        'Provider capability registries must use shared PER_PAGE_OPTIONS',
        errors,
    )
    require(
        'PER_PAGE_OPTIONS: tuple[int, ...] = (5, 10, 25, 50)' in common_pagination,
        'Canonical KAORI page-size options drifted from 5/10/25/50',
        errors,
    )

    for relative, indicator_id, uses_variable_id in registry_contracts:
        source = read(relative)
        require('components/loading_bar.html' in source, f'{relative}: must import shared loading bar', errors)
        if uses_variable_id:
            require(
                f"loading_id = '{indicator_id}'" in source or f'loading_id = "{indicator_id}"' in source,
                f'{relative}: canonical loading id drifted',
                errors,
            )
            require(
                'loading_bar.render(loading_id' in source,
                f'{relative}: must render canonical loading indicator',
                errors,
            )
            require(
                'hx-indicator="#{{ loading_id }}"' in source,
                f'{relative}: registry requests must target canonical loading indicator',
                errors,
            )
        else:
            require(
                f"loading_bar.render('{indicator_id}'" in source,
                f'{relative}: must render canonical loading indicator',
                errors,
            )
            require(
                f'hx-indicator="#{indicator_id}"' in source,
                f'{relative}: registry requests must target canonical loading indicator',
                errors,
            )
        require('components/pagination.html' in source, f'{relative}: must use shared pagination', errors)
        require(
            'pagination.allowed_per_page' in source,
            f'{relative}: page-size selector must render server-owned allowed_per_page',
            errors,
        )
        for token in fake_loading_tokens:
            require(token not in source, f'{relative}: synthetic local loading state is forbidden ({token})', errors)

    # Record-detail actions and modals are shared; registry details may not recreate local geometry.
    actions = read('app/templates/integrations/components/_record_actions.html')
    require(
        '{{ table_ui.action_classes() }}' in actions,
        'Integration View More must use shared table action classes',
        errors,
    )
    require(
        'data-lucide="chevron-right"' in actions,
        'Integration View More must use quiet chevron-right iconography',
        errors,
    )
    require(
        'panel-top-open' not in actions, 'Integration View More must not restore oversized panel iconography', errors
    )
    require("role='record'" in actions, 'Shared View More macro must preserve optional role compatibility', errors)

    runtime_modal = read('app/templates/integrations/components/_runtime_observation_modal.html')
    require(
        'record_detail_modal.render(' in runtime_modal,
        'Runtime Observation must use shared record-detail modal shell',
        errors,
    )
    require("size='standard'" in runtime_modal, 'Runtime Observation modal must use standard size', errors)
    require(
        '<dialog' not in runtime_modal, 'Runtime Observation content must not own a standalone dialog shell', errors
    )
    require(
        'Diagnostic Review' in runtime_modal,
        'Runtime Observation modal must retain one Diagnostic Review boundary',
        errors,
    )
    require(
        'Recommended Action' in runtime_modal,
        'Runtime Observation diagnostic review must retain recommended action guidance',
        errors,
    )

    runtime_overview = read('app/templates/integrations/partials/_runtime_overview.html')
    require(
        'record_actions.view_more(' in runtime_overview,
        'Integration Runtime Overview must use shared View More',
        errors,
    )
    require(
        'expandable_row' not in runtime_overview and 'Hide Details' not in runtime_overview,
        'Runtime Overview inline detail expansion is forbidden',
        errors,
    )
    require('table-fixed' in runtime_overview, 'Runtime Overview must remain a fixed-layout KAORI table', errors)

    # Runtime detail workspaces remain full-width decision/evidence surfaces.
    for relative in (
        'app/templates/integrations/observability/metrics_source/partials/_runtime_panel.html',
        'app/templates/integrations/observability/alert_source/providers/alertmanager/partials/_runtime_panel.html',
    ):
        source = read(relative)
        require(
            'integrations/components/_runtime_decision.html' in source,
            f'{relative}: must use shared runtime decision surface',
            errors,
        )
        require(
            'runtime_decision.render(' in source, f'{relative}: must render shared runtime decision surface', errors
        )
        require('xl:sticky' not in source, f'{relative}: sticky Runtime Decision rail is forbidden', errors)

    kubernetes_runtime = read(
        'app/templates/integrations/orchestration/container_orchestrator/providers/kubernetes/partials/_runtime_workspace.html'
    )
    require(
        'data-kaori-runtime-decision-summary' in kubernetes_runtime,
        'Kubernetes runtime decision summary marker is missing',
        errors,
    )
    require(
        'data-kaori-runtime-evidence-workspace' in kubernetes_runtime,
        'Kubernetes runtime evidence workspace marker is missing',
        errors,
    )
    require(
        'data-kaori-runtime-primary-finding' in kubernetes_runtime,
        'Kubernetes runtime primary finding must remain concise and explicit',
        errors,
    )

    # Provider detail Configuration is read-only; edit workspaces are separate.
    config_contract = read('app/templates/integrations/components/_provider_configuration_contract.html')
    for marker in (
        'data-kaori-provider-configuration-contract',
        'Connection Contract',
        'Connection Evidence',
        'operational_context.render(',
        'Configure Connection',
    ):
        require(marker in config_contract, f'Shared provider Configuration contract missing: {marker}', errors)
    require('Operational Boundary' not in config_contract, 'Separate Operational Boundary surface is retired', errors)
    require('Operational Flow' not in config_contract, 'Separate Operational Flow surface is retired', errors)
    for provider, template_root in (
        ('metrics_source', 'app/templates/integrations/observability/metrics_source'),
        ('alertmanager', 'app/templates/integrations/observability/alert_source/providers/alertmanager'),
    ):
        relative = f'{template_root}/partials/_detail_configuration.html'
        source = read(relative)
        require(
            'provider_configuration_contract.render(' in source,
            f'{relative}: must use shared read-only provider Configuration contract',
            errors,
        )
        require('<form' not in source, f'{relative}: detail Configuration must not embed editable forms', errors)
        require(
            'edit_instance' in source, f'{relative}: Configuration must link to dedicated Edit Connection page', errors
        )

    # Provider detail tabs use one shared controller.
    tab_controller = read('app/static/js/integration_workspace_tabs.js')
    layout = read('app/templates/layouts/app.html')
    require('window.integrationWorkspaceTabs' in tab_controller, 'Shared provider tab controller is missing', errors)
    require(
        'integration_workspace_tabs.js' in layout, 'Application layout must load shared provider tab controller', errors
    )
    for provider, template_root in (
        ('metrics_source', 'app/templates/integrations/observability/metrics_source'),
        ('alertmanager', 'app/templates/integrations/observability/alert_source/providers/alertmanager'),
    ):
        source = read(f'{template_root}/instance_detail.html')
        require('integrationWorkspaceTabs(' in source, f'{provider}: detail tabs must use shared controller', errors)
        require(
            'binding_rows|default([])' in source,
            f'{provider}: binding badge must count registered binding_rows',
            errors,
        )
        require(
            'scope_bindings|default([])' not in source,
            f'{provider}: stale scope_bindings badge fallback is forbidden',
            errors,
        )

    # Top-level provider registries share one DRY proportional-column contract.
    # Provider pages must not reintroduce page-local fixed layouts or forced desktop widths.
    shared_registry = read('app/templates/integrations/components/_provider_registry.html')
    require(
        'connection_registry_colgroup' in shared_registry and 'connection_registry_head' in shared_registry,
        'Shared provider registry must own the canonical proportional columns and headers',
        errors,
    )
    require(
        'table_ui.table_classes()' in shared_registry,
        'Shared provider registry must use the responsive canonical table contract',
        errors,
    )
    registry_templates = (
        'app/templates/integrations/orchestration/container_orchestrator/providers/kubernetes/partials/_registry.html',
        'app/templates/integrations/observability/metrics_source/partials/_inventory_content.html',
        'app/templates/integrations/observability/alert_source/providers/alertmanager/partials/_inventory_content.html',
        'app/templates/integrations/storage/object_storage/providers/minio/partials/_registry_content.html',
    )
    for relative in registry_templates:
        source = read(relative)
        require(
            'provider_registry.connection_registry_colgroup()' in source
            and 'provider_registry.connection_registry_head()' in source,
            f'{relative}: registry must consume the shared connection column contract',
            errors,
        )
        require('table-fixed' not in source, f'{relative}: page-local table-fixed layout is forbidden', errors)
        require('min-w-[10' not in source, f'{relative}: forced desktop registry width is forbidden', errors)

    # RBAC baseline and optional Secret access remain separate by design.
    rbac = read(
        'app/templates/integrations/orchestration/container_orchestrator/providers/kubernetes/partials/_minimum_validation_rbac.html'
    )
    require(
        'components/workspace_tabs.html' in rbac and 'workspace_tabs.render(' in rbac,
        'Minimum Validation RBAC modal must use shared tabs',
        errors,
    )
    require(
        'Baseline Validation Reader' in rbac and 'Optional Secret Reader' in rbac,
        'Both RBAC evidence boundaries must remain explicit',
        errors,
    )
    baseline_start = rbac.find('id="minimum-rbac-panel-baseline"')
    optional_start = rbac.find('id="minimum-rbac-panel-secret"')
    baseline_rbac = (
        rbac[baseline_start:optional_start] if baseline_start >= 0 and optional_start > baseline_start else rbac
    )
    require('resources: ["secrets"]' not in baseline_rbac, 'Baseline validation RBAC must exclude Secrets', errors)
    optional_rbac = rbac[optional_start:] if optional_start >= 0 else ''
    require(
        'kind: Role' in optional_rbac and 'kind: RoleBinding' in optional_rbac,
        'Optional Secret reader must stay namespace-scoped',
        errors,
    )

    # Canonical Kubernetes navigation must not regress to the retired cluster list endpoint.
    kubernetes_detail = read(
        'app/templates/integrations/orchestration/container_orchestrator/providers/kubernetes/detail.html'
    )
    require(
        (
            "url_for('integrations.kubernetes')" in kubernetes_detail
            or 'url_for("integrations.kubernetes")' in kubernetes_detail
        ),
        'Kubernetes detail must return to Integration registry',
        errors,
    )
    require(
        'cluster.list_clusters' not in kubernetes_detail,
        'Kubernetes detail must not reference retired cluster.list_clusters endpoint',
        errors,
    )

    # Shared operational feedback must stay script-owned and inline-style free.
    toast = read('app/templates/components/operational_toast.html')
    toast_js = read('app/static/js/operational_toasts.js')
    require('data-operational-toast-timer' in toast, 'Operational toast timer marker is missing', errors)
    require('style=' not in toast, 'Operational toast must remain free from inline timer style', errors)
    require(
        'timerBar.animate' in toast_js and 'scaleX(0)' in toast_js,
        'Operational toast countdown must remain JavaScript-owned',
        errors,
    )

    # Known dead Integration-era templates may not return.
    obsolete = (
        'app/templates/integrations/partials/_runtime_detail_content.html',
        'app/templates/integrations/observability/metrics_source/partials/_analytics_readiness.html',
        'app/templates/integrations/orchestration/container_orchestrator/providers/kubernetes/partials/_runtime_history.html',
        'app/templates/integrations/partials/_binding_validation_posture.html',
        'app/templates/integrations/partials/_status_badge.html',
        'app/templates/integrations/observability/metrics_source/partials/_validation_response.html',
        'app/templates/integrations/observability/alert_source/providers/alertmanager/partials/_operation_feedback_oob.html',
    )
    cleanup_script = read('scripts/cleanup_obsolete_files.sh')
    for relative in obsolete:
        require(
            not (ROOT / relative).exists(),
            f'Obsolete Integration compatibility template reintroduced: {relative}',
            errors,
        )
        require(
            f"'{relative}'" in cleanup_script,
            f'Cleanup script must retain obsolete Integration path: {relative}',
            errors,
        )

    # Observability Bindings & Consumers final-lock contract.
    binding_boundary = read('app/templates/integrations/components/_binding_readiness_boundary.html')
    binding_modal = read('app/templates/integrations/components/_observability_binding_modal.html')
    binding_layout = read('app/templates/integrations/components/_binding_registry_layout.html')
    validation_poller = read('app/templates/integrations/components/_validation_poller.html')
    require(
        'data-kaori-binding-readiness-boundary' in binding_boundary
        and 'Source-Owned Mutation' in binding_boundary
        and 'Primary resolves before Secondary, then Fallback' in binding_boundary,
        'Bindings & Consumers must keep the shared readiness and resolver boundary',
        errors,
    )
    require(
        'data-kaori-binding-workflow' in binding_modal
        and 'Consumer &amp; Resolver Preference' in binding_modal
        and 'Source-Owned Mutation Boundary' in binding_modal
        and 'Validation Required' in binding_modal,
        'Shared Observability Add Binding dialog must keep workflow and validation ownership guidance',
        errors,
    )
    require(
        'table_ui.table_classes' in binding_layout
        and 'min-w-[72rem]' in binding_layout
        and 'data-kaori-binding-registry-columns' in binding_layout
        and binding_layout.count('w-[30%]') == 1
        and binding_layout.count('w-[18%]') == 2
        and binding_layout.count('w-[34%]') == 1
        and 'detail_grid_classes' in binding_layout
        and 'detail_item_classes' in binding_layout
        and 'flex min-w-0 flex-nowrap items-center justify-end gap-2 whitespace-nowrap' in binding_layout,
        'Shared binding registry must keep a summary-first four-column layout with stable Actions capacity and expandable secondary details',
        errors,
    )
    require(
        'data-kaori-validation-poller' in validation_poller and 'hx-trigger="every {{ delay }}"' in validation_poller,
        'Integration validation must reuse the shared periodic terminal-aware validation poller',
        errors,
    )
    validation_state = read('app/integrations/validation/state.py')
    validation_web = read('app/integrations/validation/web.py')
    validation_tasks = read('app/integrations/validation/tasks.py')
    metrics_contract = read('app/definitions/catalogs/integrations/observability/metrics_source/contract.yaml')
    require(
        'Cache-Control' in validation_web
        and "'no-store, max-age=0'" in validation_web
        and 'kaori:notifications-changed' in validation_web,
        'Validation poll responses must bypass caches and refresh Notification Deck on terminal completion',
        errors,
    )
    require(
        'from app.models.integration import IntegrationBinding' in validation_tasks
        and 'db.session.get(IntegrationBinding, binding_id)' in validation_tasks,
        'Binding validation worker must import and load the canonical IntegrationBinding model',
        errors,
    )
    require(
        'def _reconcile_terminal_job(' in validation_state
        and "celery_state not in {'SUCCESS', 'FAILURE', 'REVOKED'}" in validation_state
        and "'is_active': False if terminal" in validation_state
        and "'is_complete': True if terminal" in validation_state,
        'Validation snapshots must stop polling on terminal Celery results and reconcile durable JobExecution state',
        errors,
    )
    require(
        'def _binding_id_from_snapshot(' in validation_state
        and "scope_type') or '') != 'integration_binding'" in validation_state
        and "prefix = 'binding:'" in validation_state
        and "payload['binding_id'] = binding_id" in validation_state,
        'Binding validation snapshots must recover binding identity from durable JobExecution scope when transient metadata is missing',
        errors,
    )
    full_validation = validation_tasks.split('def validate_integration_instance', 1)[1].split(
        'def _as_result_payload', 1
    )[0]
    require(
        '_refresh_provider_bindings(' not in full_validation and 'binding_validation_summary' not in full_validation,
        'Provider Full Validation must remain core-only and must not refresh bindings implicitly',
        errors,
    )
    thanos_contract = metrics_contract.split('- key: thanos', 1)[1].split('compatibility_profiles:', 1)[0]
    require(
        'version_detection_mode: automatic' in thanos_contract
        and 'compatibility_profile_options: []' in thanos_contract
        and 'Prometheus HTTP API v2' not in thanos_contract
        and 'Prometheus HTTP API v3' not in thanos_contract,
        'Thanos must auto-detect its own runtime and must not expose fake Prometheus HTTP v2/v3 choices',
        errors,
    )

    metrics_form = read('app/templates/integrations/observability/metrics_source/instance_form.html')
    metrics_runtime_template = read(
        'app/templates/integrations/observability/metrics_source/partials/_runtime_panel.html'
    )
    require(
        'Prometheus HTTP API v1 / PromQL core contract' in metrics_form
        and 'Prometheus HTTP API v2' not in metrics_form
        and 'Prometheus HTTP API v3' not in metrics_form
        and 'Provider Runtime Profile' in metrics_runtime_template
        and 'Query Contract' in metrics_runtime_template,
        'Metrics Source UI must separate provider runtime compatibility from the shared query contract',
        errors,
    )

    provider_header = read('app/templates/components/connection_validation_header.html')
    require(
        'text-base font-semibold text-content-primary' in provider_header
        and 'mt-1 max-w-3xl text-sm leading-6 text-content-secondary' in provider_header
        and 'text-xs leading-5 text-content-muted' not in provider_header,
        'Provider detail primary headers must use the canonical text-base title and text-sm/leading-6 description typography',
        errors,
    )

    for runtime_path in (
        'app/templates/integrations/observability/metrics_source/partials/_runtime_panel.html',
        'app/templates/integrations/observability/alert_source/providers/alertmanager/partials/_runtime_panel.html',
        'app/templates/integrations/storage/object_storage/providers/minio/partials/_detail_runtime.html',
        'app/templates/integrations/orchestration/container_orchestrator/providers/kubernetes/partials/_runtime_workspace.html',
    ):
        runtime_template = read(runtime_path)
        require(
            '_validation_poller.html' in runtime_template
            and 'validation_poller.render(' in runtime_template
            and 'hx-trigger="load delay:1500ms"' not in runtime_template,
            f'Runtime workspace must use shared terminal-aware polling: {runtime_path}',
            errors,
        )

    for provider, template_root, identity_column in (
        ('metrics_source', 'app/templates/integrations/observability/metrics_source', 'Metrics Identity'),
        (
            'alertmanager',
            'app/templates/integrations/observability/alert_source/providers/alertmanager',
            'Alert Identity',
        ),
    ):
        registry = read(f'{template_root}/partials/_binding_registry.html')
        scope = read(f'{template_root}/partials/_detail_scope.html')
        for marker in (
            'data-kaori-binding-registry-final-lock',
            'Consumer Binding',
            identity_column,
            'Consumer Profile',
            'Resolver Preference',
            'Binding Validation',
            'Effective Resolution',
            'Actions',
            'Validate before eligibility',
            'data-kaori-binding-view-more',
            'data-kaori-binding-details-row',
            'data-kaori-binding-secondary-details',
        ):
            require(marker in registry, f'{provider}: binding registry final-lock marker missing: {marker}', errors)
        action_region = registry.split('data-kaori-binding-actions', 1)[1].split('</div>', 1)[0]
        first_row = registry.split('{% for row in binding_registry_rows %}', 1)[1]
        consumer_cell = first_row.split('<td class="{{ table_ui.cell_classes() }}">', 1)[1].split('</td>', 1)[0]
        require(
            'View More' in action_region
            and 'data-kaori-binding-view-more' in action_region
            and 'data-kaori-binding-view-more' not in consumer_cell,
            f'{provider}: View More must remain a canonical Actions-column button rather than inline Consumer Binding text',
            errors,
        )
        require(
            'components/pagination.html' in registry, f'{provider}: binding pagination must remain canonical', errors
        )
        require(
            'components/loading_bar.html' in registry, f'{provider}: binding loading bar must remain shared', errors
        )
        require(
            '_binding_registry_layout.html' in registry
            and 'data-kaori-binding-registry-table' in registry
            and 'binding_registry_layout.columns()' in registry
            and 'binding_registry_layout.action_group_classes()' in registry
            and 'binding_registry_layout.detail_grid_classes()' in registry
            and 'colspan="4"' in registry,
            f'{provider}: binding table must keep shared summary-first geometry and expandable detail ownership',
            errors,
        )
        require(
            '_validation_poller.html' in scope
            and 'validation_poller.render(' in scope
            and 'hx-trigger="load delay:1500ms" hx-target="this"' not in scope,
            f'{provider}: binding validation must poll through the shared child poller rather than self-replacing root HTMX',
            errors,
        )
        require(
            "binding_validation_job.get('binding_id')" in scope
            and 'binding_poll_active' in scope
            and 'binding_validation_job.binding_id' not in scope
            and 'binding_validation_job.binding_id' not in registry,
            f'{provider}: binding polling and action state must tolerate incomplete transient validation metadata without raising template errors',
            errors,
        )

    # Integrations Overview and provider front-page final-lock contract.
    provider_front_pages = {
        'Kubernetes': read(
            'app/templates/integrations/orchestration/container_orchestrator/providers/kubernetes/frontpage.html'
        ),
        'Metrics Source': read('app/templates/integrations/observability/metrics_source/frontpage.html'),
        'Alertmanager': read(
            'app/templates/integrations/observability/alert_source/providers/alertmanager/frontpage.html'
        ),
        'MinIO': read('app/templates/integrations/storage/object_storage/providers/minio/index.html'),
    }
    for provider, source in provider_front_pages.items():
        require('Coverage Gaps' in source, f'{provider}: fourth overview metric must be Coverage Gaps', errors)
        require('Uncovered Assets' not in source, f'{provider}: retired Uncovered Assets label returned', errors)
        require('Uncovered Scopes' not in source, f'{provider}: retired Uncovered Scopes label returned', errors)
        require(
            'provider_front.hero(' in source and 'provider_front.overview(' in source,
            f'{provider}: provider front page must remain shared-component owned',
            errors,
        )
    alertmanager_front = provider_front_pages['Alertmanager']
    require(
        'stats.ready == stats.total' in alertmanager_front,
        'Alertmanager provider posture must compare ready connections against all registered connections',
        errors,
    )
    require(
        'stats.ready == stats.configured' not in alertmanager_front,
        'Alertmanager provider posture must not report Healthy when an unconfigured record exists',
        errors,
    )

    integration_overview = read('app/templates/integrations/overview.html')
    integration_service = read('app/integrations/service.py')
    integration_overview_workspace = read('app/integrations/overview_workspace.py')
    for marker in (
        "available_provider_count ~ ' Providers'",
        'integration_status(item.posture_state, item.posture_label',
        'Operational Readiness',
        'progress_bar.bar(item.readiness_percent',
    ):
        require(marker in integration_overview, f'Integrations Overview provider catalog missing: {marker}', errors)
    require(
        'framed_workspace_tabs.render_navigation(' in integration_overview
        and "hx_target='#integration-workspace'" in integration_overview,
        'Integration Overview deep workspaces must be server-owned and demand-loaded',
        errors,
    )
    require(
        "allowedTabs: ['catalog', 'runtime', 'coverage']" not in integration_overview,
        'Integration Overview must not eagerly render client-hidden deep workspaces',
        errors,
    )
    require(
        'No targets registered' in integration_overview
        and 'integration_status(item.posture_state, item.posture_label' in integration_overview,
        'Integration Domain Coverage must not report 0-of-0 target domains as Ready',
        errors,
    )
    require(
        'Runtime Evidence Lifecycle' in runtime_overview and 'components/states/_empty_state.html' in runtime_overview,
        'Runtime Overview must use canonical empty-state ownership and expose shared lifecycle governance',
        errors,
    )
    for marker in (
        "'ready': ready",
        "'total': total",
        "'attention': attention",
        "'readiness_percent':",
        "'posture_state': posture_state",
        "'posture_label': posture_label",
    ):
        require(marker in integration_service, f'Integrations provider catalog evidence missing: {marker}', errors)
    overview_builder = integration_overview_workspace.split('def build_integrations_overview(', 1)[1]
    require(
        "if active_tab == 'catalog':" in overview_builder
        and "if active_tab == 'coverage':" in overview_builder
        and 'latest = _latest_runtime_observations()' in overview_builder,
        'Integration Overview selected-workspace build boundary is missing',
        errors,
    )
    require(
        'build_extension_runtime_rows(latest)' in overview_builder and 'latest=latest' in overview_builder,
        'Integration Runtime Overview must reuse one latest-observation snapshot per request',
        errors,
    )
    runtime_detail_builder = integration_service.split('def build_integration_runtime_detail(', 1)[1]
    require(
        '_latest_runtime_observation(integration_type, str(target_id))' in runtime_detail_builder
        and '_latest_runtime_observations()' not in runtime_detail_builder,
        'Integration Runtime detail must read only the selected target observation',
        errors,
    )

    domain_routes = read('app/integrations/routes.py')
    domain_service = read('app/integrations/domain_service.py')
    domain_page = read('app/templates/integrations/domain.html')
    domain_workspace = read('app/templates/integrations/partials/_domain_workspace.html')
    registry_module = read('app/integrations/registry.py')
    require(
        "is_workspace_partial = is_htmx_request() and htmx_target() == 'domain-workspace'" in domain_routes
        and "return render_template('integrations/partials/_domain_workspace.html', **context)" in domain_routes,
        'Integration domain workspaces must return the selected HTMX workspace without rendering the full domain page',
        errors,
    )
    require(
        '{% include "integrations/partials/_domain_workspace.html" %}' in domain_page
        and domain_workspace.count('registry_ui.filter_form(') == 2
        and domain_workspace.count('registry_ui.clear_filters_link(') == 2,
        'Integration domain Provider Registry and Consumer Bindings must use canonical KAORI filter ownership',
        errors,
    )
    require(
        "'bindings': sum(1 for binding in consumer_bindings if binding.enabled)" in domain_service
        and 'No {{ domain.label }} Consumer Bindings Yet' in domain_workspace
        and 'Use Add Consumer Binding' not in domain_workspace,
        'Integration domain binding metrics must exclude native owner attachments and must not advertise a missing action',
        errors,
    )
    require(
        "include_details=normalized_tab == 'bindings'" in domain_service
        and 'load_only(' in domain_service
        and '_resolve_provider_detail_urls(provider_registry_rows)' in domain_service
        and '_resolve_binding_detail_urls(binding_registry_rows)' in domain_service
        and 'detail_url_for_record' in registry_module,
        'Integration domain registries must keep binding evidence and provider-detail resolution page-bounded',
        errors,
    )
    require(
        'if registered <= 0:' in domain_service
        and 'if enabled <= 0:' in domain_service
        and "return 'attention'" in domain_service,
        'Integration domain posture must not label registered disabled targets as Not Configured',
        errors,
    )

    # Provider detail lifecycle final-lock contract.
    provider_details = {
        'Kubernetes': read(
            'app/templates/integrations/orchestration/container_orchestrator/providers/kubernetes/detail.html'
        ),
        'Metrics Source': read('app/templates/integrations/observability/metrics_source/instance_detail.html'),
        'Alertmanager': read(
            'app/templates/integrations/observability/alert_source/providers/alertmanager/instance_detail.html'
        ),
        'MinIO': read('app/templates/integrations/storage/object_storage/providers/minio/instance_detail.html'),
    }
    for provider, source in provider_details.items():
        for label in ('Configuration', 'Validation & Capabilities', 'Runtime & History'):
            require(label in source, f'{provider}: provider detail lifecycle tab missing: {label}', errors)
        require(
            'Produced by Full Validation' in source,
            f'{provider}: connection posture must attribute provider evidence to Full Validation',
            errors,
        )
        require(
            'Validated Capabilities' in source,
            f'{provider}: provider detail must use Validated Capabilities terminology',
            errors,
        )

    require(
        'Inventory & Lifecycle' in provider_details['Kubernetes'],
        'Kubernetes detail must retain Inventory & Lifecycle',
        errors,
    )
    require(
        'Inventory & Lifecycle' in provider_details['MinIO'], 'MinIO detail must retain Inventory & Lifecycle', errors
    )
    require(
        'Bindings & Consumers' in provider_details['Metrics Source'],
        'Metrics Source detail must retain Bindings & Consumers',
        errors,
    )
    require(
        'Bindings & Consumers' in provider_details['Alertmanager'],
        'Alertmanager detail must retain Bindings & Consumers',
        errors,
    )

    validation_templates = {
        'Kubernetes': read(
            'app/templates/integrations/orchestration/container_orchestrator/providers/kubernetes/partials/_capability_workspace.html'
        ),
        'Metrics Source': read(
            'app/templates/integrations/observability/metrics_source/partials/_detail_validation_content.html'
        ),
        'Alertmanager': read(
            'app/templates/integrations/observability/alert_source/providers/alertmanager/partials/_detail_validation_content.html'
        ),
        'MinIO': read(
            'app/templates/integrations/storage/object_storage/providers/minio/partials/_detail_validation.html'
        ),
    }
    for provider, source in validation_templates.items():
        require(
            f'{provider} Full Validation' in source,
            f'{provider}: validation workspace title must be Full Validation',
            errors,
        )
        require(
            'Run Full Validation' in source, f'{provider}: validation action must remain Run Full Validation', errors
        )
        require(
            'capability_readiness.render(' in source,
            f'{provider}: validation workspace must use shared capability readiness',
            errors,
        )
    require(
        'Core Validation' not in validation_templates['Metrics Source'],
        'Metrics Source detail UI must not expose retired Core Validation title',
        errors,
    )
    require(
        'Alertmanager Core Validation' not in validation_templates['Alertmanager'],
        'Alertmanager detail UI must not expose retired Core Validation title',
        errors,
    )

    for provider, relative in (
        ('Metrics Source', 'app/templates/integrations/observability/metrics_source/partials/_runtime_panel.html'),
        (
            'Alertmanager',
            'app/templates/integrations/observability/alert_source/providers/alertmanager/partials/_runtime_panel.html',
        ),
        ('MinIO', 'app/templates/integrations/storage/object_storage/providers/minio/partials/_detail_runtime.html'),
    ):
        source = read(relative)
        require(
            'integrations/components/_runtime_decision.html' in source,
            f'{provider}: runtime must import shared Runtime Decision',
            errors,
        )
        require(
            'runtime_decision.render(' in source, f'{provider}: runtime must render shared Runtime Decision', errors
        )

    # The final lock documentation is itself part of the contract.
    lock_doc = read('docs/design/KAORI_INTEGRATIONS_LOCK_V1.md')
    refinement_doc = read('docs/design/KAORI_INTEGRATIONS_LOCK_V1_1.md')
    audit_doc = read('docs/design/audits/KAORI_INTEGRATIONS_FINAL_LOCK_V1_1_AUDIT_2026_08_08.md')
    standard = read('docs/design/components/INTEGRATIONS_WORKSPACE_STANDARD.md')
    require('Status: Locked baseline' in lock_doc, 'Integration lock document must declare Locked baseline', errors)
    require(
        'Status: Locked refinement baseline' in refinement_doc,
        'Integration v1.1 refinement lock must declare Locked refinement baseline',
        errors,
    )
    require(
        'Configuration Decision rail density' in refinement_doc,
        'Integration v1.1 refinement lock must freeze Configuration Decision density',
        errors,
    )
    require(
        'Configuration Decision' in audit_doc,
        'Integration v1.1 audit must record Configuration Decision refinement',
        errors,
    )
    require(
        'KAORI Integrations Lock v1' in standard, 'Integration workspace standard must reference the final lock', errors
    )
    require(
        'KAORI Integrations Lock v1.1' in standard,
        'Integration workspace standard must reference the v1.1 refinement',
        errors,
    )

    if errors:
        for error in errors:
            print(f'ERROR: {error}')
        return 1

    print(f'PASS — KAORI Integrations Final Lock v1.1 · {checked_templates} templates')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
