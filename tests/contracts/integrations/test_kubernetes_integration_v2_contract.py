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
    frontpage_service = read('app/integrations/kubernetes_frontpage.py')

    assert 'components/table.html' in registry
    assert 'data-kaori-one-line-filters' in registry
    assert 'min-w-[840px]' not in registry
    assert 'xl:grid-cols-[minmax(0,1.5fr)_repeat(3,minmax(0,1fr))]' in registry
    assert 'table-fixed' not in registry
    assert 'provider_registry.connection_registry_table_classes()' in registry
    assert '[overflow-wrap:anywhere]' in registry
    assert 'input changed delay:300ms' in registry
    assert 'change delay:100ms from:select' in registry
    assert 'Apply Filters' not in registry
    assert '>Reset<' not in registry
    assert 'item_label="Connections"' in registry
    assert 'table_ui.row_classes()' in registry
    assert 'hover:bg-surface-hover' not in registry
    for name in ('q', 'environment', 'readiness', 'coverage'):
        assert f"request.args.get('{name}'" in routes
    assert "target == 'kubernetes-connection-registry'" in routes
    assert 'normalized_query' in frontpage_service
    assert "row.get('coverage_summary')" in frontpage_service


def test_kubernetes_activity_is_navigation_and_capability_modal_scope_isolated() -> None:
    registry = read('app/templates/integrations/kubernetes/partials/_registry.html')
    capability = (
        read('app/templates/integrations/kubernetes/partials/_capability_workspace.html')
        + read('app/templates/integrations/kubernetes/partials/_capability_registry.html')
        + read('app/templates/integrations/components/_capability_readiness.html')
    )
    modal = read('app/templates/integrations/components/_record_detail_modal.html')
    controller = read('app/static/js/native_dialogs.js')

    assert "url_for('integrations.kubernetes_detail', cluster_id=row.cluster_id)" in registry
    assert '>Manage<' in registry or 'Manage\n' in registry
    activity_link = registry[registry.index("url_for('integrations.kubernetes_detail', cluster_id=row.cluster_id)") :]
    assert '@click=' not in activity_link.split('</a>', 1)[0]

    assert 'data-kaori-capability-native-dialogs' in capability
    actions = read('app/templates/integrations/components/_record_actions.html')
    assert 'record_actions.view_more(' in capability
    assert "role='capability'" in capability
    assert 'data-kaori-dialog-open' in actions
    assert 'data-dialog-target="{{ dialog_target }}"' in actions
    assert 'record_detail_modal.render(' in capability
    assert 'data-kaori-native-dialog' in modal
    assert 'onclick=' not in modal
    assert 'dialog.showModal()' in controller


def test_kubernetes_runtime_health_requires_persisted_observation() -> None:
    service = read('app/integrations/service.py')
    presentation = read('app/integrations/runtime/presentation.py')
    runtime = read('app/templates/integrations/kubernetes/partials/_runtime_workspace.html')

    assert 'IntegrationRuntimeObservation.query.filter_by(' in service
    assert "provider='kubernetes'" in service
    assert 'runtime_observation_state_view(' in service
    assert 'def runtime_observation_state_view(' in presentation
    assert "'health_status': 'not_observed'" in presentation
    assert "'health_score_display': 'N/A'" in presentation
    assert 'without inferring health from connection state' in presentation
    assert "runtime_gate_label = 'Observation Required'" in runtime
    assert 'Not Observed' in runtime
    assert 'Persisted Runtime Refresh evidence' in runtime
    assert 'Health gate only; validation remains independent.' in runtime
    assert 'Validation Readiness' in runtime


def test_kubernetes_actions_are_permission_aware() -> None:
    detail = read('app/templates/integrations/kubernetes/detail.html')
    detail_posture = read('app/templates/integrations/components/_provider_detail_posture.html')
    capability = (
        read('app/templates/integrations/kubernetes/partials/_capability_workspace.html')
        + read('app/templates/integrations/kubernetes/partials/_capability_registry.html')
        + read('app/templates/integrations/components/_capability_readiness.html')
    )
    runtime = read('app/templates/integrations/kubernetes/partials/_runtime_workspace.html')
    connection = read('app/templates/integrations/kubernetes/partials/_connection_contract.html')

    assert "current_user.has_permission('clusters.sync')" in detail
    assert 'show_primary_action' in detail_posture
    assert "current_user.has_permission('settings.manage_integrations')" in detail
    routes = read('app/integrations/routes.py')
    assert "@integrations_bp.get('/kubernetes')" in routes
    assert 'def kubernetes() -> ResponseReturnValue:' in routes
    assert "url_for('integrations.kubernetes')" in detail or 'url_for("integrations.kubernetes")' in detail
    assert 'cluster.list_clusters' not in detail
    assert 'Back to Registry' in detail_posture
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
    source_projection = read('app/integrations/asset_owner_sources.py')
    inventory = read('app/templates/integrations/kubernetes/partials/_inventory_lifecycle.html')

    for key in ('source_readiness', 'binding_validation', 'effective_status', 'effective_label'):
        assert f"'{key}'" in source_projection
    shared_sources = read('app/templates/integrations/components/_asset_owner_observability_sources.html')
    for label in ('Source Readiness', 'Binding Validation', 'Effective Resolution'):
        assert label in shared_sources
    assert 'source.status' not in inventory


def test_inventory_freshness_and_capability_dimensions_are_explicit() -> None:
    service = read('app/integrations/service.py')
    inventory = read('app/templates/integrations/kubernetes/partials/_inventory_lifecycle.html')
    detail = read('app/templates/integrations/kubernetes/detail.html')

    assert 'ClusterInventory.query.filter_by(cluster_id=cluster.id)' in service
    assert "'inventory_collected_at_display'" in service
    assert "'validated_feature_count'" in service
    assert "'operational_domain_count'" in service
    assert 'Last Collected' in inventory
    assert 'operational_use.inventory_collected_at_display' in inventory
    assert 'Validated Features' in inventory
    assert 'Operational Domains' in inventory
    assert 'Validated Features' in detail


def test_kubernetes_coverage_uses_canonical_asset_coverage_registry() -> None:
    coverage = read('app/templates/integrations/kubernetes/partials/_integration_coverage.html')

    assert 'Kubernetes Integration Coverage' in coverage
    assert 'kubernetes-coverage-filter-form' in coverage
    assert 'provider_registry.asset_coverage_colgroup()' in coverage
    assert 'provider_registry.asset_coverage_head(' in coverage
    assert 'Kubernetes Cluster' in coverage
    assert 'Kubernetes API' in coverage
    assert 'Metrics Source' not in coverage  # owned by shared head
    assert 'Alert Source' not in coverage  # owned by shared head
    assert 'row.inventory_coverage.status' in coverage
    assert 'row.prometheus_operational.status' in coverage
    assert 'row.alertmanager_operational.status' in coverage
    assert 'row.coverage_summary.status' in coverage
    assert 'components/states/_empty_state.html' in coverage
    assert 'provider_registry.pagination_footer(' in coverage
    assert 'Operational Readiness Paths' not in coverage
    assert 'data-kaori-operational-path-card' not in coverage


def test_secret_capability_is_optional_and_kept_out_of_baseline_readiness() -> None:
    compatibility = read('app/integrations/kubernetes/compatibility.py')
    validation = read('app/integrations/kubernetes/validation.py')
    service = read('app/integrations/service.py')
    capability = (
        read('app/templates/integrations/kubernetes/partials/_capability_workspace.html')
        + read('app/templates/integrations/kubernetes/partials/_capability_registry.html')
        + read('app/templates/integrations/components/_capability_readiness.html')
    )

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


def test_capability_workspace_uses_registry_modal_and_consistent_typography() -> None:
    capability = (
        read('app/templates/integrations/kubernetes/partials/_capability_workspace.html')
        + read('app/templates/integrations/kubernetes/partials/_capability_registry.html')
        + read('app/templates/integrations/components/_capability_readiness.html')
    )
    modal = read('app/templates/integrations/components/_record_detail_modal.html')

    for marker in (
        'data-kaori-capability-workspace-v8',
        'data-kaori-capability-readiness',
        'data-kaori-capability-explorer',
        'data-kaori-capability-matrix',
        'data-kaori-capability-matrix-header',
        'data-kaori-capability-matrix-row',
        'data-kaori-capability-layout',
        'data-kaori-capability-full-width',
        'data-kaori-readiness-score',
        'data-kaori-capability-gate-decision',
        'data-kaori-next-operational-action',
    ):
        assert marker in capability
    assert 'Capability Registry' in capability
    assert 'Search Capability' in capability
    assert 'All Requirements' in capability
    assert 'All Statuses' in capability
    assert "hx-get=\"{{ url_for('integrations.kubernetes_capability_registry'" in capability
    assert 'hx-indicator="#kubernetes-capability-loading"' in capability
    assert 'x-model.debounce.150ms="query"' not in capability
    assert 'x-show="visible({{ loop.index0 }})"' not in capability
    assert 'lg:grid-cols-[minmax(0,1fr)_22rem]' not in capability
    assert 'xl:grid-cols-[minmax(0,1fr)_24rem]' not in capability
    assert '2xl:grid-cols-[minmax(0,1fr)_25rem]' not in capability
    assert 'Kubernetes Capability Readiness' in capability
    assert 'Validation Decision' not in capability
    assert 'data-kaori-capability-side-panel' not in capability
    assert 'Operational Gate' in capability
    assert 'Next Operational Action' in capability
    assert 'Validation Workflow' not in capability
    assert 'Resource' in capability
    assert 'Core Contract' in capability
    assert 'record_actions.view_more(' in capability
    assert "'capability-detail-modal-' ~ loop.index" in capability
    assert 'record_detail_modal.render(' in capability
    assert 'data-kaori-capability-modal-content' in capability
    assert 'data-kaori-capability-modal-v2' in capability
    assert 'data-kaori-capability-modal-v3' in capability
    assert 'Capability Decision' in capability
    assert 'Contract Snapshot' in capability
    assert 'Validation Evidence' in capability
    assert 'Operational Decision' in capability
    assert 'Operational Impact' in capability
    assert 'Recommended Action' in capability
    assert 'Governance Boundary' in capability
    assert 'Verification Command' in capability
    assert 'technical_check.render(' not in capability
    assert 'font-sans' in capability
    assert 'font-mono' not in capability

    assert '<dialog id="{{ modal_id }}"' in modal
    assert 'data-kaori-native-dialog' in modal
    assert 'method="dialog"' in modal
    assert 'max-w-6xl' in modal
    assert 'max-w-5xl' in modal
    assert 'data-kaori-dialog-size="{{ size }}"' in modal
    assert 'data-kaori-dialog-close' in modal
    assert 'onclick=' not in modal
    assert 'x-teleport' not in modal


def test_kubernetes_detail_workspaces_use_connected_standard_surfaces() -> None:
    connection = read('app/templates/integrations/kubernetes/partials/_connection_contract.html')
    capability = (
        read('app/templates/integrations/kubernetes/partials/_capability_workspace.html')
        + read('app/templates/integrations/kubernetes/partials/_capability_registry.html')
        + read('app/templates/integrations/components/_capability_readiness.html')
    )
    inventory = read('app/templates/integrations/kubernetes/partials/_inventory_lifecycle.html')
    runtime = read('app/templates/integrations/kubernetes/partials/_runtime_workspace.html')

    assert 'data-kaori-connection-contract-v2' in connection
    assert 'data-kaori-connection-summary' in connection
    assert 'data-kaori-connection-evidence' in connection
    operational_context = read('app/templates/integrations/components/_provider_operational_context.html')
    assert 'data-kaori-operational-context' in operational_context
    assert 'Connection Summary' in connection
    assert 'Connection Evidence' in connection
    assert 'operational_context.render(' in connection
    assert 'Step {{ loop.index }}' in operational_context
    assert '_minimum_validation_rbac.html' in connection
    assert 'font-sans' in connection
    assert 'font-mono' not in connection

    assert 'data-kaori-capability-workspace-v8' in capability
    assert 'data-kaori-capability-readiness' in capability
    assert 'Capability Matrix' in capability
    assert 'data-kaori-capability-filters' in capability
    assert 'data-kaori-capability-record' in capability
    assert 'Kubernetes Capability Readiness' in capability
    assert 'data-kaori-capability-full-width' in capability
    assert 'font-mono' not in capability

    assert 'data-kaori-inventory-lifecycle-v4' in inventory
    assert 'data-kaori-inventory-lifecycle-v5' in inventory
    assert 'data-kaori-inventory-lifecycle-decision' in inventory
    assert 'Bound Observability Sources' in read(
        'app/templates/integrations/components/_asset_owner_observability_sources.html'
    )
    assert 'components/table.html' in inventory
    assert 'Inventory &amp; Lifecycle Decision' in inventory
    assert 'Retention Boundary' in inventory
    assert 'Removed With Connection' in inventory
    assert 'Retained After Removal' in inventory
    assert 'Next Lifecycle Action' in inventory
    assert 'xl:grid-cols-[minmax(0,1fr)_28rem]' not in inventory
    assert '<aside' not in inventory

    assert 'data-kaori-runtime-workspace-v8' in runtime
    assert 'data-kaori-runtime-decision-summary' in runtime
    assert 'Primary Finding' in runtime
    assert 'Diagnostic Evidence' in runtime
    assert 'data-kaori-runtime-diagnostic-list' in runtime
    assert 'data-kaori-runtime-diagnostic-row' in runtime
    assert 'data-kaori-runtime-observation-boundary' in runtime


def test_kubernetes_runtime_uses_neutral_surfaces_with_controlled_brand_identity() -> None:
    detail = read('app/templates/integrations/kubernetes/detail.html')
    runtime = read('app/templates/integrations/kubernetes/partials/_runtime_workspace.html')
    inventory = read('app/templates/integrations/kubernetes/partials/_inventory_lifecycle.html')
    history = read('app/templates/integrations/partials/_runtime_history.html')

    assert 'data-kaori-runtime-workspace-v8' in runtime
    assert 'data-kaori-runtime-main-layout' in runtime
    assert 'data-kaori-runtime-decision-summary' in runtime
    assert 'data-kaori-runtime-primary-finding' in runtime
    assert 'Primary Finding' in runtime
    assert 'Evidence Boundary' in runtime
    assert 'bg-surface-card' in runtime
    assert "palette_icon('gauge', 'brand'" in runtime
    assert "runtime_history_variant='violet-v2'" not in detail
    assert "runtime_history_variant='violet-v2'" not in runtime

    assert 'data-kaori-inventory-lifecycle-v4' in inventory
    assert 'bg-surface-card' in inventory
    assert 'integration_ui.palette_icon' in inventory
    assert "palette_icon('database', 'brand'" in inventory
    assert 'data-kaori-runtime-history-standard-v2' in history
    assert 'dark:text-kaori-accent' in history


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
    frontpage_service = read('app/integrations/kubernetes_frontpage.py')

    assert 'def bound_sources_for_scopes(' in coverage
    assert 'contains_eager(IntegrationBinding.instance)' in coverage
    assert 'source_maps = {' in coverage
    assert 'bound_sources_for_scopes(' in frontpage_service
    assert "('prometheus', 'alertmanager')" in frontpage_service
    assert 'contains_eager(KubernetesConnection.cluster)' in frontpage_service
    assert '_build_registry_row(connection, bound_sources=bound_sources)' in frontpage_service


def test_kubernetes_integration_overview_uses_controlled_kaori_icon_palette() -> None:
    page = read('app/templates/integrations/kubernetes.html')
    coverage = read('app/templates/integrations/kubernetes/partials/_integration_coverage.html')
    registry = read('app/templates/integrations/kubernetes/partials/_registry.html')
    provider_registry = read('app/templates/integrations/components/_provider_registry.html')

    assert 'data-kaori-kubernetes-integration-icon-palette' in page
    assert 'provider_registry.asset_coverage_head(' in coverage
    assert 'Kubernetes Cluster' in coverage
    assert 'Kubernetes API' in coverage
    assert 'registry_header("Kubernetes Integration Coverage"' in coverage
    assert 'palette_icon("boxes", "brand")' in coverage or "palette_icon('boxes', 'brand')" in coverage
    assert "'tone': 'info'" not in coverage
    assert "'tone': 'warning'" not in coverage
    assert "'provider_tone'" not in coverage
    assert 'data-kaori-kubernetes-registry-icon-palette' in registry
    assert 'connection_icon_tone = "success" if row.readiness == "ready"' in registry
    assert (
        'palette_icon("server-cog", connection_icon_tone)' in registry
        or "palette_icon('server-cog', connection_icon_tone)" in registry
    )
    assert "registry_header(title, description, icon, loading_id, title_id=None, tone='brand')" in provider_registry


def test_kubernetes_integration_uses_canonical_compact_label_roles() -> None:
    page = read('app/templates/integrations/kubernetes.html')
    provider_frontpage = read('app/templates/integrations/components/_provider_frontpage.html')
    coverage = read('app/templates/integrations/kubernetes/partials/_integration_coverage.html')
    registry = read('app/templates/integrations/kubernetes/partials/_registry.html')
    connection = read('app/templates/integrations/kubernetes/partials/_connection_contract.html')
    capability = (
        read('app/templates/integrations/kubernetes/partials/_capability_workspace.html')
        + read('app/templates/integrations/kubernetes/partials/_capability_registry.html')
        + read('app/templates/integrations/components/_capability_readiness.html')
    )
    runtime = read('app/templates/integrations/kubernetes/partials/_runtime_workspace.html')
    inventory = read('app/templates/integrations/kubernetes/partials/_inventory_lifecycle.html')
    history = read('app/templates/integrations/partials/_runtime_history.html')
    labels = read('app/templates/components/table_label.html')
    standard = read('docs/design/components/INTEGRATIONS_WORKSPACE_STANDARD.md')

    assert 'provider_front.hero(' in page
    assert 'display="text"' in provider_frontpage
    detail_posture = read('app/templates/integrations/components/_provider_detail_posture.html')
    assert 'display="text"' in detail_posture
    assert 'display="indicator"' in coverage
    assert 'display="indicator"' in registry
    assert "display='special'" in connection
    assert 'components/table_label.html' in capability
    assert "display='text'" in capability
    assert "display='indicator'" in capability
    assert 'components/table_label.html' in runtime
    assert "metadata_label((runtime_state.diagnostics|length) ~ ' Checks')" in runtime
    assert "display='indicator'" in runtime
    asset_sources = read('app/templates/integrations/components/_asset_owner_observability_sources.html')
    assert 'display="indicator"' in asset_sources
    assert "integration_status(health_tone, row.effective_status_label, display='indicator')" in history
    assert 'Validation · {{ row.readiness_label }}' in history
    assert labels.count('whitespace-nowrap') >= 4
    assert 'Single-Line Compact Label Contract' in standard
