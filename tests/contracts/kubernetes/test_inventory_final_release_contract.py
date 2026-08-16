from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_inventory_final_lock_is_wired_into_release_gate() -> None:
    quality_gate = read('scripts/quality_gate.sh')
    core_lock = read('scripts/verify_core_kubernetes_final_lock.py')

    assert 'python scripts/verify_inventory_final_lock.py' in quality_gate
    assert 'verify_inventory_final_lock.py' in core_lock


def test_inventory_final_standard_documents_authz_snapshot_and_shared_ui_contracts() -> None:
    standard = read('docs/design/patterns/INVENTORY_RESOURCE_PAGE.md')

    assert 'Authorization before blocker evaluation' in standard
    assert 'committed inventory generation' in standard
    assert 'Status Badge Box' in standard
    assert 'Full Workspace Modal' in standard
    assert '5 / 10 / 25 / 50' in standard


def test_inventory_read_side_no_longer_owns_obsolete_template_or_helpers() -> None:
    assert not (ROOT / 'app/templates/inventory/partials/_README.md').exists()
    formatting = read('app/inventory/kubernetes/formatting.py')
    common = read('app/inventory/kubernetes/resources/common.py')

    assert 'def format_byte_count(' not in formatting
    assert 'def format_gib(' not in formatting
    assert 'def _split_inventory_values(' not in common


def test_topology_cluster_identity_uses_eager_loaded_database_relationship_not_runtime_resolver() -> None:
    repository = read('app/inventory/kubernetes/topology/repository.py')
    builder = read('app/inventory/kubernetes/topology/node_builder.py')

    assert 'joinedload(Cluster.kubernetes_connection)' in repository
    assert 'cluster.kubernetes_connection.server' in builder
    assert 'app.integrations.kubernetes.resolver' not in builder


def test_inventory_resource_template_registry_uses_the_canonical_kubernetes_namespace() -> None:
    routes = read('app/inventory/kubernetes/routes.py')
    resources = ('nodes', 'namespaces', 'configuration', 'workloads', 'pods', 'services', 'ingresses', 'storage')

    assert "f'inventory/kubernetes/{resource}/index.html'" in routes
    assert "f'inventory/kubernetes/{resource}/partials/_page_workspace.html'" in routes
    assert "f'inventory/kubernetes/{resource}/partials/_table_card.html'" in routes
    assert "f'inventory/kubernetes/{resource}/partials/_table_content.html'" in routes
    assert "f'inventory/{resource}/index.html'" not in routes

    for resource in resources:
        base = ROOT / 'app/templates/inventory/kubernetes' / resource
        assert (base / 'index.html').is_file(), resource
        assert (base / 'partials/_page_workspace.html').is_file(), resource
        assert (base / 'partials/_table_card.html').is_file(), resource
        assert (base / 'partials/_table_content.html').is_file(), resource


def test_storage_inventory_populates_the_shared_scope_label_used_by_its_hero() -> None:
    routes = read('app/inventory/kubernetes/routes.py')
    storage_block = routes[routes.index('def storage():') : routes.index('def storage_details(')]

    assert "inventory['scope_label'] = _inventory_scope_label(clusters, cluster_id)" in storage_block
