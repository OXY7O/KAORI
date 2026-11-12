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


def test_operations_overview_follows_inventory_section_hierarchy_with_metadata_badges() -> None:
    page = read('app/templates/kubernetes/operations/overview.html')
    inventory = read('app/templates/kubernetes/inventory/overview/index.html')
    catalog = read('app/templates/kubernetes/inventory/overview/partials/_kpi_cards.html')

    assert 'components/section_intro.html' in inventory
    assert 'components/section_intro.html' in page
    assert 'components/table_label.html' in page
    assert 'table_label.metadata_label(' in catalog
    assert 'header_badge=capability_badge' in page
    assert "available_capabilities ~ (' Workspace' if available_capabilities == 1 else ' Workspaces')" in page
    assert 'components/info_tip.html' in page
    assert "info_tip.render('operations-execution-evidence-guide'" in page
    assert "'Execution & Evidence Model Guide'" in page
    assert "variant='guide'" in page
    assert "placement='right'" in page
    assert "table_label.metadata_label('Info', icon='info')" not in page
    assert 'header_badge=execution_guide' in page

    for heading, section_id in (
        ('Operational Capabilities', 'operations-capabilities-heading'),
        ('Execution Governance', 'operations-execution-heading'),
    ):
        assert f"section_intro.render('{heading}'" in page
        assert f'aria-labelledby="{section_id}"' in page
        assert f"'{section_id}'" in page

    assert page.index("section_intro.render('Operational Capabilities'") < page.index("'Operation Workspace Catalog'")
    assert page.index("section_intro.render('Execution Governance'") < page.index("'Execution & Evidence Model'")
    assert page.index("'Operation Workspace Catalog'") < page.index("'Execution & Evidence Model'")


def test_operations_cards_opt_into_compact_navigation_without_changing_defaults() -> None:
    page = read('app/templates/kubernetes/operations/overview.html')
    shared = read('app/templates/components/workspace_link_card.html')

    assert 'macro render(workspace, compact=false)' in shared
    assert 'min-h-40' in shared
    assert 'min-h-56' in shared
    assert 'set body_classes = "mt-4 min-w-0 flex-1"' in shared
    assert 'workspace.href' in shared
    assert 'workspace.search_text' in shared
    assert 'workspace.scope' in shared
    assert 'aria-label="Open {{ workspace.title }} Workspace"' in shared
    assert 'data-workspace-card' in shared

    assert page.count('compact=true) }}') == 2
    assert 'sm:grid-cols-2' in page
    assert "url_for('kubernetes_operations.configmap_management')" in page
    assert "url_for('kubernetes_operations.secret_management')" in page
    assert '{% if can_configmaps %}' in page
    assert '{% if can_secrets %}' in page


def test_execution_evidence_guide_uses_shared_hover_focus_accessible_popover() -> None:
    overview = read('app/templates/kubernetes/operations/overview.html')
    guide = read('app/templates/components/info_tip.html')

    assert "info_tip.render('operations-execution-evidence-guide'" in overview
    assert "'Select and verify a live Kubernetes target inside the authorized capability workspace.'" in overview
    assert "'Enforce permission checks and operation-specific validation before attempting mutation.'" in overview
    assert "'Kubernetes executes the operation; KAORI retains the resulting audit evidence.'" in overview
    assert "variant='guide'" in overview
    assert 'data-kaori-info-tip-variant=' in guide
    assert 'data-kaori-info-tip-trigger' in guide
    assert 'data-kaori-info-tip-preview' in guide
    assert 'aria-expanded="false"' in guide
    assert 'role="tooltip"' in guide
    assert '<span>Guide</span>' in guide


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
