from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_storage_removes_nonfunctional_composite_tracker() -> None:
    index = read('app/templates/analytics/storage/index.html')

    assert 'storage-load-tracker' not in index
    assert 'analytics/partials/_load_tracker.html' not in index
    assert 'data-analytics-page-request-tracking="false"' in index


def test_storage_heavy_record_tabs_load_on_first_activation() -> None:
    section = read('app/templates/analytics/storage/partials/_storage_section.html')

    assert section.count('kaori:analytics-tab-activated once') == 3
    assert "storage_filesystem_summary" in section
    assert section.count("storage_persistent_summary") >= 2
    assert 'storage-filesystem-lazy-indicator' in section
    assert 'persistent-volume-claims-lazy-indicator' in section
    assert 'persistent-volumes-lazy-indicator' in section


def test_storage_uses_canonical_tab_and_mixed_scope_ownership() -> None:
    routes = read('app/analytics/storage/routes.py')
    presentation = read('app/analytics/storage/presentation.py')
    controls = read('app/templates/analytics/storage/partials/_controls_readiness.html')
    filesystem = read('app/templates/analytics/storage/partials/_filesystem_panel.html')
    contract = read('docs/design/components/ANALYTICS_STORAGE_ANALYSIS.md')

    assert "STORAGE_TABS = ('capacity', 'filesystem', 'pvc', 'pv', 'recommendations')" in presentation
    assert "name='tab'" in presentation
    assert "name='storage_tab'" not in presentation
    assert "parameters=_snapshot_parameters()" in routes
    assert "return {'cluster_id': cluster_id}" in routes
    assert 'name="namespace"' in controls
    assert "record_filter.select('storage_node'" in filesystem
    assert 'Node is local to the Filesystem tab' in contract
    assert 'PVC evidence follows Namespace' in contract
    assert 'PV evidence remains cluster-scoped' in contract


def test_storage_primary_evidence_and_operational_reading_use_neutral_cards() -> None:
    overview = read('app/templates/analytics/storage/partials/_overview.html')
    capacity = read('app/templates/analytics/storage/partials/_capacity_utilization_panel.html')
    filesystem = read('app/templates/analytics/storage/partials/_filesystem_panel.html')
    pvc = read('app/templates/analytics/storage/partials/_persistent_volume_claims_panel.html')
    pv = read('app/templates/analytics/storage/partials/_persistent_volumes_panel.html')

    assert 'analysis_surface.evidence_shell_classes()' in overview
    assert 'analysis_surface.guidance_card_classes()' in overview
    assert 'data-kaori-operational-reading' in overview
    assert 'analysis_surface.guidance_fact_grid_classes(3)' in overview
    assert 'Keep Node, Namespace, And Cluster Storage Evidence Separate' in overview
    assert 'resource_pressure_lane.render(' in capacity
    assert 'analysis_surface.interpretation_grid_classes()' in capacity
    assert 'evidence_list.shell(' in filesystem
    assert 'evidence_list.shell(' in pvc
    assert 'evidence_list.shell(' in pv
    assert 'analysis_surface.record_guidance_classes()' in pv


def test_storage_record_panels_use_shared_filter_and_record_components() -> None:
    filesystem = read('app/templates/analytics/storage/partials/_filesystem_panel.html')
    pvc = read('app/templates/analytics/storage/partials/_persistent_volume_claims_panel.html')
    pv = read('app/templates/analytics/storage/partials/_persistent_volumes_panel.html')
    record_component = read('app/templates/analytics/components/_evidence_record_list.html')
    filter_component = read('app/templates/analytics/components/_record_filter_bar.html')

    for source, record_key in (
        (filesystem, 'filesystem'),
        (pvc, 'pvc'),
        (pv, 'pv'),
    ):
        assert 'record_filter.form(' in source
        assert 'evidence_list.shell(' in source
        assert 'embedded=true' in source
        assert f'data-kaori-storage-record-card="{record_key}"' in source

    assert 'Node Filesystem Records' in filesystem
    assert 'Persistent Volume Claim Records' in pvc
    assert 'Persistent Volume Records' in pv
    assert 'macro header_cell' in record_component
    assert 'macro mobile_label' in record_component
    assert 'macro form' in filter_component
    assert 'macro search' in filter_component
    assert 'macro select' in filter_component


def test_storage_pagination_owns_full_href_and_partial_htmx_endpoint() -> None:
    pagination = read('app/templates/analytics/components/_record_pagination.html')
    shared = read('app/templates/components/pagination.html')
    filesystem = read('app/templates/analytics/storage/partials/_filesystem_panel.html')
    pvc = read('app/templates/analytics/storage/partials/_persistent_volume_claims_panel.html')
    pv = read('app/templates/analytics/storage/partials/_persistent_volumes_panel.html')

    assert 'href_endpoint' in pagination
    assert 'partial_endpoint' in pagination
    assert "'filesystem_page'" in filesystem
    assert "'pvc_page'" in pvc
    assert "'pv_page'" in pv
    assert "'analytics.storage'" in filesystem
    assert "'analytics.storage'" in pvc
    assert "'analytics.storage'" in pv
    assert 'href_endpoint=None' in shared
    assert 'page_hx_url' in shared
    assert "response.headers['HX-Push-Url']" in read('app/analytics/storage/routes.py')


def test_storage_lifecycle_tones_are_domain_semantics_not_css_parsing() -> None:
    domain = read('app/analytics/storage/domain.py')
    filesystem = read('app/templates/analytics/storage/partials/_filesystem_panel.html')
    pvc = read('app/templates/analytics/storage/partials/_persistent_volume_claims_panel.html')
    pv = read('app/templates/analytics/storage/partials/_persistent_volumes_panel.html')

    assert "'Bound': 'normal'" in domain
    assert "'Pending': 'warning'" in domain
    assert "'Lost': 'critical'" in domain
    assert "'Available': 'info'" in domain
    assert "'Released': 'warning'" in domain
    assert "'Failed': 'critical'" in domain
    for source in (filesystem, pvc, pv):
        assert 'risk_lower' not in source
        assert 'risk.class' not in source


def test_storage_templates_remove_local_micro_typography_debt() -> None:
    paths = [
        'app/templates/analytics/storage/partials/_hero.html',
        'app/templates/analytics/storage/partials/_overview.html',
        'app/templates/analytics/storage/partials/_capacity_utilization_panel.html',
        'app/templates/analytics/storage/partials/_filesystem_panel.html',
        'app/templates/analytics/storage/partials/_persistent_volume_claims_panel.html',
        'app/templates/analytics/storage/partials/_persistent_volumes_panel.html',
        'app/templates/analytics/storage/partials/_recommendations.html',
    ]
    for path in paths:
        source = read(path)
        assert 'text-[10px]' not in source, path
        assert 'text-[11px]' not in source, path
        assert 'tracking-[' not in source, path


def test_storage_standard_is_documented_and_registered() -> None:
    guide = read('docs/design/KAORI_STYLING_GUIDE.md')
    design_readme = read('docs/design/README.md')
    analysis = read('docs/design/components/ANALYTICS_ANALYSIS_SURFACES.md')
    storage = read('docs/design/components/ANALYTICS_STORAGE_ANALYSIS.md')

    assert 'Analytics Storage Analysis Standard' in guide
    assert 'components/ANALYTICS_STORAGE_ANALYSIS.md' in design_readme
    assert 'Evidence Record Collection' in analysis
    assert 'Mixed-Scope Analytics' in analysis
    assert 'Observed PVC usage must never be labeled as PV utilization' in guide
    assert 'The canonical workspace parameter is `tab`' in storage


def test_storage_pvc_partial_coverage_is_visible_without_hiding_valid_totals() -> None:
    domain = read('app/analytics/storage/domain.py')
    overview = read('app/templates/analytics/storage/partials/_overview.html')
    pvc = read('app/templates/analytics/storage/partials/_persistent_volume_claims_panel.html')
    hero = read('app/templates/analytics/storage/partials/_hero.html')
    presentation = read('app/analytics/storage/presentation.py')

    assert "'capacity_evidence_complete': capacity_complete" in domain
    assert "'pressure_evidence_complete': pressure_complete" in domain
    assert "'pressure_coverage_display'" in domain
    assert "'pressure_capacity'" in domain
    assert "'pressure_used'" in domain
    assert 'pressure_rows = [' in domain
    assert 'Partial aggregate:' in overview
    assert 'Coverage {{ pvc.pressure_coverage_display }}' in overview
    assert 'pvc.capacity_coverage_display' in pvc
    assert 'pvc.used_coverage_display' in pvc
    assert 'pvc.evidence_gap_count' in pvc
    assert 'pvc.pressure_coverage_display' in hero
    assert "pvc.get('pressure_used', 'N/A')" in presentation
    assert "pvc.get('pressure_capacity', 'N/A')" in presentation
