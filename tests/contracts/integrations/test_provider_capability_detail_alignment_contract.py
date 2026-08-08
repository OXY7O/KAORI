from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
KUBERNETES = ROOT / 'app/templates/integrations/kubernetes/partials/_capability_workspace.html'
PROMETHEUS = ROOT / 'app/templates/prometheus/partials/_capability_registry.html'
ALERTMANAGER = ROOT / 'app/templates/alertmanager/partials/_capability_registry.html'
DETAIL = ROOT / 'app/templates/integrations/components/_provider_capability_detail.html'
ACTIONS = ROOT / 'app/templates/integrations/components/_record_actions.html'


def test_provider_view_more_action_uses_shared_kaori_table_action():
    action = ACTIONS.read_text()
    assert '{% import "components/table.html" as table_ui %}' in action
    assert '{{ table_ui.action_classes() }}' in action
    assert 'data-lucide="chevron-right"' in action
    assert 'panel-top-open' not in action
    assert 'record_actions.view_more(' in PROMETHEUS.read_text()
    assert 'record_actions.view_more(' in ALERTMANAGER.read_text()


def test_provider_capability_modals_follow_kubernetes_information_architecture():
    shared = DETAIL.read_text()
    for token in (
        'Capability Contract',
        'Validation Evidence',
        'Operational Impact',
        'Recommended Action',
        'Technical Verification',
        'Evidence Boundary',
    ):
        assert token in shared
    assert 'data-kaori-provider-capability-contract' in shared
    assert 'data-kaori-provider-capability-evidence' in shared
    assert 'data-kaori-provider-capability-impact' in shared
    assert 'data-kaori-provider-capability-action' in shared
    assert 'data-kaori-provider-capability-technical-check' in shared
    assert 'data-kaori-provider-capability-evidence-boundary' in shared
    assert 'provider_capability_detail.content(' in PROMETHEUS.read_text()
    assert 'provider_capability_detail.content(' in ALERTMANAGER.read_text()
