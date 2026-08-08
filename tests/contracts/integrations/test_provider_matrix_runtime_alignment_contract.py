from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text()


def test_provider_validation_workspaces_share_capability_readiness_component():
    shared = read('app/templates/integrations/components/_capability_readiness.html')
    prometheus = read('app/templates/prometheus/partials/_detail_validation_content.html')
    alertmanager = read('app/templates/alertmanager/partials/_detail_validation_content.html')

    assert 'data-kaori-provider-capability-readiness' in shared
    assert 'Validated capability coverage' not in shared  # label is provider supplied
    assert "capability_readiness.render(" in prometheus
    assert "capability_readiness.render(" in alertmanager
    assert 'Validation Decision' not in prometheus
    assert 'Validation Decision' not in alertmanager


def test_provider_runtime_workspaces_share_kubernetes_style_decision_component():
    shared = read('app/templates/integrations/components/_runtime_decision.html')
    prometheus = read('app/templates/prometheus/partials/_runtime_panel.html')
    alertmanager = read('app/templates/alertmanager/partials/_runtime_panel.html')

    assert 'data-kaori-provider-runtime-decision' in shared
    assert 'Operational Response' in shared
    assert 'Evidence Handoff' in shared
    for source in (prometheus, alertmanager):
        assert 'runtime_decision.render(' in source
        assert 'data-kaori-provider-runtime-kubernetes-pattern' in source
        assert 'lg:sticky' not in source
        assert 'xl:sticky' not in source


def test_provider_runtime_main_page_uses_concise_diagnostics_and_modal_owns_full_detail():
    presentation = read('app/integrations/runtime/presentation.py')
    modal = read('app/templates/integrations/components/_runtime_observation_modal.html')
    prometheus = read('app/templates/prometheus/partials/_runtime_panel.html')
    alertmanager = read('app/templates/alertmanager/partials/_runtime_panel.html')

    assert "'summary': _diagnostic_summary(" in presentation
    assert "'message_redundant': _message_repeats_diagnostic" in presentation
    assert 'row.message and not row.message_redundant' in modal
    assert 'Diagnostic Review' in modal
    for source in (prometheus, alertmanager):
        assert 'step.summary' in source
        assert 'step.detail' not in source
        assert 'step.recommendation' not in source
