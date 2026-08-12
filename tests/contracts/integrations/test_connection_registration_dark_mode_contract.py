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
    add = read('app/templates/cluster/add.html')
    edit = read('app/templates/cluster/edit.html')
    form = read('app/templates/cluster/partials/_form.html')

    assert 'kaori-integration-semantic space-y-6' in add
    assert 'kaori-integration-semantic space-y-6' in edit
    assert '{% import "components/action_button.html" as action_button %}' in form
    assert "action_button.classes('secondary')" in form
    assert "action_button.classes('primary')" in form
    assert 'dark:border-brand-outline dark:bg-surface-muted' in form
    assert 'dark:text-kaori-accent' in form


def test_prometheus_and_alertmanager_registration_forms_use_shared_action_contract() -> None:
    prometheus = read('app/templates/prometheus/instance_form.html')
    alertmanager = read('app/templates/alertmanager/instance_form.html')

    for source in (prometheus, alertmanager):
        assert '{% import "components/action_button.html" as action_button %}' in source
        assert "action_button.classes('secondary')" in source
        assert "action_button.classes('primary')" in source

    shared_context = read('app/templates/integrations/components/_provider_registration_context.html')
    assert 'provider_registration_context.render(' in prometheus
    assert 'provider_registration_context.render(' in alertmanager
    assert 'Related Operational Workspace' in shared_context
