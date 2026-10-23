"""Alert Incidents Policy UAT design regression (#2923).

This is source/Jinja validation, not rendered-browser Visual QA or admission.
"""
from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[3]
WORKSPACE_PATH = 'app/templates/platform_operations/data_lifecycle/partials/_domain_workspace.html'


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding='utf-8')


def test_policy_panel_preserves_shared_block_but_softens_outer_outline() -> None:
    source = read(WORKSPACE_PATH)
    Environment().parse(source)
    assert 'class="{{ table_ui.block_classes() }} !border-outline-subtle !shadow-none"' in source
    assert 'components/table.html' in source
    assert 'components/table_label.html' in source
    assert 'bg-surface-card' in source
    assert 'border border-outline-default bg-surface-card' in source
    assert 'border border-outline-subtle bg-surface-subtle p-3.5' in source


def test_alert_incidents_coverage_is_two_by_two_without_changing_other_domains() -> None:
    source = read(WORKSPACE_PATH)
    coverage = source.split('<h3 class="text-base font-semibold leading-6 text-content-primary">', 1)[1]
    coverage = coverage.split('Lifecycle Coverage</h3>', 1)[1].split('{% endfor %}', 1)[0]
    assert 'sm:grid-cols-2' in coverage
    assert "lifecycle.coverage|length == 3" in coverage
    assert "selected.name != 'alert_incident'" not in coverage
    assert 'xl:grid-cols-3' in coverage
    assert '{% for item in lifecycle.coverage %}' in coverage
    assert '{{ item.icon }}' in coverage
    assert '{{ item.label }}' in coverage
    assert '{{ item.description }}' in coverage

    presentation = read('app/platform_operations/data_lifecycle/retention/presentation.py')
    incident = presentation.split("'alert_incident': (", 1)[1].split("\n        ),", 1)[0]
    for label in (
        'Closed Alert Cases',
        'Incident Timeline',
        'Notification Delivery',
        'Postmortem Evidence',
    ):
        assert f"'label': '{label}'" in incident
    assert incident.count("'label':") == 4


def test_recovery_copy_shortened_without_changing_retry_contract() -> None:
    source = read(WORKSPACE_PATH)
    assert 'Cleanup blocked; transient failures retry once, then need manual retry.' in source
    assert 'Cleanup stays blocked; transient failures retry once, then require manual retry.' not in source
    assert 'Failure Recovery' in source


def test_worker_ready_copy_does_not_claim_ready_when_unavailable() -> None:
    source = read(WORKSPACE_PATH)
    assert 'Queue {{ lifecycle.queue_name }} · {{ lifecycle.worker.label }}' in source
    assert '{% if lifecycle.worker.queue_ready %} and ready for lifecycle jobs{% endif %}.' in source
    assert 'Execution Worker' in source

    presentation = read('app/platform_operations/data_lifecycle/retention/presentation.py')
    assert "'queue_name': str(current_app.config.get('RETENTION_CELERY_QUEUE'" in presentation
    assert "'queue_ready': state['ready']" in presentation
