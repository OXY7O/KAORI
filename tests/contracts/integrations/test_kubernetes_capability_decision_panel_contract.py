from pathlib import Path

TEMPLATE = Path("app/templates/integrations/kubernetes/partials/_capability_workspace.html")
REGISTRY = Path("app/templates/integrations/kubernetes/partials/_capability_registry.html")
ROUTES = Path("app/integrations/routes.py")
SERVICE = Path("app/integrations/service.py")


def _source() -> str:
    return TEMPLATE.read_text(encoding="utf-8")


def test_capability_readiness_merges_overview_and_decision_into_one_surface():
    source = _source()

    assert "data-kaori-capability-decision-summary" in source
    assert "Kubernetes Capability Readiness" in source
    assert "Capability Coverage" in source
    assert "Required Usable" in source
    assert "Stable APIs" in source
    assert "Required Blocks" in source
    assert "Operational Gate" in source
    assert "Next Operational Action" in source


def test_capability_workspace_removes_redundant_validation_side_rail():
    source = _source()

    assert "data-kaori-capability-side-rail-layout" not in source
    assert "data-kaori-capability-side-panel" not in source
    assert "data-kaori-capability-decision-panel" not in source
    assert "Validation Decision" not in source
    assert "lg:grid-cols-[minmax(0,1fr)_22rem]" not in source
    assert "xl:grid-cols-[minmax(0,1fr)_24rem]" not in source
    assert "2xl:grid-cols-[minmax(0,1fr)_25rem]" not in source


def test_capability_registry_is_full_width_and_uses_standard_kaori_table():
    source = REGISTRY.read_text(encoding="utf-8")

    assert "data-kaori-capability-full-width" in source
    assert "data-kaori-capability-table-standard" in source
    assert "Capability Registry" in source
    assert "table_ui.table_classes()" in source
    assert "table_ui.head_classes()" in source
    assert "table_ui.row_classes()" in source
    assert "table_ui.cell_classes()" in source
    for label in ("Capability", "Resource", "API Contract", "Requirement", "Status", "Details"):
        assert f">{label}<" in source


def test_capability_registry_filters_do_not_force_horizontal_scroll():
    source = REGISTRY.read_text(encoding="utf-8")

    assert 'data-kaori-capability-filters' in source
    assert 'lg:grid-cols-[minmax(0,1fr)_14rem_14rem]' in source
    assert 'table-fixed' in source
    assert 'min-w-[760px]' not in source
    assert 'min-w-[820px]' not in source
    assert 'overflow-x-auto' not in source


def test_capability_registry_uses_runtime_history_style_htmx_loading_contract():
    source = REGISTRY.read_text(encoding="utf-8")
    routes = ROUTES.read_text(encoding="utf-8")
    service = SERVICE.read_text(encoding="utf-8")

    assert 'components/pagination.html' in source
    assert 'components/loading_bar.html' in source
    assert "loading_bar.render('kubernetes-capability-loading', active=validation_job and validation_job.is_active" in source
    assert 'hx-indicator="#kubernetes-capability-loading"' in source
    assert 'data-kaori-capability-loading-region' in source
    assert "hx-get=\"{{ url_for('integrations.kubernetes_capability_registry'" in source
    assert 'hx-trigger="input changed delay:300ms from:#kubernetes-capability-search, change delay:100ms from:select"' in source
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
    source = REGISTRY.read_text(encoding="utf-8")

    assert 'aria-label="Capability readiness"' in workspace
    assert "bg-kaori-primary" in workspace

    assert "record_actions.view_more(" in source
    assert "record_detail_modal.render(" in source
    assert "Capability Decision" in source
    assert "Contract Snapshot" in source
    assert "Validation Evidence" in source
    assert "Operational Decision" in source
    assert "Verification Command" in source
