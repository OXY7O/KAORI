from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

FORM_CONTEXT_CONSUMERS = (
    'app/templates/kubernetes_operations/configmaps/create.html',
    'app/templates/kubernetes_operations/configmaps/update.html',
    'app/templates/kubernetes_operations/configmaps/delete.html',
    'app/templates/kubernetes_operations/secrets/create.html',
    'app/templates/kubernetes_operations/secrets/replace.html',
    'app/templates/kubernetes_operations/secrets/delete.html',
    'app/templates/kubernetes_operations/secrets/reveal.html',
)


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_shared_form_with_context_component_owns_canonical_geometry() -> None:
    source = read('app/templates/components/form_with_context_rail.html')
    assert 'grid gap-6 xl:grid-cols-12 xl:items-start' in source
    assert 'min-w-0 xl:col-span-8' in source
    assert 'min-w-0 space-y-4 xl:col-span-4 xl:sticky xl:top-5' in source


def test_reviewed_operations_tasks_consume_shared_form_with_context_geometry() -> None:
    for relative in FORM_CONTEXT_CONSUMERS:
        source = read(relative)
        assert 'components/form_with_context_rail.html' in source
        assert 'form_context.layout_classes()' in source
        assert 'form_context.main_classes()' in source
        assert 'form_context.rail_classes()' in source
        assert 'components/info_flow.html' in source
        assert 'components/information_guide_card.html' in source
        assert 'class="grid gap-6 xl:grid-cols-12 xl:items-start"' not in source


def test_integration_registration_pages_remain_visual_references_until_refactor() -> None:
    references = (
        'app/templates/cluster/add.html',
        'app/templates/integrations/observability/metrics_source/instance_form.html',
        'app/templates/integrations/observability/alert_source/providers/alertmanager/instance_form.html',
    )
    for relative in references:
        source = read(relative)
        assert 'xl:grid-cols-12 xl:items-start' in source
        assert 'xl:col-span-8' in source
        assert 'space-y-4 xl:col-span-4 xl:sticky xl:top-5' in source


def test_form_with_context_standard_is_indexed_and_distinct_from_fixed_width_rail() -> None:
    standard = read('docs/design/components/FORM_WITH_CONTEXT_RAIL.md')
    right_rail = read('docs/design/components/RIGHT_CONTEXT_RAIL.md')
    design_readme = read('docs/design/README.md')
    assert '# KAORI Form + Right Context Standard' in standard
    assert 'Register Kubernetes Connection' in standard
    assert 'Register Metrics Source' in standard
    assert 'Register Alertmanager Connection' in standard
    assert 'Create Kubernetes ConfigMap' in standard
    assert 'Protected Kubernetes Secret Reveal' in standard
    assert 'FORM_WITH_CONTEXT_RAIL.md' in right_rail
    assert 'components/FORM_WITH_CONTEXT_RAIL.md' in design_readme
