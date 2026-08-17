from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[3]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_secret_reveal_operational_states_use_shared_semantic_labels() -> None:
    posture = _read('app/templates/platform_operations/kubernetes/_secret_reveal_workspace.html')
    cluster = _read('app/templates/platform_operations/kubernetes/secret_reveal/_cluster_workspace.html')
    table = _read('app/templates/platform_operations/kubernetes/secret_reveal/_namespace_policy_table_content.html')

    assert "status_indicator_label('Reveal Enabled'" in posture
    assert "status_indicator_label('Ready'" in cluster
    assert cluster.count("status_indicator_label('Verified'") == 2
    assert 'policy_icon' not in table
    assert 'table_label.status_label' in table


def test_namespace_policy_uses_title_case_and_inventory_pagination_contract() -> None:
    section = _read('app/templates/platform_operations/kubernetes/secret_reveal/_namespace_policy_section.html')
    table = _read('app/templates/platform_operations/kubernetes/secret_reveal/_namespace_policy_table_content.html')

    assert 'Search Namespace' in section
    assert 'Reveal Policy' in section
    assert "namespace_summary.total ~ ' Total'" in section
    assert "namespace_summary.enabled ~ ' Enabled'" in section
    assert 'pagination_ui.footer_classes()' in table
    assert "pagination_ui.resource_name('Namespaces'" in table
    assert 'No Namespace Matches the Current Filters' in table
    assert "'namespace' if namespace_pagination.total_items" not in table


def test_jobs_reuse_shared_metadata_status_and_pagination_components() -> None:
    activity = _read('app/templates/platform_operations/jobs/configuration/_execution_activity.html')
    registry = _read('app/templates/platform_operations/jobs/executions/partials/_registry.html')
    empty_state = _read('app/templates/platform_operations/jobs/configuration/_job_workspace.html')

    assert 'table_label.metadata_label(definition.queue_name)' in activity
    assert "status_indicator_label('Ready for Execution', 'normal')" in activity
    assert 'table_registry.footer' in registry
    assert "resource_label='Executions'" in registry
    assert 'Select a Registered Job' in empty_state


def test_changed_platform_operations_templates_parse() -> None:
    environment = Environment()
    for relative in (
        'app/templates/platform_operations/kubernetes/_secret_reveal_workspace.html',
        'app/templates/platform_operations/kubernetes/secret_reveal/_cluster_workspace.html',
        'app/templates/platform_operations/kubernetes/secret_reveal/_namespace_policy_section.html',
        'app/templates/platform_operations/kubernetes/secret_reveal/_namespace_policy_table_content.html',
        'app/templates/platform_operations/jobs/configuration/_execution_activity.html',
        'app/templates/platform_operations/jobs/configuration/_job_workspace.html',
        'app/templates/platform_operations/jobs/executions/partials/_registry.html',
    ):
        environment.parse(_read(relative))
