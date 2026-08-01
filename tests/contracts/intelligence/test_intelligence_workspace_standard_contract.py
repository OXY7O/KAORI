from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text()


def test_recommendations_and_rule_catalog_are_separate_workspaces():
    routes = read('app/intelligence/routes.py')
    assert "intelligence/recommendations.html" in routes
    assert "intelligence/rule_catalog.html" in routes
    assert Path('app/templates/intelligence/rule_catalog.html').exists()


def test_reserved_plan_language_replaces_placeholder_language():
    paths = list(Path('app/templates/intelligence').rglob('*.html')) + [Path('app/intelligence/service.py')]
    content = '\n'.join(path.read_text().lower() for path in paths)
    assert 'reserved plan' in content
    assert 'dummy_flow' not in content
    assert 'mvp' not in content
    assert 'coming soon' not in content
    assert 'placeholder page' not in content
    assert 'placeholder workspace' not in content


def test_automation_control_mutations_are_fail_closed_by_default():
    routes = read('app/automation_control/routes.py')
    presentation = read('app/automation_control/presentation.py')
    assert "AUTOMATION_CONTROL_MUTATIONS_ENABLED" in routes
    assert "AUTOMATION_CONTROL_MUTATIONS_ENABLED" in presentation
    assert "detail=str(exc)" not in routes
    assert "Automation Control Reserved Plan" in routes


def test_automation_workspace_uses_integrated_tabs_and_grouped_foundations():
    template = read('app/templates/intelligence/automation_control.html')
    overview = read('app/templates/intelligence/partials/automation_control/_overview.html')
    assert 'link_tabs(' in template
    assert 'payload.domain_groups' in overview
    assert 'overflow-x-auto' not in overview


def test_intelligence_templates_do_not_use_inline_script_or_onchange():
    content = '\n'.join(path.read_text() for path in Path('app/templates/intelligence').rglob('*.html'))
    assert '<script' not in content
    assert 'onchange=' not in content
