from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
KUBERNETES = (
    ROOT
    / 'app/templates/integrations/orchestration/container_orchestrator/providers/kubernetes/partials/_capability_workspace.html'
)
PROMETHEUS = ROOT / 'app/templates/integrations/observability/metrics_source/partials/_capability_registry.html'
ALERTMANAGER = (
    ROOT
    / 'app/templates/integrations/observability/alert_source/providers/alertmanager/partials/_capability_registry.html'
)
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


def test_github_capability_modal_uses_compact_shared_presentation():
    shared = DETAIL.read_text()
    github = ROOT / 'app/templates/integrations/source_control/github/partials/_capability_registry.html'
    assert 'presentation="github"' in github.read_text()
    assert "presentation == 'github'" in shared
    assert 'Validation evidence, ownership, impact, and remediation.' in shared
    assert "presentation == 'metrics_source'" in shared
    panel = shared.split('data-kaori-github-capability-evidence-impact>', 1)[0].rsplit(
        '{% if compact_github %}', 1
    )[1]
    rows = shared.split('data-kaori-github-capability-evidence-impact>', 1)[1].split('{% else %}', 1)[0]
    assert 'divide-y divide-outline-subtle rounded-xl border border-outline-default bg-surface-card' in panel
    assert rows.count('sm:grid-cols-[12rem_minmax(0,1fr)]') == 2
    assert rows.count('data-kaori-provider-capability-evidence') == 1
    assert rows.count('data-kaori-provider-capability-impact') == 1
    assert rows.index('Validation Evidence') < rows.index('Success Criteria:') < rows.index('Operational Impact')
    for field in ('row.evidence', 'row.success_criteria', 'row.impact'):
        assert rows.count(field) == 1
    assert 'bg-status-' not in rows and 'border-status-' not in rows
    assert 'rounded-lg' not in rows and 'lg:grid-cols-2' not in rows
    assert 'data-kaori-github-capability-success-criteria' in rows
