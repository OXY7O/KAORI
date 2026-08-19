from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_binding_decision_is_shared_and_keeps_readiness_dimensions_independent() -> None:
    shared = read('app/templates/integrations/components/_binding_readiness_boundary.html')
    prom = read('app/templates/integrations/observability/metrics_source/partials/_detail_scope.html')
    alert = read(
        'app/templates/integrations/observability/alert_source/providers/alertmanager/partials/_detail_scope.html'
    )

    assert 'data-kaori-binding-readiness-boundary' in shared
    for marker in (
        'Source Ready',
        'Bindings Validated',
        'Resolver Paths Ready',
        'Resolver Preference',
        'Source-Owned Mutation',
        'Primary resolves before Secondary, then Fallback',
        'Validation Required',
    ):
        assert marker in shared

    for source in (prom, alert):
        assert '_binding_readiness_boundary.html' in source
        assert 'binding_readiness_boundary.render(' in source
        assert "title='Binding Decision'" in source

    assert "marker='data-kaori-binding-decision-horizontal'" in prom
    assert "identity_title='Consumer Identity Boundary'" in prom
    assert "marker='data-kaori-alertmanager-binding-decision-horizontal'" in alert
    assert "identity_title='Alert Identity Boundary'" in alert


def test_metrics_source_and_alertmanager_binding_registries_share_summary_first_contract() -> None:
    layout = read('app/templates/integrations/components/_binding_registry_layout.html')
    prom = read('app/templates/integrations/observability/metrics_source/partials/_binding_registry.html')
    alert = read(
        'app/templates/integrations/observability/alert_source/providers/alertmanager/partials/_binding_registry.html'
    )

    assert 'table_ui.table_classes' in layout
    assert 'min-w-[72rem]' in layout
    assert 'data-kaori-binding-registry-columns' in layout
    for width in ('w-[30%]', 'w-[18%]', 'w-[34%]'):
        assert width in layout
    assert layout.count('w-[30%]') == 1
    assert layout.count('w-[18%]') == 2
    assert layout.count('w-[34%]') == 1
    assert 'detail_grid_classes' in layout
    assert 'detail_item_classes' in layout
    assert 'flex min-w-0 flex-nowrap items-center justify-end gap-2 whitespace-nowrap' in layout

    summary_columns = (
        'Consumer Binding',
        'Binding Validation',
        'Effective Resolution',
        'Actions',
    )
    expanded_labels = (
        'Consumer Profile',
        'Resolver Preference',
    )
    for source in (prom, alert):
        assert 'data-kaori-binding-registry-final-lock' in source
        assert '_binding_registry_layout.html' in source
        assert 'data-kaori-binding-registry-table' in source
        assert 'binding_registry_layout.columns()' in source
        assert 'binding_registry_layout.state_cell_classes()' in source
        assert 'binding_registry_layout.action_group_classes()' in source
        assert 'binding_registry_layout.detail_grid_classes()' in source
        assert 'binding_registry_layout.detail_item_classes()' in source
        assert 'data-kaori-binding-view-more' in source
        actions = source.split('data-kaori-binding-actions', 1)[1].split('</div>', 1)[0]
        row_body = source.split('{% for row in binding_registry_rows %}', 1)[1]
        consumer_cell = row_body.split('<td class="{{ table_ui.cell_classes() }}">', 1)[1].split('</td>', 1)[0]
        assert 'View More' in actions
        assert 'data-kaori-binding-view-more' in actions
        assert 'data-kaori-binding-view-more' not in consumer_cell
        assert 'data-kaori-binding-details-row' in source
        assert 'data-kaori-binding-secondary-details' in source
        assert 'colspan="4"' in source
        assert 'overscroll-x-contain' in source
        assert 'components/pagination.html' in source
        assert 'components/loading_bar.html' in source
        assert 'binding_registry_pagination.allowed_per_page' in source
        assert 'Validate before eligibility' in source
        assert 'Resolver eligible' in source
        for column in summary_columns:
            assert column in source
        for label in expanded_labels:
            assert label in source

    assert 'Metrics Identity' in prom
    assert 'Alert Identity' in alert
    assert 'row.consumer_profile_label' in prom
    assert 'row.consumer_profile_label' in alert


def test_binding_validation_polling_uses_the_shared_terminal_aware_poller() -> None:
    prom = read('app/templates/integrations/observability/metrics_source/partials/_detail_scope.html')
    alert = read(
        'app/templates/integrations/observability/alert_source/providers/alertmanager/partials/_detail_scope.html'
    )
    poller = read('app/templates/integrations/components/_validation_poller.html')
    state = read('app/integrations/validation/state.py')
    web = read('app/integrations/validation/web.py')
    metrics_routes = read('app/integrations/observability/metrics_source/application/binding_web.py')
    alert_routes = read(
        'app/integrations/observability/alert_source/providers/alertmanager/application/routes.py'
    )

    assert 'data-kaori-validation-poller' in poller
    assert 'hx-trigger="every {{ delay }}"' in poller
    for source, target in (
        (prom, '#metrics-source-scope-workspace'),
        (alert, '#alertmanager-scope-workspace'),
    ):
        assert '_validation_poller.html' in source
        assert 'validation_poller.render(' in source
        assert target in source
        assert 'hx-trigger="load delay:1500ms" hx-target="this"' not in source

    assert 'def validation_poll_response(' in web
    assert "response.headers['Cache-Control'] = 'no-store, max-age=0'" in web
    assert "response.headers['HX-Trigger'] = '{\"kaori:notifications-changed\":{}}'" in web
    assert 'def _reconcile_terminal_job(' in state
    assert "'is_active': False if terminal" in state
    assert "'is_complete': True if terminal" in state
    assert 'validation_poll_response(content, snapshot=snapshot)' in metrics_routes
    assert 'validation_poll_response(content, snapshot=snapshot)' in alert_routes

    metrics_registry = read('app/templates/integrations/observability/metrics_source/partials/_binding_registry.html')
    alert_registry = read(
        'app/templates/integrations/observability/alert_source/providers/alertmanager/partials/_binding_registry.html'
    )
    result = read('app/templates/integrations/components/_binding_validation_result.html')
    for registry in (metrics_registry, alert_registry):
        assert "'Validating'" in registry
        assert 'disabled:cursor-wait' in registry
        assert 'View More' in registry
        assert 'data-kaori-binding-view-more' in registry
        assert '_binding_validation_result.html' in registry
    assert 'Binding Validation Result' in result

    navbar = read('app/templates/components/navigation/navbar.html')
    feedback = read('app/templates/components/operation_feedback_oob.html')
    assert 'kaori:notifications-changed' in navbar
    assert 'operation_feedback_oob' in prom
    assert 'operation_feedback_oob' in alert
    assert "{% include 'components/operational_toast.html' %}" in feedback


def test_worker_completion_terminalizes_jobs_and_refreshes_operational_feedback() -> None:
    tasks = read('app/integrations/validation/tasks.py')
    completion = read('app/integrations/validation/completion.py')
    web = read('app/integrations/validation/web.py')
    navbar = read('app/templates/components/navigation/navbar.html')

    binding_body = tasks.split('def validate_integration_binding', 1)[1].split(
        '@shared_task(', 1
    )[0]
    assert binding_body.index('_record_completion(') < binding_body.index('final_payload(')
    assert 'mark_job_succeeded(' in completion
    assert 'mark_job_failed(' in completion
    assert "response.headers['HX-Trigger'] = '{\"kaori:notifications-changed\":{}}'" in web
    assert '@kaori:notifications-changed.window' in navbar


def test_runtime_refresh_polling_and_asset_profile_parity_are_global() -> None:
    poller = read('app/templates/integrations/components/_validation_poller.html')
    runtime_templates = (
        read('app/templates/integrations/observability/metrics_source/partials/_runtime_panel.html'),
        read(
            'app/templates/integrations/observability/alert_source/providers/alertmanager/partials/_runtime_panel.html'
        ),
        read('app/templates/integrations/storage/object_storage/providers/minio/partials/_detail_runtime.html'),
        read(
            'app/templates/integrations/orchestration/container_orchestrator/providers/kubernetes/partials/_runtime_workspace.html'
        ),
    )
    assert 'hx-trigger="every {{ delay }}"' in poller
    for source in runtime_templates:
        assert '_validation_poller.html' in source
        assert 'validation_poller.render(' in source
        assert 'hx-trigger="load delay:1500ms"' not in source

    metrics_contract = read(
        'app/definitions/catalogs/integrations/observability/metrics_source/contract.yaml'
    )
    alert_contract = read(
        'app/definitions/catalogs/integrations/observability/alert_source/providers/alertmanager.yaml'
    )
    assert 'asset_type: kubernetes_cluster' in metrics_contract
    assert 'asset_type: object_storage_system' in metrics_contract
    assert 'profile_key: kubernetes-metrics-v1' in metrics_contract
    assert 'profile_key: object-storage-metrics-v1' in metrics_contract
    assert 'asset_type: kubernetes_cluster' in alert_contract
    assert 'asset_type: object_storage_system' in alert_contract


def test_shared_add_binding_modal_locks_workflow_roles_and_source_ownership() -> None:
    modal = read('app/templates/integrations/components/_observability_binding_modal.html')

    for marker in (
        'data-kaori-binding-workflow',
        'Binding Workflow',
        'Consumer &amp; Resolver Preference',
        'Primary',
        'Secondary',
        'Fallback',
        'Lower priority wins within the same role',
        'Resolved Consumer Profile',
        'data-kaori-binding-identity-boundary',
        'Source-Owned Mutation Boundary',
        'Validation Required',
        'Create Binding',
    ):
        assert marker in modal

    assert 'm-auto w-[min(46rem,calc(100vw-2rem))]' in modal
    assert 'min-w-0 flex-1 text-xs leading-5 text-content-muted' in modal
    assert 'flex shrink-0 items-center justify-end gap-2' in modal
    assert 'whitespace-nowrap rounded-lg bg-kaori-primary' in modal


def test_binding_runtime_contract_keeps_validation_required_transition_and_roles() -> None:
    prom = read('app/integrations/observability/metrics_source/binding_management.py')
    alert = read('app/integrations/observability/alert_source/providers/alertmanager/binding_management.py')

    for source in (prom, alert):
        assert "{'primary', 'secondary', 'fallback'}" in source
        assert "binding.validation_status = 'validation_required'" in source
        assert 'binding.validation_evidence = None' in source
        assert 'binding.last_validated_at = None' in source


def test_consumer_asset_parity_and_source_owned_mutation_remain_locked() -> None:
    assets = read('app/integrations/consumer_assets.py')
    taxonomy_catalog = read('app/definitions/catalogs/integrations/taxonomy.yaml')
    asset_table = read('app/templates/integrations/components/_asset_owner_observability_sources.html')
    standard = read('docs/design/components/INTEGRATIONS_WORKSPACE_STANDARD.md')

    assert 'integration_taxonomy_document()' in assets
    assert 'asset_type: kubernetes_cluster' in taxonomy_catalog
    assert 'asset_type: object_storage_system' in taxonomy_catalog
    for marker in ('Source Readiness', 'Binding Validation', 'Effective Resolution'):
        assert marker in asset_table
    assert 'Bindings & Consumers final-lock contract (2026-08-13)' in standard
    assert 'source-owned mutation' in standard.lower()


def test_final_lock_templates_do_not_add_page_local_style_debt() -> None:
    paths = (
        'app/templates/integrations/components/_observability_binding_modal.html',
        'app/templates/integrations/components/_binding_readiness_boundary.html',
        'app/templates/integrations/observability/metrics_source/partials/_binding_registry.html',
        'app/templates/integrations/observability/alert_source/providers/alertmanager/partials/_binding_registry.html',
    )
    for path in paths:
        source = read(path)
        assert 'text-[' not in source
        assert 'tracking-[' not in source
        assert 'rounded-3xl' not in source


def test_integrations_final_lock_verifier_owns_binding_contract() -> None:
    verifier = read('scripts/verify_integrations_final_lock.py')
    for marker in (
        'Observability Bindings & Consumers final-lock contract.',
        'data-kaori-binding-readiness-boundary',
        'data-kaori-binding-workflow',
        'data-kaori-binding-registry-final-lock',
        'Resolver Preference',
        'Validate before eligibility',
    ):
        assert marker in verifier
