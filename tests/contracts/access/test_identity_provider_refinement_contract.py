from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_identity_provider_workspace_is_separate_from_user_lifecycle() -> None:
    routes = read('app/access/identity_providers/routes.py')
    users_routes = read('app/access/users/routes.py')
    service = read('app/access/identity_providers/service.py')
    assert "bp = Blueprint('identity_providers'" in routes
    assert "url_prefix='/access/identity-providers'" in routes
    assert "@permission_required('identity_providers.view')" in routes
    assert "@permission_required('identity_providers.manage')" in routes
    assert "@permission_required('identity_providers.provision')" in routes
    assert 'normalize_provider_filters(request.args.to_dict())' in routes
    assert 'build_identity_provider_payload(filters)' in routes
    assert "request.headers.get('HX-Request') == 'true'" in routes
    assert 'identity_providers' not in users_routes
    assert 'PROVIDER_STATE_OPTIONS' in service
    assert 'provider_filter_options()' in service
    assert 'ExternalIdentityLink.provider_id' in service
    assert "'directory_identity_links': sum(" in service
    assert 'provider_id in directory_provider_ids' in service
    assert 'build_pagination_window(' in service


def test_identity_provider_overview_uses_provider_adapter_boundary_and_tabs() -> None:
    template = read('app/templates/access/identity_providers/index.html')
    overview = read('app/templates/access/identity_providers/partials/_overview.html')
    tabs = read('app/templates/access/identity_providers/partials/_tabs.html')
    assert 'page_hero.context_card(' in template
    assert '{% import "components/table_label.html" as table_label %}' in template
    assert 'components/table_labels.html' not in template
    assert 'Authentication Source Posture' in overview
    for label in ('Configured', 'Enabled', 'Directory', 'Browser SSO'):
        assert label in overview
    for boundary in (
        'Provider / Adapter Boundary',
        'Credential Ownership',
        'Identity Projection',
        'Authorization Boundary',
    ):
        assert boundary in overview
    for tab in ('Overview', 'Providers', 'Directory Provisioning'):
        assert tab in tabs


def test_provider_registry_uses_dynamic_provider_filter_and_shared_kaori_table() -> None:
    registry = read('app/templates/access/identity_providers/partials/_registry.html')
    assert '{% import "components/table.html" as table_ui %}' in registry
    assert '{% import "components/loading_bar.html" as loading_bar %}' in registry
    assert '{% import "components/details/_expandable_row.html" as expandable %}' in registry
    assert 'name="provider_key"' in registry
    assert 'provider_filter_options' in registry
    assert 'provider_type' not in registry
    assert 'google_oidc' not in registry
    assert 'github_oauth' not in registry
    assert 'hx-target="#identity-provider-registry"' in registry
    assert 'access/identity_providers/partials/_provider_detail.html' in registry
    for heading in ('Provider', 'Adapter', 'Configuration', 'State', 'Identity Links', 'Action'):
        assert heading in registry
    assert 'Rows Per Page' in registry
    assert 'pagination_ui.numeric_pages(' in registry


def test_provider_model_and_forms_are_provider_neutral() -> None:
    model = read('app/models/identity.py')
    form = read('app/access/identity_providers/forms.py')
    selector = read('app/templates/access/identity_providers/partials/_provider_selector.html')
    js = read('app/static/js/identity_provider_form.js')
    for required in ('provider_key:', 'adapter_key:', 'configuration_json:', 'admission_policy_json:'):
        assert required in model
    for forbidden in ('provider_type:', 'oidc_client_id:', 'allowed_domains:', 'allowed_subjects:'):
        assert forbidden not in model
    assert "choices=[('', 'Select provider'), *configurable_provider_choices()]" in form
    assert 'data-adapter-key' in selector
    assert 'data-configuration-profile' in selector
    assert 'data-admission-policy' in selector
    for forbidden in ('google_oidc', 'github_oauth', "=== 'google'", "=== 'github'", "=== 'ldap'"):
        assert forbidden not in js


def test_directory_provisioning_dispatches_by_adapter_and_uses_signed_evidence() -> None:
    routes = read('app/access/identity_providers/routes.py')
    proof = read('app/access/identity_providers/provisioning_proof.py')
    template = read('app/templates/access/identity_providers/directory_provisioning.html')
    assert 'get_directory_provider_adapter(selected_provider.adapter_key)' in routes
    assert 'LdapDirectoryClient(selected_provider)' not in routes
    assert 'URLSafeTimedSerializer' in proof
    assert 'PROJECTION_PROOF_MAX_AGE_SECONDS = 600' in proof
    assert 'name="projection_proof"' in template
    assert 'Directory Provisioning' in template


def test_identity_provider_secret_and_validation_evidence_remain_safe() -> None:
    detail = read('app/templates/access/identity_providers/partials/_provider_detail.html')
    service = read('app/access/identity_providers/service.py')
    assert "'label': 'On Demand'" in service
    assert 'Validation runs live and is not stored as durable provider readiness evidence.' in service
    assert 'Credential Reference' in detail
    for forbidden in ('Client Secret Value', 'Bind Password Value', 'Last Validated'):
        assert forbidden not in detail
        assert forbidden not in service
