from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_pod_inventory_applies_resource_page_pattern() -> None:
    hero = read('app/templates/kubernetes/inventory/pods/partials/_hero.html')
    summary = read('app/templates/kubernetes/inventory/pods/partials/_summary_cards.html')
    table = read('app/templates/kubernetes/inventory/pods/partials/_table_content.html')

    assert 'page_hero.context_card(' in hero
    assert "inventory.total_pods ~ ' Pods in Scope'" in hero
    assert 'inventory.owner_type_count' in hero
    assert 'inventory.ready_count' in hero
    assert 'inventory.exception_count' in hero
    assert 'posture_grid.render(posture_metrics, columns=4)' in summary
    assert 'Running Coverage' not in summary
    assert '>Pod</th>' in table
    assert '>Scope</th>' in table
    assert '>Runtime State</th>' in table
    assert '>Placement</th>' in table
    assert '>Ownership & Activity</th>' in table
    assert 'table_ui.namespaced_scope_identity(' in table
    assert 'pod.operational_state_label' in table
    assert 'pod.state_evidence' in table


def test_pod_filters_are_owner_aware_and_workspace_scoped() -> None:
    service = read('app/kubernetes/inventory/resources/pods.py')
    routes = read('app/kubernetes/inventory/routes.py')
    card = read('app/templates/kubernetes/inventory/pods/partials/_table_card.html')
    content = read('app/templates/kubernetes/inventory/pods/partials/_table_content.html')

    assert 'owner_type: str | None = None' in service
    assert "func.nullif(func.trim(PodInventory.workload_type), '')" in service
    assert 'get_pod_filter_statuses(' in routes and 'owner_type=owner_type' in routes
    assert 'get_pod_filter_nodes(' in routes and routes.count('owner_type=owner_type') >= 2
    assert 'hx-trigger="change, keyup changed delay:500ms from:find input[name=\'search\']"' in card
    assert 'hx-target="#pods-page-workspace"' in card
    assert 'name="partial_mode" value="page_workspace"' in card
    assert 'hx-target="#pods-table-content"' in content
    assert 'hx-swap="innerHTML"' in content
    assert "'partial_mode': 'table_content'" in content
    assert "endpoint='inventory.pods'" in content


def test_pod_operational_state_separates_phase_and_readiness() -> None:
    semantics = read('app/kubernetes/inventory/resources/pod_semantics.py')

    assert "state = 'Ready' if ready_total > 0 and ready_count == ready_total else 'Not Ready'" in semantics
    assert "state = 'Starting'" in semantics
    assert "state = 'Terminating'" in semantics
    assert "state = 'Completed'" in semantics
    assert "state = 'Failed'" in semantics
    assert "elif str(ready or '').casefold() == 'not reported':" in semantics
    assert 'return state, OPERATIONAL_STATE_TONES[state], evidence' in semantics


def test_pod_detail_uses_shared_runtime_references_and_metadata_components() -> None:
    detail = read('app/templates/kubernetes/inventory/pods/partials/_pod_detail_content.html')
    runtime = read('app/templates/components/container_runtime_collection.html')
    related = read('app/templates/components/related_resource_collection.html')
    semantics = read('app/kubernetes/inventory/resources/pod_semantics.py')

    assert 'container_collection.render(pod.container_statuses)' in detail
    assert "related_collection.inventory_render('Configuration References'" in detail
    assert "related_collection.inventory_render('Storage References'" in detail
    assert "metadata_collection.render('Pod Labels'" in detail
    assert "metadata_collection.render('Pod Annotations'" in detail
    assert "normalized_state == 'terminated'" in semantics
    assert "exit_code in (0, '0')" in semantics
    assert '{% if resource.status %}' in related
    assert 'Runtime State' in runtime
    assert 'Restart Activity' in runtime


def test_pod_detail_does_not_apply_implicit_configuration_scoring() -> None:
    detail = read('app/templates/kubernetes/inventory/pods/partials/_pod_detail_content.html')

    rejected = (
        'qos_tones',
        'restart_policy_tones',
        'dns_policy_tones',
        "status_label(selector, 'normal'",
        "status_label(selector, 'info'",
    )
    for token in rejected:
        assert token not in detail
    assert 'remain factual evidence until compared with an explicit governance policy' in detail
