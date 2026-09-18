import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_related_workspace_card_uses_global_contextual_violet_surface_in_dark_mode() -> None:
    source = read('app/templates/components/related_page_card.html')

    assert 'kaori-brand-domain-panel' in source
    assert 'text-brand-foreground' in source
    assert 'text-brand-foreground-muted' in source
    assert 'bg-brand-surface' in source
    assert 'bg-brand-surface-strong' in source
    assert 'dark:bg-surface-card' not in source
    assert 'dark:text-content-primary' not in source
    assert 'bg-brand-surface-strong' in source
    assert 'hover:bg-kaori-primary-hover' in source
    assert 'hover:text-white' in source


def test_shared_connection_guidance_uses_accent_violet_not_bright_supporting_text() -> None:
    for relative in (
        'app/templates/components/info_flow.html',
        'app/templates/components/information_guide_card.html',
        'app/templates/components/view_more_content.html',
        'app/templates/components/connection_validation_header.html',
        'app/templates/components/context_guidance_card.html',
    ):
        source = read(relative)
        assert 'dark:text-kaori-accent' in source, relative


def test_kubernetes_connection_forms_follow_integration_dark_mode_and_shared_actions() -> None:
    add = read('app/templates/kubernetes/cluster/add.html')
    edit = read('app/templates/kubernetes/cluster/edit.html')
    form = read('app/templates/kubernetes/cluster/partials/_form.html')

    assert 'kaori-integration-semantic space-y-6' in add
    assert 'kaori-integration-semantic space-y-6' in edit
    assert '{% import "components/action_button.html" as action_button %}' in form
    assert "action_button.classes('secondary')" in form
    assert "action_button.classes('primary')" in form
    assert 'dark:border-brand-outline dark:bg-surface-muted' in form
    assert 'dark:text-kaori-accent' in form


def test_metrics_source_and_alertmanager_registration_forms_use_shared_action_contract() -> None:
    metrics_source = read('app/templates/integrations/observability/metrics_source/instance_form.html')
    alertmanager = read(
        'app/templates/integrations/observability/alert_source/providers/alertmanager/instance_form.html'
    )

    for source in (metrics_source, alertmanager):
        assert '{% import "components/action_button.html" as action_button %}' in source
        assert "action_button.classes('secondary')" in source
        assert "action_button.classes('primary')" in source

    shared_context = read('app/templates/integrations/components/_provider_registration_context.html')
    assert 'provider_registration_context.render(' in metrics_source
    assert 'provider_registration_context.render(' in alertmanager
    assert 'Related Operational Workspace' in shared_context


def test_kubernetes_connection_form_reuses_shared_shell_and_semantic_ownership() -> None:
    form_path = 'app/templates/kubernetes/cluster/partials/_form.html'
    form = read(form_path)
    baseline = json.loads(read('docs/architecture/ui-style-debt-baseline.json'))

    assert 'components/kubernetes_operation_ui.html' in form
    assert 'kubernetes_operation_ui.surface_shell_classes()' in form
    assert 'components/operational_callout.html' in form
    assert form.count("operational_callout.semantic_border_classes('critical')") == 2

    assert 'overflow-hidden rounded-xl border border-outline-default bg-surface-card shadow-sm' not in form
    assert 'border-status-critical-border' not in form
    assert 'border-status-warning-border' not in form
    assert (
        'kube_allow_weak_tls(class="h-4 w-4 rounded border-outline-strong accent-status-warning focus:ring-status-warning")'
        in form
    )

    assert 'x-on:kubernetes-connection-tested.window="applyConnectionTest($event)"' in form
    assert 'hx-target="#kubernetes-connection-test-result"' in form
    assert 'provider_registration_actions.render(' in form
    assert form_path not in baseline['files']
