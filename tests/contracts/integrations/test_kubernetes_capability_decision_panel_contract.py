from pathlib import Path

TEMPLATE = Path(
    'app/templates/integrations/orchestration/container_orchestrator/providers/kubernetes/partials/_capability_workspace.html'
)
REGISTRY = Path(
    'app/templates/integrations/orchestration/container_orchestrator/providers/kubernetes/partials/_capability_registry.html'
)
READINESS = Path('app/templates/integrations/components/_capability_readiness.html')
ROUTES = Path('app/integrations/routes.py')
SERVICE = Path('app/integrations/service.py')


def _source() -> str:
    return TEMPLATE.read_text(encoding='utf-8')


def test_capability_readiness_uses_shared_provider_surface():
    source = _source()
    shared = READINESS.read_text(encoding='utf-8')

    assert 'integrations/components/_capability_readiness.html' in source
    assert 'capability_readiness.render(' in source
    assert 'Kubernetes Capability Readiness' in source
    assert 'Validated Capabilities' in source
    assert 'Legacy Fallbacks' in source
    assert 'Required Blocks' in source
    assert 'data-kaori-capability-readiness' in shared
    assert 'Operational Gate' in shared
    assert 'Evidence Boundary' in shared
    assert 'Next Operational Action' in shared
    assert 'bg-surface-subtle' in shared
    assert 'bg-kaori-primary' in shared

    # Presentation geometry belongs to the shared component, not this provider page.
    assert 'data-kaori-capability-overview' not in source
    assert 'progress_bar.bar(' not in source


def test_capability_workspace_removes_redundant_validation_side_rail():
    source = _source()

    assert 'data-kaori-capability-side-rail-layout' not in source
    assert 'data-kaori-capability-side-panel' not in source
    assert 'data-kaori-capability-decision-panel' not in source
    assert 'Validation Decision' not in source
    assert 'lg:grid-cols-[minmax(0,1fr)_22rem]' not in source
    assert 'xl:grid-cols-[minmax(0,1fr)_24rem]' not in source
    assert '2xl:grid-cols-[minmax(0,1fr)_25rem]' not in source


def test_capability_registry_is_full_width_and_uses_standard_kaori_table():
    source = REGISTRY.read_text(encoding='utf-8')

    assert 'data-kaori-capability-full-width' in source
    assert 'data-kaori-capability-table-standard' in source
    assert 'Capability Registry' in source
    assert 'table_ui.table_classes()' in source
    assert 'table_ui.head_classes()' in source
    assert 'table_ui.row_classes()' in source
    assert 'table_ui.cell_classes()' in source
    for label in ('Capability', 'Resource', 'API Contract', 'Requirement', 'Status', 'Details'):
        assert f'>{label}<' in source


def test_capability_registry_filters_do_not_force_horizontal_scroll():
    source = REGISTRY.read_text(encoding='utf-8')

    assert 'data-kaori-capability-filters' in source
    assert 'table_ui.filter_layout_classes()' in source
    assert 'lg:grid-cols-[minmax(0,1fr)_14rem_14rem]' not in source
    assert 'table-fixed' in source
    assert 'min-w-[760px]' not in source
    assert 'min-w-[820px]' not in source
    assert 'overflow-x-auto' not in source


def test_capability_registry_uses_runtime_history_style_htmx_loading_contract():
    source = REGISTRY.read_text(encoding='utf-8')
    routes = ROUTES.read_text(encoding='utf-8')
    service = SERVICE.read_text(encoding='utf-8')

    assert 'components/pagination.html' in source
    assert 'components/loading_bar.html' in source
    assert "loading_bar.render('kubernetes-capability-loading', label='Refreshing Capability Registry')" in source
    assert 'active=validation_job and validation_job.is_active' not in source
    assert 'hx-indicator="#kubernetes-capability-loading"' in source
    assert 'data-kaori-capability-loading-region' in source
    assert "hx-get=\"{{ url_for('integrations.kubernetes_capability_registry'" in source
    assert (
        'hx-trigger="input changed delay:300ms from:#kubernetes-capability-search, change delay:100ms from:select"'
        in source
    )
    assert 'data-kaori-auto-submit' in source
    assert 'pagination_ui.numeric_pages(' in source
    assert 'capability_page' in source
    assert 'capability_per_page' in source
    assert "@integrations_bp.get('/kubernetes/<string:cluster_id>/capabilities/registry')" in routes
    assert 'def kubernetes_capability_registry(' in routes
    assert 'def build_kubernetes_capability_registry(' in service

    # No page-local fake loading state: filters are real HTMX requests, matching
    # Recent Runtime Observations and the rest of KAORI server-backed tables.
    for legacy_token in (
        'registryLoading:',
        'validationActive:',
        'showRegistryLoading()',
        'loadingTimer:',
        'x-show="registryLoading"',
        'pageSize: 5',
        'filteredRows()',
    ):
        assert legacy_token not in source
        assert legacy_token not in _source()

    assert 'data-kaori-capability-pagination' in source
    assert 'Showing <span' in source
    assert 'Previous' in source
    assert 'Next' in source


def test_capability_registry_keeps_readiness_progress_and_modal_detail_boundary():
    workspace = _source()
    shared = READINESS.read_text(encoding='utf-8')
    source = REGISTRY.read_text(encoding='utf-8')

    assert 'capability_readiness.render(' in workspace
    assert 'progress_bar.bar(' in shared
    assert 'bg-kaori-primary' in shared

    assert 'record_actions.view_more(' in source
    assert 'record_detail_modal.render(' in source
    assert 'Capability Decision' in source
    assert 'Contract Snapshot' in source
    assert 'Validation Evidence' in source
    assert 'Operational Decision' in source
    assert 'Verification Command' in source


def test_optional_capability_gaps_are_separate_from_core_readiness() -> None:
    workspace = _source()
    registry = REGISTRY.read_text(encoding='utf-8')

    assert "{% set capability_readiness_state = 'blocked' %}" in workspace
    assert "{% elif legacy_features %}" in workspace
    assert "{% set capability_readiness_state = 'ready' %}" in workspace
    assert (
        'Core required API and RBAC evidence for Kubernetes workspaces; '
        'optional Tenant contracts are tracked separately.'
        in workspace
    )
    assert 'Why Provider Validation Is {{ validation_state.readiness_label }}' in workspace
    assert "' required blocks'" in workspace
    assert "' optional gaps'" in workspace
    assert '>Unavailable / Gap</option>' in registry
    assert "'Optional Gap' if optional_gap else 'Required Block'" in registry
    assert 'Optional Capability Unavailable' in registry
    assert (
        'This optional Tenant capability is unavailable. Core readiness is unaffected; '
        'no supported API contract currently satisfies the required verbs.'
        in registry
    )
    assert 'Cluster-scoped optional governance contract' in registry
    assert 'workflow-required access; do not broaden the baseline ClusterRole' in registry


def test_capability_modal_does_not_guess_commands_without_selected_contract() -> None:
    registry = REGISTRY.read_text(encoding='utf-8')

    assert "has_selected_contract = row.api_version != 'Not selected' and row.resource != '-'" in registry
    assert "row.key[:17] == 'tenant.admission.'" in registry
    assert 'data-kaori-capability-verification-unavailable' in registry
    assert 'No executable command is generated without a selected API/resource contract.' in registry
    assert (
        'No API/resource contract was selected. Enable the approved workflow, '
        'then rerun Full Validation.'
        in registry
    )
    assert 'Optional admission-governance access is cluster scoped' in registry


def test_capability_copy_keeps_optional_governance_concise() -> None:
    workspace = _source()
    registry = REGISTRY.read_text(encoding='utf-8')

    assert (
        'Required API/RBAC contracts are usable; optional Tenant access stays workflow-scoped.'
        in workspace
    )
    assert 'Optional workflows must establish their own approved access boundary.' in registry
    assert (
        'Full Validation owns API/RBAC readiness; runtime and inventory remain separate.'
        in registry
    )
