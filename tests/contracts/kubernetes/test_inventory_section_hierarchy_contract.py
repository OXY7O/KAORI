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
