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

    assert (
        """'runtime',
                'Runtime',
                'waypoints',
                'artifact_registry.runtime_overview'"""
        in catalog
    )
    # Validate the actual catalog definition, not Ruff-dependent multiline layout.
    catalog_ast = ast.parse(catalog)
    capability_views = next(
        stmt.value
        for stmt in catalog_ast.body
        if isinstance(stmt, ast.AnnAssign)
        and isinstance(stmt.target, ast.Name)
        and stmt.target.id == '_CAPABILITY_VIEWS'
    )
    assert isinstance(capability_views, ast.Dict)
    runtime_view_nodes = next(
        value
        for key, value in zip(capability_views.keys, capability_views.values, strict=True)
        if isinstance(key, ast.Constant) and key.value == 'artifact_registry_runtime'
    )
    assert isinstance(runtime_view_nodes, ast.Tuple)
    actual_views = [
        (
            ast.literal_eval(call.args[0]),
            ast.literal_eval(call.args[1]),
            ast.literal_eval(call.args[3]),
            ast.literal_eval(call.args[4]),
        )
        for call in runtime_view_nodes.elts
        if isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id == 'CapabilityViewDefinition'
    ]
    assert actual_views == [
        ('overview', 'Overview', 'artifact_registry.runtime_overview', ('artifact_registry.view',)),
        ('usage', 'Runtime Usage', 'artifact_registry.runtime', ('artifact_registry.view',)),
        ('topology', 'Topology', 'artifact_registry.runtime_topology', ('artifact_registry.view',)),
    ]

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
        'def runtime_overview()'
    ) in routes
    assert "'artifact_registry/runtime_overview.html'" in routes
    assert 'runtime=build_runtime_usage(**_runtime_topology_filters())' in routes
    assert "@artifact_registry_bp.get('/runtime')\n@permission_required('artifact_registry.view')" in routes
    assert "@artifact_registry_bp.get('/runtime/topology')\n@permission_required('artifact_registry.view')" in routes
    assert (
        "@artifact_registry_bp.get('/runtime/topology/data')\n@permission_required('artifact_registry.view')" in routes
    )
    assert "@artifact_registry_bp.get('/runtime/<int:binding_id>/details')" in routes
    assert 'return jsonify(build_dependency_topology(**_runtime_topology_filters()))' in routes


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
    assert 'Runtime Evidence Posture' in overview
    assert 'snapshot_context_bar.render(' in overview
    assert 'Runtime Usage' in overview
    assert 'Topology' in overview
    assert "url_for('artifact_registry.runtime'," in overview
    assert "url_for('artifact_registry.runtime_topology'," in overview
    assert 'Correlation Prerequisites' in overview
    assert 'Runtime Bindings' in usage_workspace
    assert 'Open Dependency Topology' not in usage_workspace
    assert 'Dependency Topology' in topology


def test_runtime_overview_reuses_security_catalog_and_compact_posture() -> None:
    """Runtime and Security keep the same snapshot > workspaces > posture order."""
    runtime = _read('app/templates/artifact_registry/runtime_overview.html')
    security = _read('app/templates/artifact_registry/partials/_security_overview.html')
    workspace = _read('app/templates/components/workspace_link_card.html')
    clipboard_free = _read('app/templates/components/resource_posture_grid.html')

    Environment().parse(runtime)

    for page in (runtime, security):
        assert page.index('snapshot_context_bar.render(') < page.index("'2 Workspaces'")
        assert page.index("'2 Workspaces'") < page.index('posture_grid.render(')
        assert "workspace_card.render({" in page
        assert page.count('}, compact=true)') == 2
        assert "body_classes='p-5'" in page
        assert 'header_badge=workspace_badge' in page
        assert 'header_badge=posture_badge' in page
        assert 'posture_grid.render(' in page
        assert 'compact=true)' in page

    assert 'components/workspace_link_card.html' in runtime
    assert 'components/table_label.html' in runtime
    assert 'components/inventory_asset_card.html' not in runtime
    assert "section_intro.render('Runtime Workspaces'" in runtime
    assert "'Runtime Workspace Catalog'" in runtime
    assert "'Registry Runtime Evidence'" in runtime
    assert "section_intro.render('Runtime Evidence Posture'" in runtime
    assert "table_label.metadata_label('2 Workspaces', icon='layout-grid')" in runtime
    assert "table_label.metadata_label(runtime_metrics|length ~ ' Indicators', icon='layout-grid')" in runtime
    assert 'posture_grid.render(runtime_metrics, columns=4, compact=true)' in runtime
    assert 'md:grid-cols-4' in clipboard_free
    assert 'data-workspace-card' in workspace

    # Preserve the exact committed read-model values, URL-backed scope and RBAC route.
    assert "url_for('artifact_registry.runtime'," in runtime
    assert "url_for('artifact_registry.runtime_topology'," in runtime
    for name in ('q', 'source_id', 'cluster_id', 'namespace', 'match_type', 'exposure', 'artifact_id'):
        assert f'{name}=runtime.filters.' in runtime
    assert "'href': usage_url" in runtime
    assert "'href': topology_url" in runtime
    assert "'scope': runtime.total ~ ' Bindings'" in runtime
    assert "'scope': runtime.artifact_count ~ ' Artifacts'" in runtime
    for value in (
        'runtime.artifact_count',
        'runtime.digest_matches',
        'runtime.tag_matches',
        'runtime.security_exposed',
    ):
        assert value in runtime
    assert "'warning' if runtime.tag_matches else 'info'" in runtime
    assert "'critical' if runtime.security_exposed else 'info'" in runtime
    assert '{% if runtime.setup.is_blocked %}' in runtime
    assert 'components/states/_blocked_state.html' in runtime
    assert 'Committed correlation counts are not live runtime health checks' in runtime
    assert 'Runtime Explorer' not in runtime
    assert 'Explore Runtime' not in runtime
