from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PRESENTATION = ROOT / 'app/automation_control/presentation.py'
ROUTES = ROOT / 'app/automation_control/routes.py'
TEMPLATE = ROOT / 'app/templates/intelligence/automation_control.html'
NAVIGATION = ROOT / 'app/templates/components/navigation/intelligence_menu.html'
PARTIALS = ROOT / 'app/templates/intelligence/partials/automation_control'


def _template_source() -> str:
    return TEMPLATE.read_text() + ''.join(path.read_text() for path in sorted(PARTIALS.glob('*.html')))


def test_automation_control_maps_every_completed_domain_once() -> None:
    module = ast.parse(PRESENTATION.read_text())
    assignment = next(
        node for node in module.body
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id == 'DOMAIN_DEFINITIONS'
    )
    assert isinstance(assignment.value, ast.Tuple)
    numbers = []
    for item in assignment.value.elts:
        assert isinstance(item, ast.Call)
        first_arg = item.args[0]
        assert isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, int)
        numbers.append(first_arg.value)

    assert numbers == list(range(1, 21))


def test_ui_exposes_governed_workspaces_without_direct_resolver_dispatch() -> None:
    route_text = ROUTES.read_text()
    template_text = _template_source()
    presentation_text = PRESENTATION.read_text()

    assert "@automation_control_bp.route('/automation-control')" in route_text
    assert "@permission_required('intelligence.view')" in route_text
    for workspace in (
        'Foundation Map',
        'Runbooks & Bindings',
        'Decision Review',
        'Resolver Operations',
        'Production Readiness',
    ):
        assert workspace in presentation_text or workspace in template_text

    assert 'dispatch_resolver_execution' not in route_text
    assert 'execute_persisted_decision' not in route_text
    assert 'csrf_token()' in template_text


def test_every_automation_mutation_is_post_only_and_permission_gated() -> None:
    route_text = ROUTES.read_text()
    assert route_text.count("@automation_control_bp.post('/automation-control/") >= 10
    assert "@permission_required('knowledge.runbooks.manage')" in route_text
    assert "@permission_required('knowledge.runbooks.publish')" in route_text
    assert "@permission_required('intelligence.decisions.create')" in route_text
    assert "@permission_required('intelligence.decisions.approve')" in route_text
    assert "@permission_required('intelligence.decisions.execute')" in route_text


def test_sidebar_links_to_the_control_center() -> None:
    text = NAVIGATION.read_text()
    assert "url_for('automation_control.index')" in text
    assert 'Automation Control' in text


def test_automation_control_template_is_split_by_operator_workspace() -> None:
    wrapper = TEMPLATE.read_text()
    partials = sorted(PARTIALS.glob('*.html'))

    assert len(wrapper.splitlines()) < 120
    assert {path.name for path in partials} == {
        '_overview.html',
        '_runbooks.html',
        '_decisions.html',
        '_operations.html',
        '_readiness.html',
    }
    assert all(path.stat().st_size < 25_000 for path in partials)
