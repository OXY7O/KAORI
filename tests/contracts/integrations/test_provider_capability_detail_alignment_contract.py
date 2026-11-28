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


def test_all_capability_registries_share_grouped_presentation():
    shared = DETAIL.read_text()
    provider_paths = (
        'source_control/github/partials/_capability_registry.html',
        'observability/metrics_source/partials/_capability_registry.html',
        'observability/alert_source/providers/alertmanager/partials/_capability_registry.html',
        'registry/providers/harbor/partials/_capability_registry.html',
        'storage/object_storage/providers/minio/partials/_capability_registry.html',
    )
    for path in provider_paths:
        registry = (ROOT / 'app/templates/integrations' / path).read_text()
        assert 'provider_capability_detail.content(' in registry
        assert 'presentation=' not in registry
    for path in (
        'orchestration/container_orchestrator/providers/kubernetes/partials/_capability_registry.html',
        'secrets_management/vault/partials/_capability_detail_content.html',
    ):
        source = (ROOT / 'app/templates/integrations' / path).read_text()
        for macro in ('contract', 'grouped_section', 'field', 'boundary', 'verification_panel'):
            assert f'capability_detail.{macro}(' in source
        assert 'data-kaori-capability-verification-unavailable' in source
    assert 'presentation=' not in shared
    assert 'sm:w-36 sm:shrink-0' in shared
    assert 'sm:flex-row sm:gap-4' in shared
    assert 'divide-y divide-outline-subtle' in shared
    assert 'sm:border-l' not in shared
    assert 'bg-status-' not in shared
    assert '<details' not in shared and '<summary' not in shared
    assert 'technical_check.render(' not in shared
    assert 'verification_panel(' in shared
    assert 'x-ref="script"' in shared
    for title in (
        'Capability Contract',
        'Validation Evidence',
        'Success Criteria',
        'Operational Decision',
        'Next Action',
        'Technical Verification',
        'Evidence Boundary',
    ):
        assert title in shared


def test_shared_capability_modal_renders_decision_fields_and_remediation():
    environment = Environment(loader=FileSystemLoader(str(ROOT / 'app/templates')), autoescape=True)
    render = environment.get_template('integrations/components/_provider_capability_detail.html').module.content
    for provider in ('GitHub', 'Metrics Source', 'Alertmanager', 'Harbor', 'MinIO'):
        for available, required, status_key, status_label in (
            (True, True, 'ready', 'Verified'),
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
            html = str(render(row, provider, 'Provider owner', 'Assessment', 'Provider boundary'))
            for marker in ('evidence', 'impact', 'action', 'operational-decision', 'evidence-boundary'):
                assert html.count(f'data-kaori-provider-capability-{marker}>') == 1
            for field in ('evidence', 'success_criteria', 'impact', 'next_action'):
                assert html.count(row[field]) == 1
            assert status_label in html
            assert ('Controlled remediation step' in html) == (not available)
            assert 'Provider boundary' in html
            assert html.index('Validation Evidence') < html.index('Operational Decision') < html.index('Evidence Boundary')


def test_shared_verification_panel_preserves_visible_evidence_and_copy_boundaries():
    environment = Environment(loader=FileSystemLoader(str(ROOT / 'app/templates')), autoescape=True)
    panel = environment.get_template('integrations/components/_provider_capability_detail.html').module.verification_panel
    html = str(panel(
        'Technical Verification',
        'Registered technical evidence',
        value='actions: read, metadata: read',
        metadata=['App Read Permission Contract'],
        status_label='Permission Verified',
        status_tone='ready',
        evidence='Committed observation',
        observed_series='7',
        observed_value='42',
        error_detail='Example provider error',
    ))
    for text in (
        'actions: read, metadata: read', 'App Read Permission Contract', 'Permission Verified',
        'Committed observation', 'Observed Series:', 'Observed Value:', 'Example provider error',
        'x-ref="script"', 'navigator.clipboard.writeText',
    ):
        assert text in html
    assert '<details' not in html and '<summary' not in html
    unavailable = str(panel('Verification Command', 'No command', unavailable='Run Full Validation'))
    assert 'Run Full Validation' in unavailable
    assert 'navigator.clipboard' not in unavailable and '<pre' not in unavailable
    script = str(panel('Verification Command', 'Operator guidance', value='example\ncommand', copy_label='Copy Script'))
    assert 'example\ncommand' in script
    assert 'Copy Script' in script


def test_shared_capability_content_keeps_distinct_registered_queries_visible():
    environment = Environment(loader=FileSystemLoader(str(ROOT / 'app/templates')), autoescape=True)
    render = environment.get_template('integrations/components/_provider_capability_detail.html').module.content
    row = {
        'available': True,
        'required': True,
        'status_key': 'ready',
        'status_label': 'Verified',
        'category': 'inventory',
        'evidence': 'Committed observation text',
        'success_criteria': 'Expected evidence',
        'impact': 'Operational impact',
        'next_action': 'Next operator action',
        'remediation': [],
        'technical_checks': [{
            'label': 'Technical check',
            'status_label': 'Verified',
            'tone': 'normal',
            'icon': 'circle-check',
            'evidence': 'Committed observation text',
            'query': 'observed_expression',
            'registered_query': 'registered_expression',
        }],
    }
    for provider in ('GitHub', 'Metrics Source', 'Alertmanager', 'Harbor', 'MinIO'):
        html = str(render(row, provider, 'Owner', 'Technical evidence', 'Provider boundary'))
        assert '<details' not in html
        assert html.count('x-ref="script"') == 2
        assert 'observed_expression' in html
        assert 'registered_expression' in html
        assert html.count('Committed observation text') == 1
        assert html.index('Technical Verification') < html.index('Evidence Boundary')
