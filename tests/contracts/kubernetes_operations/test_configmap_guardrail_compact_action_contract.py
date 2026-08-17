from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_configmap_create_uses_the_same_form_grid_as_connection_registration_pages() -> None:
    template = (ROOT / 'app/templates/kubernetes_operations/configmaps/create.html').read_text(encoding='utf-8')
    assert 'data-kubernetes-operation-layout="form-context-v1"' in template
    assert 'data-kubernetes-operation-experience="configmap-create-v1"' in template
    assert 'components/form_with_context_rail.html' in template
    assert 'form_context.layout_classes()' in template
    assert 'form_context.main_classes()' in template
    assert 'form_context.rail_classes()' in template
    assert 'data-kubernetes-operation-form="configmap-create"' in template
    assert 'ConfigMap Definition' in template
    assert 'ConfigMap Creation Flow' in template
    assert 'Creation Safety Contract' in template
    assert 'info_flow.render(' in template
    assert 'information_guide_card.render(' in template
    assert 'configmap_ui.action_bar(' in template
    assert 'embedded=true' in template
    assert 'components/context_rail.html' not in template
    assert 'workspace_section(' not in template
    assert 'workflow_control(' not in template


def test_configmap_create_reuses_the_proven_integration_form_geometry() -> None:
    create = (ROOT / 'app/templates/kubernetes_operations/configmaps/create.html').read_text(encoding='utf-8')
    references = (
        ROOT / 'app/templates/cluster/add.html',
        ROOT / 'app/templates/integrations/observability/metrics_source/instance_form.html',
        ROOT / 'app/templates/integrations/observability/alert_source/providers/alertmanager/instance_form.html',
    )
    component = (ROOT / 'app/templates/components/form_with_context_rail.html').read_text(encoding='utf-8')
    layout_tokens = (
        'grid gap-6 xl:grid-cols-12 xl:items-start',
        'xl:col-span-8',
        'space-y-4 xl:col-span-4 xl:sticky xl:top-5',
    )
    assert 'form_context.layout_classes()' in create
    assert 'form_context.main_classes()' in create
    assert 'form_context.rail_classes()' in create
    for token in layout_tokens:
        assert token in component
        assert any(token in path.read_text(encoding='utf-8') for path in references)


def test_shared_operation_ui_keeps_reusable_section_and_action_geometry() -> None:
    component = (ROOT / 'app/templates/components/kubernetes_operation_ui.html').read_text(encoding='utf-8')
    assert 'macro workspace_section' in component
    assert 'macro workflow_control' in component
    assert 'components/operational_point_flow.html' in component
    assert 'form_action_bar.render' in component
