from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_empty_and_blocked_states_have_canonical_shared_owners() -> None:
    empty = read('app/templates/components/states/_empty_state.html')
    blocked = read('app/templates/components/states/_blocked_state.html')
    guide = read('docs/design/components/empty-state.md')
    engineering = read('docs/standards/KAORI_ENGINEERING_STANDARD_V1.md')

    assert 'data-kaori-empty-state' in empty
    assert 'data-kaori-blocked-state' in blocked
    assert "state_variant == 'table'" in blocked
    assert "blocked_state_variant='table'" in guide
    assert 'page-local icon/title/description empty-state markup is not allowed' in guide
    assert 'HTMX out-of-band fragments are response-only helpers' in guide
    assert 'canonical table/registry/workspace zero states use `components/states/_empty_state.html`' in engineering


def test_jobs_execution_zero_states_use_canonical_empty_state_without_oob_leak() -> None:
    routes = read('app/platform_operations/jobs/routes.py')
    active = read('app/templates/platform_operations/jobs/executions/partials/_active_jobs.html')
    registry = read('app/templates/platform_operations/jobs/executions/partials/_registry.html')
    queues = read('app/templates/platform_operations/jobs/executions/partials/_queue_activity.html')
    configuration = read('app/templates/platform_operations/jobs/configuration/_job_workspace.html')
    execution_activity = read('app/templates/platform_operations/jobs/configuration/_execution_activity.html')

    assert "fragment_context['include_status_oob'] = fragment == 'active'" in routes
    assert '{% if include_status_oob|default(false) %}' in active
    assert (
        "{% if embedded|default(false) %}\n    {% include 'platform_operations/jobs/executions/partials/_status_oob.html' %}"
        not in active
    )
    assert 'hx-on::before-request="if (document.hidden) event.preventDefault()"' in active

    for template in (active, registry, queues, configuration, execution_activity):
        assert 'components/states/_empty_state.html' in template
    assert "empty_state_label = 'Queue Clear'" in active
    assert "empty_state_label = 'No Results'" in registry
    assert 'px-6 py-12 text-center' not in active
    assert 'px-6 py-12 text-center' not in registry
    assert 'px-6 py-12 text-center' not in queues
    assert "empty_state_label = 'Selection Required'" in configuration
    assert "empty_state_title = 'No Execution Recorded'" in execution_activity


def test_kubernetes_administration_distinguishes_empty_from_blocked_table_state() -> None:
    cluster = read('app/templates/platform_operations/kubernetes/secret_reveal/_cluster_workspace.html')
    namespace_table = read(
        'app/templates/platform_operations/kubernetes/secret_reveal/_namespace_policy_table_content.html'
    )

    assert "empty_state_label = 'Setup Required'" in cluster
    assert "empty_state_action_label = 'Add Cluster'" in cluster
    assert 'components/states/_empty_state.html' in cluster

    assert "empty_state_label = 'No Results'" in namespace_table
    assert "blocked_state_variant = 'table'" in namespace_table
    assert "blocked_state_label = 'Source Unavailable'" in namespace_table
    assert 'components/states/_blocked_state.html' in namespace_table
