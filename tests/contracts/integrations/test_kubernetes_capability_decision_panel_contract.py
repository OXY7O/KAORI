from pathlib import Path

TEMPLATE = Path("app/templates/integrations/kubernetes/partials/_capability_workspace.html")


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
    source = _source()

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
    source = _source()

    assert 'data-kaori-capability-filters' in source
    assert 'lg:grid-cols-[minmax(0,1fr)_14rem_14rem]' in source
    assert 'table-fixed' in source
    assert 'min-w-[760px]' not in source
    assert 'min-w-[820px]' not in source
    assert 'overflow-x-auto' not in source


def test_capability_registry_uses_kaori_pagination_and_loading_contract():
    source = _source()

    assert 'components/pagination.html' in source
    assert 'components/loading_bar.html' in source
    assert "loading_bar.render('kubernetes-capability-loading', active=validation_job and validation_job.is_active" in source
    assert 'hx-indicator="#kubernetes-capability-loading"' in source
    assert 'data-kaori-capability-loading-region' in source
    assert 'capabilityLoading:' not in source
    assert 'x-on:htmx:before-request="capabilityLoading = true"' not in source
    assert 'x-show="capabilityLoading"' not in source
    assert 'data-kaori-capability-pagination' in source
    assert 'pageSize: 5' in source
    assert '[5, 10, 25, 50]' in source
    assert 'Showing <span' in source
    assert '> Capabilities</p>' in source
    assert 'Previous' in source
    assert 'Next' in source


def test_capability_registry_keeps_readiness_progress_and_modal_detail_boundary():
    source = _source()

    assert 'aria-label="Capability readiness"' in source
    assert "bg-kaori-primary" in source
    assert "record_actions.view_more(" in source
    assert "record_detail_modal.render(" in source
    assert "Capability Decision" in source
    assert "Contract Snapshot" in source
    assert "Validation Evidence" in source
    assert "Operational Decision" in source
    assert "Verification Command" in source
