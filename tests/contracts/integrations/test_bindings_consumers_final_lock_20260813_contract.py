from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_binding_decision_is_shared_and_keeps_readiness_dimensions_independent() -> None:
    shared = read('app/templates/integrations/components/_binding_readiness_boundary.html')
    prom = read('app/templates/prometheus/partials/_detail_scope.html')
    alert = read('app/templates/alertmanager/partials/_detail_scope.html')

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


def test_prometheus_and_alertmanager_binding_registries_share_final_column_contract() -> None:
    prom = read('app/templates/prometheus/partials/_binding_registry.html')
    alert = read('app/templates/alertmanager/partials/_binding_registry.html')

    columns = (
        'Consumer Asset',
        'Consumer Profile',
        'Resolver Preference',
        'Binding Validation',
        'Effective Resolution',
        'Actions',
    )
    for source in (prom, alert):
        assert 'data-kaori-binding-registry-final-lock' in source
        assert 'table-fixed' in source
        assert 'components/pagination.html' in source
        assert 'components/loading_bar.html' in source
        assert 'binding_registry_pagination.allowed_per_page' in source
        assert 'Validate before eligibility' in source
        assert 'Resolver eligible' in source
        assert 'flex flex-nowrap items-center justify-end' in source
        assert 'whitespace-nowrap' in source
        for column in columns:
            assert column in source

    assert 'Metrics Identity' in prom
    assert 'Alert Identity' in alert
    assert 'row.consumer_profile_label' in prom
    assert 'row.consumer_profile_label' in alert


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
    prom = read('app/integrations/prometheus/binding_management.py')
    alert = read('app/integrations/alertmanager/binding_management.py')

    for source in (prom, alert):
        assert "{'primary', 'secondary', 'fallback'}" in source
        assert "binding.validation_status = 'validation_required'" in source
        assert 'binding.validation_evidence = None' in source
        assert 'binding.last_validated_at = None' in source


def test_consumer_asset_parity_and_source_owned_mutation_remain_locked() -> None:
    assets = read('app/integrations/consumer_assets.py')
    asset_table = read('app/templates/integrations/components/_asset_owner_observability_sources.html')
    standard = read('docs/design/components/INTEGRATIONS_WORKSPACE_STANDARD.md')

    assert "asset_type='kubernetes_cluster'" in assets
    assert "asset_type='object_storage_system'" in assets
    for marker in ('Source Readiness', 'Binding Validation', 'Effective Resolution'):
        assert marker in asset_table
    assert 'Bindings & Consumers final-lock contract (2026-08-13)' in standard
    assert 'source-owned mutation' in standard.lower()


def test_final_lock_templates_do_not_add_page_local_style_debt() -> None:
    paths = (
        'app/templates/integrations/components/_observability_binding_modal.html',
        'app/templates/integrations/components/_binding_readiness_boundary.html',
        'app/templates/prometheus/partials/_binding_registry.html',
        'app/templates/alertmanager/partials/_binding_registry.html',
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
