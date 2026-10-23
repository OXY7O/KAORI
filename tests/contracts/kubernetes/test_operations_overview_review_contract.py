from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_operations_overview_is_permission_scoped_navigation() -> None:
    routes = read('app/kubernetes/operations/routes.py')
    menu = read('app/templates/components/navigation/kubernetes_operations_menu.html')
    page = read('app/templates/kubernetes/operations/overview.html')
    assert '@any_permission_required(' in routes
    assert "endpoint='overview'" in routes
    assert "'kubernetes/operations/overview.html'," in routes
    assert 'cluster_posture=get_operations_cluster_posture()' in routes
    assert 'from app.kubernetes.operations.operation_flow import cluster_required' in routes
    overview_decorators = routes.split('def kubernetes_operations_overview():', 1)[0]
    assert "@cluster_required(\n    'Kubernetes Operations'," in overview_decorators
    assert overview_decorators.rindex('@any_permission_required(') < overview_decorators.rindex('@cluster_required(')
    blocker = read('app/templates/kubernetes/operations/cluster_required.html')
    assert "requested_page_title == 'Operations Overview'" in blocker
    assert 'No Cluster Registered' in blocker
    assert 'Target Validation Pending' in blocker
    assert 'components/cluster/_hero_blocked_context.html' in blocker
    assert 'components/cluster/_onboarding_banner.html' in blocker
    assert 'data-kubernetes-operation-capabilities' not in blocker
    assert 'Target Validation Required' in page
    assert "'Governed'," not in page
    assert "url_for('kubernetes_operations.overview')" in menu
    catalog = read('app/common/workspace_navigation_catalog.py')
    navigation = read('app/common/workspace_navigation.py')
    assert "'operations'," in catalog
    assert "'kubernetes_operations.overview'," in catalog
    assert "'kubernetes_operations.overview': 'overview'" in navigation
    assert "return 'kubernetes_operations.secret_management'" not in navigation
    assert "url_for('kubernetes_operations.configmap_management')" in page
    assert "url_for('kubernetes_operations.secret_management')" in page
    assert 'data-kubernetes-operation-capabilities' in page
    assert 'current_user.has_permission(' in page
    assert 'components/workspace_link_card.html' in page


def test_both_delete_pages_use_shared_governed_confirmation() -> None:
    component = read('app/templates/components/destructive_confirmation_modal.html')
    script = read('app/static/js/destructive_confirmation_modal.js')
    for resource in ('configmaps', 'secrets'):
        page = read(f'app/templates/kubernetes/operations/{resource}/delete.html')
        assert "presentation='kubernetes'" in page
        assert 'components/destructive_confirmation_modal.html' in page
    assert "presentation == 'kubernetes'" in component
    assert 'data-destructive-target-name' in component
    assert 'data-destructive-target-scope' in component
    assert 'data-destructive-detail' in component
    assert 'data-destructive-modal-confirm' in component
    assert 'selectedOptions[0]' in script
    assert 'opener?.focus()' in script


def test_kubernetes_operations_copy_keeps_provider_authority_and_live_target_guidance() -> None:
    overview = read('app/templates/kubernetes/operations/overview.html')
    assert 'Manage audited tasks; Kubernetes executes each change.' in overview
    assert 'Select and verify a live target in its workspace.' in overview


def test_operations_overview_supporting_copy_is_compact_and_responsive() -> None:
    overview = read('app/templates/kubernetes/operations/overview.html')
    descriptions = (
        'Manage audited tasks; Kubernetes executes each change.',
        'Select and verify a live target in its workspace.',
        'Enforce permissions and operation-specific checks.',
        'Provider executes; KAORI retains audit evidence.',
    )
    for description in descriptions:
        assert description in overview
        assert len(description) <= 55

    for heading in ('Select a Live Target', 'Validate Before Mutation', 'Commit Auditable Outcome'):
        assert heading in overview
    assert 'md:grid-cols-3' in overview
    assert 'text-xs leading-5 text-content-secondary' in overview
    assert 'page_hero.description_classes()' in overview
    assert 'whitespace-nowrap' not in overview
    assert 'truncate' not in overview
    assert "current_user.has_permission('kubernetes_configmaps.view')" in overview
    assert "current_user.has_permission('kubernetes_secrets.view')" in overview


def test_operations_catalog_headings_use_canonical_title_guide() -> None:
    shared = read('app/templates/components/operational_workflow_catalog.html')
    assert 'components/info_tip.html' in shared
    assert "variant='guide'" in shared
    assert 'info_id and info_title' in shared

    for domain, title, guide_id in (
        ('configmaps', 'Choose a ConfigMap Operation', 'configmap-operation-catalog-guide'),
        ('secrets', 'Choose a Secret Operation', 'secret-operation-catalog-guide'),
    ):
        page = read(f'app/templates/kubernetes/operations/{domain}/index.html')
        assert title in page
        assert f"info_id='{guide_id}'" in page
        assert 'info_items=[' in page


def test_operations_overview_uses_committed_cluster_connection_evidence() -> None:
    flow = read('app/kubernetes/operations/operation_flow.py')
    routes = read('app/kubernetes/operations/routes.py')
    page = read('app/templates/kubernetes/operations/overview.html')
    assert 'def get_operations_cluster_posture()' in flow
    assert 'Cluster.status == ClusterStatus.CONNECTED.value' in flow
    assert 'Cluster.last_check.is_not(None)' in flow
    assert 'except SQLAlchemyError:' in flow
    assert 'cluster_posture=get_operations_cluster_posture()' in routes
    assert "cluster_posture['connection_label']" in page
    assert "cluster_posture['needs_attention']" in page
    assert "cluster_posture['status_detail']" in page
    assert 'components/operational_callout.html' in page
    assert 'Open Cluster Integrations' in page
    assert 'core_api(' not in flow
    assert 'kubernetes_client(' not in flow
