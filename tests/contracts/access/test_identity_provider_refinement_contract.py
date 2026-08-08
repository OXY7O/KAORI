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


def test_identity_provider_index_guidance_is_compact_sticky_and_directory_scoped() -> None:
    guidance = read('app/templates/users/providers/partials/_index_guidance.html')
    assert 'xl:sticky xl:top-5' in guidance
    assert 'Authentication Boundary' in guidance
    assert 'Provider Types' in guidance
    assert 'open_by_default=false' in guidance
    assert 'Directory Provisioning' in guidance
    assert 'summary.ldap_identity_links' in guidance


def test_identity_provider_form_uses_shared_hero_and_default_collapsed_guidance() -> None:
    form = read('app/templates/users/providers/form.html')
    guidance = read('app/templates/users/providers/partials/_provider_guidance.html')
    assert 'page_hero.context_card(' in form
    assert 'page_hero.context_panel_classes()' not in form
    assert "'Configuration Scope'" in form
    assert 'xl:sticky xl:top-5' in guidance
    assert guidance.count('open_by_default=false') >= 4
    assert 'Exact Callback URL' in guidance
    assert 'Technical Runbook' in guidance
    assert '<details open' not in guidance


def test_identity_provider_refinement_remains_open_before_final_lock() -> None:
    readme = read('app/users/README.md')
    audit = read('docs/design/audits/KAORI_IDENTITY_PROVIDERS_REFINEMENT_AUDIT_2026_08_09.md')
    assert 'Identity Providers refinement baseline' in readme
    assert 'not the Identity Providers Final Lock' in readme
    assert 'does not final-lock the Access domain' in audit
    assert 'Configured`, `Enabled`, and runtime validation' in audit
