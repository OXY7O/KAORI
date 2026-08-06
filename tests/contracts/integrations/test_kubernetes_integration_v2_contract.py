from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_tab_v2_is_shared_by_kubernetes_and_integration_overview() -> None:
    component = read('app/templates/components/framed_workspace_tabs.html')
    detail = read('app/templates/integrations/kubernetes/detail.html')
    overview = read('app/templates/integrations/overview.html')
    tab_v1 = read('app/templates/components/workspace_tabs.html')

    assert 'KAORI Tab Style 2' in component
    assert 'data-kaori-tab-variant="framed-workspace-v2"' in component
    assert '@keydown.arrow-right.prevent' in component
    assert ':tabindex=' in component
    assert 'components/framed_workspace_tabs.html' in detail
    assert 'framed_workspace_tabs.render(' in detail
    assert "prefix='kubernetes'" in detail
    assert 'components/framed_workspace_tabs.html' in overview
    assert 'framed_workspace_tabs.render(' in overview
    assert "prefix='integration-overview'" in overview
    assert 'KAORI Tab Style 1' in tab_v1
    registry = read('docs/design/components/TAB_STYLES.md')
    framed_contract = read('docs/design/components/FRAMED_WORKSPACE_TABS.md')
    segmented_contract = read('docs/design/components/SEGMENTED_TABS.md')
    assert 'Tab Style 2 — Framed Workspace Tabs' in registry
    assert 'components/framed_workspace_tabs.html' in registry
    assert 'Tab Style 3 — Compact Segmented Tabs' in registry
    assert 'framed-workspace-v2' in framed_contract
    assert 'Tab Style 3 — Compact Segmented Tabs' in segmented_contract


def test_kubernetes_registry_uses_one_line_htmx_filters_and_inventory_table() -> None:
    registry = read('app/templates/integrations/kubernetes/partials/_registry.html')
    routes = read('app/integrations/routes.py')
    service = read('app/integrations/service.py')

    assert 'components/table.html' in registry
    assert 'data-kaori-one-line-filters' in registry
    assert 'min-w-[840px]' in registry
    assert 'grid-cols-[minmax(17rem,1.45fr)_repeat(3,minmax(11rem,0.85fr))]' in registry
    assert 'input changed delay:300ms' in registry
    assert 'change delay:100ms from:select' in registry
    assert 'Apply Filters' not in registry
    assert '>Reset<' not in registry
    assert "item_label='Integration'" in registry
    assert 'table_ui.row_classes()' in registry
    assert 'hover:bg-surface-hover' not in registry
    for name in ('q', 'environment', 'readiness', 'coverage'):
        assert f"request.args.get('{name}'" in routes
    assert "request.headers.get('HX-Target') == 'kubernetes-connection-registry'" in routes
    assert 'normalized_query' in service
    assert "row.get('coverage_summary')" in service


def test_kubernetes_runtime_health_requires_persisted_observation() -> None:
    service = read('app/integrations/service.py')
    presentation = read('app/integrations/runtime/presentation.py')
    runtime = read('app/templates/integrations/kubernetes/partials/_runtime_workspace.html')

    assert "IntegrationRuntimeObservation.query.filter_by(" in service
    assert "provider='kubernetes'" in service
    assert 'runtime_observation_state_view(' in service
    assert "'health_status': 'not_observed'" in presentation
    assert "'health_score_display': 'N/A'" in presentation
    assert 'Runtime Not Observed' in runtime
    assert 'Runtime health is never inferred from connection state.' in runtime
    assert 'Validation Readiness' in runtime


def test_kubernetes_actions_are_permission_aware() -> None:
    detail = read('app/templates/integrations/kubernetes/detail.html')
    capability = read('app/templates/integrations/kubernetes/partials/_capability_workspace.html')
    runtime = read('app/templates/integrations/kubernetes/partials/_runtime_workspace.html')
    connection = read('app/templates/integrations/kubernetes/partials/_connection_contract.html')

    assert "current_user.has_permission('clusters.sync')" in detail
    assert "current_user.has_permission('settings.manage_integrations')" in detail
    assert "url_for('cluster.list_clusters')" in detail
    assert "current_user.has_permission('clusters.sync')" in capability
    assert "current_user.has_permission('clusters.sync')" in runtime
    assert "current_user.has_permission('clusters.manage')" in connection


def test_validation_rbac_excludes_secrets_from_baseline_and_labels_optional_access() -> None:
    rbac = read('app/templates/integrations/kubernetes/partials/_minimum_validation_rbac.html')
    baseline, optional = rbac.split('Optional Governance Secret Reader', maxsplit=1)

    assert 'resources: ["secrets"]' not in baseline
    assert 'resources: ["secrets"]' in optional
    assert 'kind: Role' in optional
    assert 'namespace: &lt;approved-namespace&gt;' in optional
    assert 'can expose Secret data' in optional


def test_source_binding_evidence_is_not_collapsed_into_one_status() -> None:
    service = read('app/integrations/service.py')
    inventory = read('app/templates/integrations/kubernetes/partials/_inventory_lifecycle.html')

    for key in ('source_readiness', 'binding_validation', 'effective_status', 'effective_label'):
        assert f"'{key}'" in service
    for label in ('Source Readiness', 'Binding Validation', 'Effective Resolution'):
        assert label in inventory
    assert 'source.status' not in inventory


def test_inventory_freshness_and_capability_dimensions_are_explicit() -> None:
    service = read('app/integrations/service.py')
    inventory = read('app/templates/integrations/kubernetes/partials/_inventory_lifecycle.html')
    detail = read('app/templates/integrations/kubernetes/detail.html')

    assert 'ClusterInventory.query.filter_by(cluster_id=cluster.id)' in service
    assert "'inventory_collected_at_display'" in service
    assert "'validated_feature_count'" in service
    assert "'operational_domain_count'" in service
    assert 'Last collected {{ operational_use.inventory_collected_at_display }}' in inventory
    assert 'Validated Features' in inventory
    assert 'Operational Domains' in inventory
    assert 'Validated Features' in detail


def test_kubernetes_coverage_uses_compact_operational_path_cards() -> None:
    coverage = read('app/templates/integrations/kubernetes/partials/_integration_coverage.html')

    assert 'Operational Readiness Paths' in coverage
    assert 'data-kaori-operational-readiness-paths' in coverage
    assert 'data-kaori-operational-path-card' in coverage
    assert 'data-kaori-readiness-step' in coverage
    assert 'Kubernetes Inventory' in coverage
    assert 'Kubernetes Analytics' in coverage
    assert 'Alert Intelligence' in coverage
    assert "'provider': 'Prometheus'" in coverage
    assert "'provider': 'Alertmanager'" in coverage
    assert 'Evidence Path' in coverage
    assert 'Cluster Binding' in coverage
    assert 'Effective Consumer' in coverage
    assert 'View Evidence' in coverage
    assert 'x-show="evidenceOpen"' in coverage
    assert 'Provider Resolution Boundary' in coverage
    assert 'xl:grid-cols-3' in coverage
    assert 'items-start' in coverage
    assert 'data-lucide="arrow-right"' not in coverage
    assert 'Operational Coverage Lanes' not in coverage
    assert 'data-kaori-operational-coverage-lanes' not in coverage
    assert 'KAORI Consumer' not in coverage
    assert 'Operational Provider Coverage' not in coverage
    assert 'data-kaori-provider-coverage' not in coverage
    assert 'min-h-[260px]' not in coverage
    assert 'bg-kaori-soft' not in coverage


def test_secret_capability_is_optional_and_kept_out_of_baseline_readiness() -> None:
    compatibility = read('app/integrations/kubernetes/compatibility.py')
    validation = read('app/integrations/kubernetes/validation.py')
    service = read('app/integrations/service.py')
    capability = read('app/templates/integrations/kubernetes/partials/_capability_workspace.html')

    assert "FeatureContract('inventory.secrets', (ApiCandidate('', 'v1', 'secrets'),), required=False)" in compatibility
    assert "'optional_blocked_features'" in compatibility
    assert "if self._contract(key).required and value['status'] == 'blocked'" in compatibility
    assert 'Core Kubernetes readiness is unaffected' in validation
    assert "'requirement_label': 'Required' if required else 'Optional'" in service
    assert 'Optional Capability Access Is Limited' in capability
    assert 'Do not expand the baseline ClusterRole.' in capability
    assert '{{ validation_state.readiness_label }}</span>' in capability


def test_minimum_validation_rbac_uses_copy_friendly_modal() -> None:
    rbac = read('app/templates/integrations/kubernetes/partials/_minimum_validation_rbac.html')

    assert 'Open RBAC Examples' in rbac
    assert 'x-teleport="body"' in rbac
    assert 'role="dialog"' in rbac
    assert 'Copy Baseline YAML' in rbac
    assert 'Copy Secret Reader YAML' in rbac
    assert '<details' not in rbac


def test_capability_workspace_uses_modern_explorer_and_consistent_typography() -> None:
    capability = read('app/templates/integrations/kubernetes/partials/_capability_workspace.html')

    assert 'data-kaori-capability-workspace-v6' in capability
    assert 'data-kaori-capability-overview' in capability
    assert 'data-kaori-capability-explorer' in capability
    assert 'data-kaori-capability-matrix' in capability
    assert 'data-kaori-capability-matrix-header' in capability
    assert 'data-kaori-capability-matrix-row' in capability
    assert 'Search Capability' in capability
    assert 'All Requirements' in capability
    assert 'All Statuses' in capability
    assert 'x-model.debounce.150ms="query"' in capability
    assert 'x-show="matches($el)"' in capability
    assert 'data-kaori-capability-expanded-evidence' in capability
    assert 'data-kaori-capability-layout' in capability
    assert 'xl:grid-cols-[minmax(0,1fr)_22rem]' in capability
    assert '2xl:grid-cols-[minmax(0,1fr)_24rem]' in capability
    assert 'data-kaori-capability-side-panel' in capability
    assert 'data-kaori-capability-decision-panel' in capability
    assert 'Validation Decision Center' in capability
    assert 'Operational Gate Decision' in capability
    assert 'data-kaori-neutral-command-strip' in capability
    assert 'data-kaori-neutral-command-center' in capability
    assert 'data-kaori-readiness-score' in capability
    assert 'data-kaori-capability-posture-grid' in capability
    assert 'bg-surface-subtle' in capability
    assert 'border-outline-default' in capability
    assert 'Capability readiness' in capability
    assert 'Capability Coverage' in capability
    assert 'Downstream Eligibility' in capability
    assert 'Next Operational Action' in capability
    assert 'Validation Workflow' in capability
    assert 'Required Usable' in capability
    assert 'Optional Available' in capability
    assert 'xl:sticky xl:top-4' in capability
    assert "('1', 'Interpret'" in capability
    assert "('4', 'Synchronize'" in capability
    assert 'font-sans' in capability
    assert 'font-mono' not in capability
    assert 'uppercase tracking-wide' not in capability
    assert 'Kubernetes API Capability Detail' not in capability
    assert 'data-kaori-capability-card-grid' not in capability
    assert 'open:lg:col-span-2' not in capability


def test_kubernetes_detail_workspaces_use_connected_standard_surfaces() -> None:
    connection = read('app/templates/integrations/kubernetes/partials/_connection_contract.html')
    capability = read('app/templates/integrations/kubernetes/partials/_capability_workspace.html')
    inventory = read('app/templates/integrations/kubernetes/partials/_inventory_lifecycle.html')
    runtime = read('app/templates/integrations/kubernetes/partials/_runtime_workspace.html')

    assert 'data-kaori-connection-contract-v2' in connection
    assert 'data-kaori-connection-summary' in connection
    assert 'data-kaori-connection-evidence' in connection
    assert 'data-kaori-operational-context' in connection
    assert 'Connection Summary' in connection
    assert 'Connection Evidence' in connection
    assert 'Operational Boundary' in connection
    assert 'Operational Flow' in connection
    assert 'xl:grid-cols-[minmax(20rem,0.8fr)_minmax(0,1.2fr)]' in connection
    assert 'lg:grid-cols-[minmax(20rem,1.4fr)_repeat(3,minmax(12rem,0.75fr))]' in connection
    assert 'data-kaori-connection-contract-v3' not in connection
    assert 'Configuration Command Center' not in connection
    assert '_minimum_validation_rbac.html' in connection
    assert 'font-sans' in connection
    assert 'font-mono' not in connection
    assert 'data-kaori-capability-workspace-v4' in capability
    assert 'data-kaori-capability-overview' in capability
    assert 'Capability Matrix' in capability
    assert 'data-kaori-capability-filters' in capability
    assert 'data-kaori-capability-record' in capability
    assert 'Validation Workflow' in capability
    assert 'data-kaori-validation-operating-boundary' in capability
    assert 'font-mono' not in capability
    assert 'lg:grid-cols-[minmax(15rem,1.3fr)' not in capability
    assert 'Bound Observability Sources' in inventory
    assert 'components/table.html' in inventory
    assert 'Lifecycle Boundary' in inventory
    assert 'Runtime Operating Model' in runtime
    assert 'Diagnostic Evidence' in runtime
    assert 'data-kaori-runtime-diagnostic-list' in runtime
    assert 'data-kaori-runtime-diagnostic-row' in runtime
    assert 'components/table.html' not in runtime


def test_kubernetes_runtime_is_neutral_while_inventory_retains_optional_violet_language() -> None:
    detail = read('app/templates/integrations/kubernetes/detail.html')
    runtime = read('app/templates/integrations/kubernetes/partials/_runtime_workspace.html')
    inventory = read('app/templates/integrations/kubernetes/partials/_inventory_lifecycle.html')
    history = read('app/templates/integrations/partials/_runtime_history.html')

    assert 'data-kaori-runtime-workspace-v4' in runtime
    assert 'data-kaori-neutral-runtime-workspace' in runtime
    assert 'data-kaori-runtime-snapshot' in runtime
    assert 'data-kaori-runtime-layout' in runtime
    assert 'data-kaori-runtime-control-panel' in runtime
    assert 'Runtime Control Panel' in runtime
    assert 'Current Operational Focus' in runtime
    assert 'Observation Boundary' in runtime
    assert 'integrations/components/_violet_workspace.html' not in runtime
    assert 'data-kaori-violet-runtime-workspace' not in runtime
    assert 'bg-kaori-soft' not in runtime
    assert 'text-kaori-primary' not in runtime
    assert 'border-kaori-primary/' not in runtime
    assert "runtime_history_variant='violet-v2'" not in detail
    assert "runtime_history_variant='violet-v2'" not in runtime

    assert 'data-kaori-violet-inventory-workspace' in inventory
    assert 'data-kaori-inventory-command-center' in inventory
    assert 'integrations/components/_violet_workspace.html' in inventory
    assert 'runtime_history_is_violet' in history


def test_connection_contract_uses_controlled_kaori_icon_palette() -> None:
    connection = read('app/templates/integrations/kubernetes/partials/_connection_contract.html')

    assert 'data-kaori-connection-icon-palette' in connection
    assert 'data-kaori-palette-icon="brand"' in connection
    assert 'data-kaori-palette-icon="info"' in connection
    assert 'data-kaori-palette-icon="success"' in connection
    assert 'bg-kaori-soft text-kaori-primary' in connection
    assert 'bg-status-info-soft text-status-info' in connection
    assert 'bg-status-normal-soft text-status-normal' in connection
    assert 'bg-status-warning-soft text-status-warning' in connection
    assert "if connection.verify_ssl else 'bg-status-warning-soft text-status-warning'" in connection
    assert 'data-kaori-violet-command-strip' not in connection
    assert 'data-kaori-violet-command-center' not in connection


def test_kubernetes_registry_bulk_loads_provider_bindings() -> None:
    coverage = read('app/integrations/coverage.py')
    service = read('app/integrations/service.py')

    assert 'def bound_sources_for_scopes(' in coverage
    assert 'contains_eager(IntegrationBinding.instance)' in coverage
    assert 'source_maps = {' in coverage
    assert 'bound_sources_for_scopes(' in service
    assert "('prometheus', 'alertmanager')" in service
    assert 'contains_eager(KubernetesConnection.cluster)' in service
    assert '_build_kubernetes_registry_row(connection, bound_sources=bound_sources)' in service


def test_kubernetes_integration_overview_uses_controlled_kaori_icon_palette() -> None:
    page = read('app/templates/integrations/kubernetes.html')
    coverage = read('app/templates/integrations/kubernetes/partials/_integration_coverage.html')
    registry = read('app/templates/integrations/kubernetes/partials/_registry.html')
    provider_registry = read('app/templates/integrations/components/_provider_registry.html')

    assert 'data-kaori-kubernetes-integration-icon-palette' in page
    assert "'tone': 'brand'" in coverage
    assert "'tone': 'info'" in coverage
    assert "'tone': 'warning'" in coverage
    assert "'provider_tone': 'info'" in coverage
    assert "'provider_tone': 'warning'" in coverage
    assert "palette_icon('workflow', 'brand'" in coverage
    assert 'palette_icon(path.icon, path.tone)' in coverage
    assert 'palette_icon_classes(path.provider_tone' in coverage
    assert 'palette_icon_classes(effective_icon_tone' in coverage
    assert "palette_icon('route', 'info'" in coverage
    assert 'data-kaori-kubernetes-registry-icon-palette' in registry
    assert "connection_icon_tone = 'success' if row.readiness == 'ready'" in registry
    assert "palette_icon('server-cog', connection_icon_tone)" in registry
    assert "registry_header(title, description, icon, loading_id, title_id=None, tone='brand')" in provider_registry
