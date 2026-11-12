from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
INVENTORY_ROOT = ROOT / 'app/templates/kubernetes/inventory'

RESOURCE_PAGES = (
    'nodes',
    'namespaces',
    'workloads',
    'pods',
    'services',
    'ingresses',
    'storage',
    'configuration',
)


def read(path: Path | str) -> str:
    target = ROOT / path if isinstance(path, str) else path
    return target.read_text(encoding='utf-8')


def test_shared_section_intro_owns_the_accepted_plain_hierarchy() -> None:
    component = read('app/templates/components/section_intro.html')
    docs = read('docs/design/components/SECTION_INTRO.md')

    assert 'macro render(title, description, id=None, supporting=None' in component
    assert 'text-lg font-semibold text-content-primary' in component
    assert 'text-sm leading-6 text-content-secondary' in component
    assert 'bg-surface-card' not in component
    assert 'border-outline' not in component
    assert 'not a Hero' in docs
    assert 'not a card' in docs


def test_every_inventory_resource_page_uses_shared_section_hierarchy() -> None:
    for page in RESOURCE_PAGES:
        workspace = read(INVENTORY_ROOT / page / 'partials/_page_workspace.html')
        assert 'components/section_intro.html' in workspace, page
        assert "'Operational Posture'" in workspace, page
        assert "'Inventory Records'" in workspace, page
        assert f"'{page}-posture-heading'" in workspace, page
        assert f"'{page}-records-heading'" in workspace, page
        assert 'aria-labelledby=' in workspace, page
        assert workspace.index('kubernetes/inventory/components/_data_freshness.html') < workspace.index(
            "'Operational Posture'"
        )
        assert workspace.index("'Operational Posture'") < workspace.index("'Inventory Records'")


def test_inventory_overview_and_topology_use_the_same_hierarchy() -> None:
    overview = read(INVENTORY_ROOT / 'overview/index.html')
    topology = read(INVENTORY_ROOT / 'topology/index.html')

    assert 'components/section_intro.html' in overview
    assert "'Inventory Assets'" in overview
    assert "'Multi-Cluster Inventory'" in overview
    assert overview.index("'Inventory Assets'") < overview.index("'Multi-Cluster Inventory'")

    assert 'components/section_intro.html' in topology
    assert "'Inventory Relationships'" in topology
    assert topology.index('kubernetes/inventory/components/_data_freshness.html') < topology.index(
        "'Inventory Relationships'"
    )


def test_inventory_posture_headers_reuse_the_asset_catalog_metadata_label() -> None:
    catalog = read(INVENTORY_ROOT / 'overview/partials/_kpi_cards.html')
    assert 'table_label.metadata_label(overview.asset_catalog|length' in catalog

    for page in RESOURCE_PAGES:
        posture = read(INVENTORY_ROOT / page / 'partials/_summary_cards.html')
        list_name = 'metrics' if page in {'services', 'ingresses', 'storage'} else 'posture_metrics'
        assert 'components/table_label.html' in posture, page
        assert f"table_label.metadata_label({list_name}|length ~ ' Indicators'" in posture, page
        assert 'header_badge=posture_badge' in posture, page
        assert f'posture_grid.render({list_name},' in posture, page
        assert "operational_section_card.render(" in posture, page


def test_topology_relationship_header_badge_tracks_committed_graph_updates() -> None:
    topology = read(INVENTORY_ROOT / 'topology/partials/_workspace.html')
    visualization = read('app/templates/components/visualization_workspace.html')
    labels = read('app/templates/components/table_label.html')
    script = read('app/static/js/kubernetes/inventory/topology.js')

    assert "table_label.count_text(graph.summary.relationships, 'Relationship')" in topology
    assert "text_id='topology-relationship-badge-count'" in topology
    assert 'header_badge=relationship_badge' in topology
    assert 'header_badge=None' in visualization
    assert 'if header_badge' in visualization
    assert 'text_id=None' in labels
    assert 'id="{{ text_id }}"' in labels
    assert "const updateSummary = (payload) => {" in script
    assert "Number(summary.relationships ?? 0)" in script
    assert "'topology-relationship-badge-count'" in script
    assert "topology-hero-relationships" in script


def test_cluster_source_actions_use_open_cluster_integrations() -> None:
    hero_paths = [
        INVENTORY_ROOT / 'overview/partials/_hero.html',
        INVENTORY_ROOT / 'topology/partials/_hero.html',
        *[INVENTORY_ROOT / page / 'partials/_hero.html' for page in RESOURCE_PAGES],
        ROOT / 'app/templates/kubernetes/governance/tls_certificates/partials/_hero.html',
    ]
    table_paths = [
        INVENTORY_ROOT / 'overview/partials/_resources_by_cluster.html',
        *[INVENTORY_ROOT / page / 'partials/_table_card.html' for page in RESOURCE_PAGES],
        ROOT / 'app/templates/kubernetes/governance/tls_certificates/partials/_table.html',
    ]

    for path in [*hero_paths, *table_paths]:
        source = read(path)
        if "url_for('integrations.kubernetes')" not in source:
            continue
        assert 'Manage Clusters' not in source, str(path)
        assert 'Open Cluster List' not in source, str(path)
        assert 'Open Cluster Integrations' in source, str(path)


def test_tls_registry_matches_inventory_section_hierarchy() -> None:
    workspace = read('app/templates/kubernetes/governance/tls_certificates/partials/_page_workspace.html')
    summary = read('app/templates/kubernetes/governance/tls_certificates/partials/_summary_cards.html')
    sync_panel = read('app/templates/kubernetes/governance/tls_certificates/partials/_sync_panel.html')

    assert 'components/section_intro.html' in workspace
    assert workspace.index('partials/_snapshot_context.html') < workspace.index('partials/_sync_panel.html')
    assert workspace.index('partials/_sync_panel.html') < workspace.index("'Certificate Posture'")
    assert workspace.index("'Certificate Posture'") < workspace.index("'Certificate Inventory'")
    assert workspace.index("'Certificate Inventory'") < workspace.index('partials/_table.html')
    assert 'Certificate Validity & Operations' not in summary
    assert 'Certificate Validity' in summary
    assert 'TLS Inventory Operations' not in summary
    assert 'aria-labelledby="tls-inventory-operations-heading"' in sync_panel
