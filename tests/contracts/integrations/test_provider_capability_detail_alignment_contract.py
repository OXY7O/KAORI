from pathlib import Path

from jinja2 import Environment, FileSystemLoader

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
    rows = shared.rsplit('{% if compact_github %}', 1)[1].split('{% else %}', 1)[0]
    assert rows.count('rounded-xl border border-outline-default bg-surface-card') == 2
    assert rows.count('sm:w-36 sm:shrink-0') == 4
    assert rows.count('sm:flex-row sm:gap-4') == 4
    assert rows.count('data-kaori-provider-capability-evidence') == 1
    assert rows.count('data-kaori-provider-capability-impact') == 1
    assert rows.count('data-kaori-provider-capability-action') == 1
    assert rows.index('Validation Evidence') < rows.index('Observation') < rows.index('Success Criteria')
    assert rows.index('Operational Decision') < rows.index('Impact') < rows.index('Next Action')
    for field in ('row.evidence', 'row.success_criteria', 'row.impact', 'row.next_action'):
        assert rows.count(field) == 1
    assert 'bg-status-' not in rows and 'border-status-' not in rows
    assert 'sm:border-l' not in rows and 'grid-cols-[' not in rows
    assert 'data-kaori-github-capability-success-criteria' in rows
    assert '{% if not row.available and row.remediation %}' in rows
    assert '{% for step in row.remediation %}' in rows


def test_github_capability_modal_renders_decision_fields_and_remediation():
    environment = Environment(loader=FileSystemLoader(str(ROOT / 'app/templates')), autoescape=True)
    render = environment.get_template('integrations/components/_provider_capability_detail.html').module.content
    for available, required, status_key, status_label in (
        (True, True, 'ready', 'Permission Verified'),
        (False, True, 'blocked', 'Required Gap'),
        (False, False, 'optional_gap', 'Optional Gap'),
        (False, True, 'unverified', 'Not Validated'),
    ):
        row = {
            'available': available,
            'required': required,
            'status_key': status_key,
            'status_label': status_label,
            'category': 'inventory',
            'evidence': 'Committed observation text',
            'success_criteria': 'Expected permission text',
            'impact': 'Operational effect text',
            'next_action': 'Operator decision text',
            'remediation': ['Controlled remediation step'],
            'technical_checks': [],
        }
        html = str(render(row, 'GitHub', 'GitHub App Permissions', 'Assessment', 'Provider boundary', 'github'))
        assert html.count('data-kaori-provider-capability-evidence>') == 1
        assert html.count('data-kaori-provider-capability-impact>') == 1
        assert html.count('data-kaori-provider-capability-action>') == 1
        for field in ('evidence', 'success_criteria', 'impact', 'next_action'):
            assert html.count(row[field]) == 1
        assert status_label in html
        assert ('Controlled remediation step' in html) == (not available)
        assert 'Recommended Action</h3>' not in html
        assert 'Provider boundary' in html
        standard = str(render(row, 'Provider', 'Owner', 'Assessment', 'Provider boundary'))
        assert 'data-kaori-github-capability-operational-decision' not in standard
        assert 'Recommended Action</h3>' in standard
