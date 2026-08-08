from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text()


def test_identity_provider_route_uses_server_side_filter_payload_and_htmx_registry() -> None:
    routes = read('app/users/routes.py')
    service = read('app/users/service.py')
    assert 'normalize_provider_filters(request.args.to_dict())' in routes
    assert 'build_identity_provider_payload(filters)' in routes
    assert "request.headers.get('HX-Request') == 'true'" in routes
    assert "users/providers/partials/_registry.html" in routes
    assert 'PROVIDER_TYPE_OPTIONS' in service
    assert 'PROVIDER_STATE_OPTIONS' in service
    assert "'page': positive_int(args.get('page'), 1)" in service
    assert "'per_page': normalize_per_page(args.get('per_page'))" in service
    assert 'ExternalIdentityLink.provider_id' in service
    assert "'ldap_identity_links': ldap_identity_links" in service


def test_identity_provider_hero_and_overview_follow_kaori_operational_grammar() -> None:
    template = read('app/templates/users/providers/index.html')
    assert 'page_hero.context_card(' in template
    assert 'page_hero.context_panel_classes()' not in template
    assert 'Provider Registry Overview' in template
    for label in ('Configured', 'Enabled', 'LDAP', 'SSO'):
        assert label in template
    for boundary in (
        'Credential Ownership',
        'Runtime Validation',
        'Identity Projection',
        'Authorization Boundary',
    ):
        assert boundary in template
    assert 'enablement does not imply validation success' in template


def test_provider_registry_uses_shared_table_loading_filters_and_expandable_details() -> None:
    registry = read('app/templates/users/providers/partials/_registry.html')
    assert '{% import "components/table.html" as table_ui %}' in registry
    assert '{% import "components/loading_bar.html" as loading_bar %}' in registry
    assert '{% import "components/details/_expandable_row.html" as expandable %}' in registry
    assert 'Search Provider' in registry
    assert 'Provider Type' in registry
    assert 'Provider State' in registry
    assert 'hx-target="#identity-provider-registry"' in registry
    assert 'identity-provider-registry-loading' in registry
    for heading in ('Provider', 'Type', 'Configuration', 'State', 'Identity Links', 'Action'):
        assert heading in registry
    assert "expandable.toggle_button('identity-providers'" in registry
    assert 'users/providers/partials/_provider_detail.html' in registry
    assert '{% import "components/pagination.html" as pagination_ui %}' in registry
    assert 'Showing {{ pagination.start_item }}–{{ pagination.end_item }} of {{ pagination.total_items }}' in registry
    assert '>Rows</span>' in registry
    assert 'Rows Per Page' in registry
    assert '>Previous</span>' in registry
    assert 'Next<i data-lucide="chevron-right"' in registry


def test_provider_detail_keeps_validation_on_demand_and_secrets_externalized() -> None:
    service = read('app/users/service.py')
    detail = read('app/templates/users/providers/partials/_provider_detail.html')
    assert "'label': 'On Demand'" in service
    assert 'Validation runs live and is not stored as durable provider readiness evidence.' in service
    assert 'Credential Reference' in detail
    assert 'Validate Provider' in detail
    assert 'Directory Provisioning' in detail
    for forbidden in ('Client Secret Value', 'Bind Password Value', 'Last Validated'):
        assert forbidden not in detail
        assert forbidden not in service


def test_identity_provider_index_uses_full_width_registry_and_directory_workflow_strip() -> None:
    template = read('app/templates/users/providers/index.html')
    strip = read('app/templates/users/providers/partials/_directory_provisioning_strip.html')
    assert 'users/providers/partials/_directory_provisioning_strip.html' in template
    assert 'users/providers/partials/_registry.html' in template
    assert 'xl:grid-cols-12' not in template
    assert '_index_guidance.html' not in template
    assert 'Authentication Boundary' not in template
    assert 'Provider Types' not in template
    assert 'Directory Provisioning' in strip
    assert 'LDAP Workflow' in strip
    assert 'summary.ldap' in strip
    assert 'summary.ldap_identity_links' in strip
    assert "url_for('users.external_identities')" in strip


def test_identity_provider_form_uses_shared_hero_ldap_flow_and_sticky_guidance() -> None:
    form = read('app/templates/users/providers/form.html')
    guidance = read('app/templates/users/providers/partials/_provider_guidance.html')
    ldap = read('app/templates/users/providers/partials/_ldap_configuration.html')
    routes = read('app/users/routes.py')
    assert 'page_hero.context_card(' in form
    assert 'page_hero.context_panel_classes()' not in form
    assert "'Configuration Scope'" in form
    assert 'xl:sticky xl:top-5' in guidance
    assert '{% import "components/operational_flow_steps.html" as flow_steps %}' in guidance
    assert "'LDAP Setup Guidance'" in guidance
    assert 'open_by_default=true' in guidance
    assert "flow_steps.render(ldap_flow_rows, aria_label='LDAP Setup Flow')" in guidance
    assert guidance.count('open_by_default=false') >= 3
    assert 'Exact Callback URL' in guidance
    assert 'Technical Runbook' in guidance
    assert '<details open' not in guidance
    assert 'font-mono' not in ldap
    assert 'font-mono' not in guidance
    assert 'Test Connection' in form
    assert "url_for('users.test_provider_configuration'" in form
    assert "@bp.post('/providers/test')" in routes
    assert "@bp.post('/providers/<int:provider_id>/test')" in routes
    assert 'candidate = IdentityProvider()' in routes
    assert 'validate_identity_provider(candidate)' in routes


def test_identity_provider_refinement_remains_open_before_final_lock() -> None:
    readme = read('app/users/README.md')
    audit = read('docs/design/audits/KAORI_IDENTITY_PROVIDERS_REFINEMENT_AUDIT_2026_08_09.md')
    assert 'Identity Providers refinement baseline' in readme
    assert 'not the Identity Providers Final Lock' in readme
    assert 'does not final-lock the Access domain' in audit
    assert 'Configured`, `Enabled`, and runtime validation' in audit
