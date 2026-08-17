from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_platform_configuration_and_protected_reveal_share_policy_authority() -> None:
    policy = read('app/kubernetes/operations/secrets/reveal_policy.py')
    protected = read('app/kubernetes/operations/secrets/reveal_service.py')

    assert 'def cluster_reveal_readiness(' in policy
    assert 'def get_namespace_policy(' in policy
    assert 'def get_configured_enabled_namespace_names(' in policy
    assert 'def update_cluster_reveal_readiness(' in policy
    assert 'def set_namespace_reveal_policy(' in policy

    assert 'cluster_reveal_readiness,' in protected
    assert 'get_configured_enabled_namespace_names,' in protected
    assert 'get_enabled_namespace_names,' in protected
    assert 'get_namespace_policy,' in protected
    assert 'return cluster_reveal_readiness(cluster)' in protected
    assert 'configured_names = get_configured_enabled_namespace_names(normalized_cluster_id)' in protected
    assert 'namespaces = get_enabled_namespace_names(normalized_cluster_id)' in protected


def test_protected_reveal_revalidates_policy_at_every_security_boundary() -> None:
    protected = read('app/kubernetes/operations/secrets/reveal_service.py')

    create_block = protected.split('def create_reveal_request(', 1)[1].split('def decide_reveal_request(', 1)[0]
    approve_block = protected.split('def decide_reveal_request(', 1)[1].split('def get_reveal_request_for_user(', 1)[0]
    reveal_block = protected.split('def reveal_secret_value(', 1)[1]

    assert 'if not _cluster_ready(cluster):' in create_block
    assert 'namespace_policy = get_namespace_policy(cluster.id, target.namespace)' in create_block
    assert "namespace_policy not in {'step_up', 'approval_required'}" in create_block

    assert 'current_policy = get_namespace_policy(record.cluster_id, record.namespace)' in approve_block
    assert 'not _cluster_ready(cluster)' in approve_block
    assert "current_policy != 'approval_required'" in approve_block
    assert 'record.policy != current_policy' in approve_block

    assert 'not _cluster_ready(cluster)' in reveal_block
    assert 'current_policy = get_namespace_policy(record.cluster_id, record.namespace)' in reveal_block
    assert "current_policy not in {'step_up', 'approval_required'}" in reveal_block
    assert 'current_policy != record.policy' in reveal_block


def test_configuration_changes_invalidate_active_protected_reveal_requests() -> None:
    policy = read('app/kubernetes/operations/secrets/reveal_policy.py')

    readiness_block = policy.split('def update_cluster_reveal_readiness(', 1)[1].split(
        'def set_namespace_reveal_policy(', 1
    )[0]
    namespace_block = policy.split('def set_namespace_reveal_policy(', 1)[1].split(
        'def build_namespace_policy_rows(', 1
    )[0]

    assert "SecretRevealRequest.status.in_(('pending', 'approved'))" in readiness_block
    assert "{'status': 'expired'}" in readiness_block
    assert 'if normalized_policy != previous_policy:' in namespace_block
    assert "SecretRevealRequest.status.in_(('pending', 'approved'))" in namespace_block
    assert "{'status': 'expired'}" in namespace_block


def test_protected_reveal_pagination_uses_title_case_resource_label() -> None:
    request_status = read('app/templates/kubernetes/operations/secrets/_reveal_request_status.html')

    assert "{{ 'Request' if my_reveal_pagination.total == 1 else 'Requests' }}" in request_status
    assert "{{ 'request' if my_reveal_pagination.total == 1 else 'requests' }}" not in request_status
    assert 'aria-label="Rows Per Page"' in request_status
    assert 'uppercase tracking-wide' not in request_status


def test_secret_reveal_dark_mode_keeps_violet_for_accents_and_actions() -> None:
    administration = read('app/templates/platform_operations/kubernetes/_secret_reveal_workspace.html')
    namespace_section = read(
        'app/templates/platform_operations/kubernetes/secret_reveal/_namespace_policy_section.html'
    )
    namespace_table = read(
        'app/templates/platform_operations/kubernetes/secret_reveal/_namespace_policy_table_content.html'
    )
    request_form = read('app/templates/kubernetes/operations/secrets/_reveal_request_form.html')
    request_status = read('app/templates/kubernetes/operations/secrets/_reveal_request_status.html')

    assert 'bg-white/70' not in administration
    assert 'bg-surface-card text-status-warning-text' in administration

    assert 'hover:bg-kaori-soft/40' not in namespace_section
    assert 'hover:bg-surface-hover hover:text-content-primary' in namespace_section
    assert 'bg-kaori-soft/70' not in namespace_table
    assert 'border-b border-outline-default bg-surface-hover' in namespace_table
    assert 'hover:bg-kaori-soft/40' not in namespace_table
    assert 'hover:bg-surface-hover' in namespace_table

    assert 'rounded-xl bg-kaori-primary text-white' not in request_form
    assert 'border border-outline-subtle bg-kaori-soft text-kaori-primary' in request_form
    assert 'space-y-1 text-xs leading-5 text-content-secondary' in request_form
    assert 'hover:bg-kaori-soft' not in request_status
    assert "table_label.status_label('Revealed', 'info'" in request_status
