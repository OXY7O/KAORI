from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text()


def test_recommendations_and_rule_catalog_are_separate_workspaces():
    routes = read('app/intelligence/routes.py')
    assert 'intelligence/recommendations.html' in routes
    assert 'intelligence/rule_catalog.html' in routes
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
    assert 'AUTOMATION_CONTROL_MUTATIONS_ENABLED' in routes
    assert 'AUTOMATION_CONTROL_MUTATIONS_ENABLED' in presentation
    assert 'detail=str(exc)' not in routes
    assert 'Automation Control Reserved Plan' in routes


def test_automation_workspace_uses_integrated_tabs_and_grouped_foundations():
    template = read('app/templates/intelligence/automation_control.html')
    overview = read('app/templates/intelligence/partials/automation_control/_overview.html')
    assert 'link_tabs(' in template
    assert "payload['domain_groups']|default([], true)" in overview
    assert 'overflow-x-auto' not in overview


def test_intelligence_templates_do_not_use_inline_script_or_onchange():
    content = '\n'.join(path.read_text() for path in Path('app/templates/intelligence').rglob('*.html'))
    assert '<script' not in content
    assert 'onchange=' not in content


def test_rule_catalog_uses_adjacent_inline_rule_definition_instead_of_modal():
    records = read('app/templates/intelligence/partials/_catalog_records.html')
    details = read('app/templates/intelligence/partials/_catalog_detail_content.html')
    routes = read('app/intelligence/routes.py')

    assert 'data-detail-toggle' in records
    assert 'data-detail-row' in records
    assert 'data-detail-group="rule-catalog"' in records
    assert 'data-detail-context="Rule Definition"' in records
    assert '<details' not in records
    assert 'resource_detail_modal' not in records
    assert 'def catalog_rule_details(' in routes
    assert '_catalog_detail_content.html' in routes
    assert 'Evaluation Logic' in details
    assert 'Operator Response' in details
    assert 'Coverage Contract' in details
    assert Path('app/templates/intelligence/partials/_catalog_workspace.html').exists()
    assert Path('app/templates/intelligence/partials/_catalog_results.html').exists()
    workspace = read('app/templates/intelligence/partials/_catalog_workspace.html')
    results = read('app/templates/intelligence/partials/_catalog_results.html')
    assert 'filter_results_target = "#catalog-results-content"' in workspace
    assert 'filter_workspace_target = "#catalog-workspace-content"' in workspace
    assert "target='#catalog-results-content'" in results
    assert "target == 'catalog-results-content'" in routes


def test_shared_productive_typography_uses_named_size_tokens_for_primary_surfaces():
    paths = [
        'app/templates/components/page_hero.html',
        'app/templates/components/side_drawer.html',
        'app/templates/components/resource_detail_modal.html',
        'app/templates/components/table_label.html',
        'app/templates/inventory/kubernetes/components/_summary.html',
        'app/templates/intelligence/components/_workspace.html',
        'app/templates/intelligence/partials/_recommendation_detail_content.html',
        'app/templates/intelligence/partials/_catalog_detail_content.html',
    ]
    content = '\n'.join(read(path) for path in paths)
    assert 'text-[10px]' not in content
    assert 'text-[11px]' not in content
    assert 'text-[12px]' not in content
    assert 'tracking-[0.' not in content
