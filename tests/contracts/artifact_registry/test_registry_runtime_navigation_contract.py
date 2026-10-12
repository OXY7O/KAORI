"""Runtime capability navigation contract (#1692 human DevContainer feedback).

Reuse the canonical Layout / Integrated Workspace Tabs. The Runtime sidebar
must land on Overview while old usage and topology links continue to work.
"""

from __future__ import annotations

import ast
from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[3]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_runtime_sidebar_is_capability_first_with_three_level_three_views() -> None:
    catalog = _read('app/common/workspace_navigation_catalog.py')
    navigation = _read('app/common/workspace_navigation.py')

    assert """'runtime',
                'Runtime',
                'waypoints',
                'artifact_registry.runtime_overview'""" in catalog
    views = catalog.rsplit("    'artifact_registry_runtime': (", 1)[1].split(
        "    'artifact_registry_analytics': (", 1
    )[0]
    assert views.count('CapabilityViewDefinition(') == 3
    labels = (
        ('overview', 'Overview', 'artifact_registry.runtime_overview'),
        ('usage', 'Runtime Usage', 'artifact_registry.runtime'),
        ('topology', 'Topology', 'artifact_registry.runtime_topology'),
    )
    positions = []
    for key, label, endpoint in labels:
        marker = f"'{key}', '{label}',"
        assert marker in views
        assert f"'{endpoint}'" in views
        positions.append(views.index(marker))
    assert positions == sorted(positions)
    assert views.count("('artifact_registry.view',)") == 3

    assert "if endpoint.startswith('artifact_registry.runtime'):" in navigation
    assert "return 'artifact_registry_runtime'" in navigation
    assert "'artifact_registry_runtime': 'Runtime'" in navigation
    for endpoint, selected in (
        ('artifact_registry.runtime_overview', 'overview'),
        ('artifact_registry.runtime', 'usage'),
        ('artifact_registry.runtime_topology', 'topology'),
        ('artifact_registry.runtime_topology_data', 'topology'),
        ('artifact_registry.runtime_binding_details', 'usage'),
    ):
        assert f"'{endpoint}': '{selected}'" in navigation
    assert "('artifact_registry.runtime', 'runtime')" in navigation

    for key in ('source_id', 'cluster_id', 'namespace', 'match_type', 'exposure', 'artifact_id', 'q'):
        assert f"'{key}'" in catalog


def test_runtime_routes_and_navigation_remain_authorized_and_compatible() -> None:
    routes = _read('app/artifact_registry/routes.py')
    ast.parse(routes)
    assert (
        "@artifact_registry_bp.get('/runtime/overview')\n"
        "@permission_required('artifact_registry.view')\n"
        "def runtime_overview()"
    ) in routes
    assert "'artifact_registry/runtime_overview.html'" in routes
    assert "runtime=build_runtime_usage(**_runtime_topology_filters())" in routes
    assert "@artifact_registry_bp.get('/runtime')\n@permission_required('artifact_registry.view')" in routes
    assert "@artifact_registry_bp.get('/runtime/topology')\n@permission_required('artifact_registry.view')" in routes
    assert "@artifact_registry_bp.get('/runtime/topology/data')\n@permission_required('artifact_registry.view')" in routes
    assert "@artifact_registry_bp.get('/runtime/<int:binding_id>/details')" in routes
    assert "return jsonify(build_dependency_topology(**_runtime_topology_filters()))" in routes


def test_canonical_tabs_render_above_hero_not_inside_individual_pages() -> None:
    layout = _read('app/templates/layouts/app.html')
    catalog = _read('app/common/navigation.py')
    overview = _read('app/templates/artifact_registry/runtime_overview.html')
    usage = _read('app/templates/artifact_registry/runtime.html')
    usage_workspace = _read('app/templates/artifact_registry/partials/_runtime_workspace.html')
    topology = _read('app/templates/artifact_registry/topology.html')
    tabs = _read('app/templates/components/workspace_tabs.html')

    assert layout.index('workspace_tabs.render_navigation(') < layout.index('{% block dashboard_content %}')
    assert 'data-kaori-tab-variant="integrated-workspace-server"' in tabs
    assert 'aria-current="page"' in tabs

    for page in (overview, usage, topology):
        Environment().parse(page)
        assert 'workspace_tabs.render_navigation(' not in page

    for key in ('runtime_overview', 'runtime', 'runtime_topology'):
        assert f"'artifact_registry.{key}'" in catalog
    assert "elif endpoint.startswith('artifact_registry.runtime'):" in catalog
    assert "BreadcrumbItem('Runtime', 'waypoints')" in catalog

    assert 'Runtime Overview' in overview
    assert 'Runtime Correlation Posture' in overview
    assert 'snapshot_context_bar.render(' in overview
    assert 'Runtime Usage' in overview
    assert 'Topology' in overview
    assert "url_for('artifact_registry.runtime'," in overview
    assert "url_for('artifact_registry.runtime_topology'," in overview
    assert 'Correlation Prerequisites' in overview
    assert 'Runtime Bindings' in usage_workspace
    assert 'Open Dependency Topology' not in usage_workspace
    assert 'Dependency Topology' in topology
