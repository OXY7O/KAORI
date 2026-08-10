from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_secret_reveal_namespace_pagination_includes_rows_label() -> None:
    table = read('app/templates/platform_operations/kubernetes/secret_reveal/_namespace_policy_table_content.html')

    assert "pagination_ui.resource_name('Namespaces', namespace_pagination.total_items)" in table
    assert '<span class="font-semibold text-content-secondary">Rows</span>' in table
    assert 'aria-label="Rows Per Page"' in table


def test_htmx_secret_reveal_mutations_deliver_feedback_immediately() -> None:
    routes = read('app/platform_operations/kubernetes/secret_reveal/routes.py')

    assert 'queue_feedback=False' in routes
    assert 'queue_operational_feedback(operation_feedback)' in routes
    assert "'components/operational_toast.html'" in routes
    assert 'toast_oob=True' in routes
    assert 'workspace_html + feedback_html' in routes

    response_block = routes.split('def _settings_response(', 1)[1].split('def _cluster_or_error(', 1)[0]
    assert "request.headers.get('HX-Request') != 'true'" in response_block
    assert 'queue_operational_feedback(operation_feedback)' in response_block
    assert 'toast_oob=True' in response_block


def test_protected_reveal_discovers_only_configured_namespaces_without_namespace_list() -> None:
    live_service = read('app/kubernetes_operations/secrets/live_service.py')
    policy = read('app/kubernetes_operations/secrets/reveal_policy.py')
    protected = read('app/kubernetes_operations/secrets/reveal_service.py')

    assert 'def list_verified_namespaces(' in live_service
    verify_block = live_service.split('def list_verified_namespaces(', 1)[1].split('def list_live_secrets(', 1)[0]
    assert 'api.read_namespace(name=namespace)' in verify_block
    assert '.list_namespace()' not in verify_block
    assert 'if status == 404:' in verify_block

    enabled_block = policy.split('def get_enabled_namespace_names(', 1)[1].split(
        'def refresh_namespace_source_snapshot(', 1
    )[0]
    assert 'list_verified_namespaces(cluster_id, configured)' in enabled_block
    assert 'list_live_namespaces(' not in enabled_block

    workspace_block = protected.split('def get_reveal_workspace(', 1)[1].split('def _allowed_keys(', 1)[0]
    assert 'get_configured_enabled_namespace_names(normalized_cluster_id)' in workspace_block
    assert 'get_enabled_namespace_names(normalized_cluster_id)' in workspace_block
    assert 'list_live_namespaces(' not in workspace_block
    assert "'configured_namespace_count': len(configured_names)" in workspace_block


def test_protected_reveal_explains_empty_namespace_and_cluster_states() -> None:
    target = read('app/templates/kubernetes_operations/secrets/_reveal_target_workspace.html')
    page = read('app/templates/kubernetes_operations/secrets/reveal.html')

    assert 'Policy-enabled namespaces are configured, but none is currently available in Kubernetes.' in target
    assert 'Enable a namespace policy under Platform Operations → Secret Reveal first.' in target
    assert 'Protected Reveal globally disabled' in page
    assert 'KUBERNETES_SECRET_REVEAL_ENABLED=true' in page
    assert 'No eligible cluster. Verify cluster readiness and enable at least one Namespace Policy.' in page
