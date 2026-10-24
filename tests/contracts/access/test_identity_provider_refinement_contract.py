import json
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
        'Provider & Adapter',
        'Credential Ownership',
        'Identity Projection',
        'Authorization Boundary',
    ):
        assert boundary in overview
    # The posture overview is always visible; only the records have routable tabs.
    assert 'Authentication Source Posture' in overview
    assert "('providers', 'Provider Registry'" in tabs
    assert "('directory', 'Directory Provisioning'" in tabs
    assert 'framed_tabs.render_navigation(' in tabs
    assert "hx_target='#identity-provider-workspace'" in tabs


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
    # The shared registry filter renders the HTMX target from its positional ID.
    assert 'registry_ui.filter_form(' in registry
    assert "'identity-provider-registry'," in registry
    shared = read('app/templates/components/table_registry.html')
    assert 'hx-target="#{{ registry_id }}"' in shared
    assert 'access/identity_providers/partials/_provider_detail.html' in registry
    # Match the Users disclosure control; always show a descriptive label.
    assert "open_label='View More Details', close_label='Hide Details'" in registry
    assert "compact=true, class_name='min-w-[7.5rem]'" in registry
    assert 'table_action=true' not in registry
    users = read('app/templates/access/users/partials/_table.html')
    assert "compact=true)" in users
    toggle = read('app/templates/components/details/_expandable_row.html')
    assert '<span data-detail-toggle-label>{{ open_label }}</span>' in toggle
    assert 'aria-expanded="false"' in toggle

    for heading in ('Provider', 'Adapter', 'Configuration', 'State', 'Identity Links', 'Action'):
        assert heading in registry
    assert 'Rows Per Page' in registry
    assert 'registry_ui.footer(' in registry
    assert 'pagination_ui.numeric_pages(' in shared


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


def test_identity_provider_form_family_reuses_shared_surface_and_semantic_authority() -> None:
    template_paths = (
        'app/templates/access/identity_providers/form.html',
        'app/templates/access/identity_providers/partials/_ldap_configuration.html',
        'app/templates/access/identity_providers/partials/_provider_guidance.html',
        'app/templates/access/identity_providers/partials/_provider_selector.html',
        'app/templates/access/identity_providers/partials/_sso_configuration.html',
    )
    sources = {path: read(path) for path in template_paths}
    baseline = json.loads(read('docs/architecture/ui-style-debt-baseline.json'))

    for path, source in sources.items():
        assert 'components/operational_section_card.html' in source, path
        assert 'overflow-hidden rounded-xl border border-outline-default bg-surface-card shadow-sm' not in source, path
        assert path not in baseline['files']

    assert sum(source.count('operational_section_card.shell_classes()') for source in sources.values()) == 8

    form = sources['app/templates/access/identity_providers/form.html']
    # Test Connection now renders via the canonical toast stack in layouts/app.html.
    assert 'components/operational_callout.html' not in form
    assert 'test_result' not in form
    assert 'identity_provider_form.js' in form
    layout = read('app/templates/layouts/app.html')
    assert 'id="operational-toast-stack"' in layout
    assert 'components/operational_toast.html' in layout

    sso = sources['app/templates/access/identity_providers/partials/_sso_configuration.html']
    assert 'components/operational_callout.html' in sso
    assert "operational_callout.semantic_surface_classes('info')" in sso
    assert 'border-status-info-border' not in sso
    assert 'data-jit-off-note' in sso
    assert 'data-jit-settings' in sso

    selector = sources['app/templates/access/identity_providers/partials/_provider_selector.html']
    for hook in (
        'data-provider-option',
        'data-adapter-key',
        'data-configuration-profile',
        'data-admission-policy',
    ):
        assert hook in selector


def test_uat_review2_idp_guidance_preserves_provider_authority_with_concise_copy() -> None:
    from jinja2 import Environment

    google = read('app/templates/access/identity_providers/providers/google/_guidance.html')
    guidance = read('app/templates/access/identity_providers/partials/_provider_guidance.html')
    overview = read('app/templates/access/identity_providers/partials/_overview.html')

    for source in (google, guidance, overview):
        Environment().parse(source)

    assert "note='Google signs in; KAORI governs access.'" in google
    assert 'Google authenticates identity; KAORI retains local authorization' not in google
    assert 'Register this exact URL with the provider.' in guidance
    assert 'Register this exact scheme, host, path, and provider instance key' not in guidance
    assert 'data-browser-callback' in guidance
    assert 'data-callback-key' in guidance
    assert 'request.url_root.rstrip' in guidance
    assert "'Provider & Adapter', 'Distinct Contracts'," in overview
    assert "'Providers own identity; adapters run sign-in.'" in overview
    for source in (google, guidance):
        assert 'whitespace-nowrap' not in source
        assert 'truncate' not in source


def test_uat_review2_ldap_provider_choice_exposes_native_radio_and_visible_selected_feedback() -> None:
    from jinja2 import Environment

    selector = read('app/templates/access/identity_providers/partials/_provider_selector.html')
    provider_js = read('app/static/js/identity_provider_form.js')
    forms = read('app/access/identity_providers/forms.py')
    catalog = read('app/access/authentication/identity_provider/catalog.py')
    definitions = read('app/definitions/catalogs/access/authentication/identity_provider/providers.yaml')

    Environment().parse(selector)
    assert 'type="radio"' in selector
    assert 'class="peer absolute inset-0 z-10 h-full w-full cursor-pointer opacity-0"' in selector
    assert 'class="peer sr-only"' not in selector
    assert 'peer-checked:border-kaori-primary' in selector
    assert 'peer-focus-visible:ring-2' in selector
    assert 'id="provider-key-{{ definition.provider_key }}"' in selector
    assert 'for="provider-key-{{ definition.provider_key }}"' in selector
    assert 'data-provider-option' in selector
    assert 'data-provider-option-badge' in selector
    assert 'data-provider-option-status' in selector
    assert 'data-provider-option-icon="{{ definition.icon }}"' in selector
    assert 'data-provider-icon="{{ definition.icon }}"' not in selector
    assert 'data-provider-display-icon' in read(
        'app/templates/access/identity_providers/partials/_sso_configuration.html'
    )
    assert 'input[type="radio"][data-provider-option]' in provider_js
    assert 'option?.dataset.providerOptionIcon' in provider_js
    assert '\'[data-configuration-panel="browser_client"] [data-provider-display-icon]\'' in provider_js
    assert "form.querySelector('[data-provider-icon]')" not in provider_js
    assert 'lucide.createIcons()' in provider_js
    assert 'peer-checked:border-kaori-primary/30 peer-checked:text-kaori-primary' not in selector
    assert "status.textContent = selected ? 'Selected' : 'Select'" in provider_js
    assert "input.nextElementSibling?.querySelector('[data-provider-option-badge]')" in provider_js
    assert "input.addEventListener('change', syncProvider)" in provider_js
    assert 'const visible = panel.dataset.configurationPanel === profile' in provider_js
    assert 'setControlsEnabled(panel, visible)' in provider_js
    assert 'configurable_provider_definitions()' in catalog
    assert 'configurable_provider_choices()' in forms
    assert 'provider_key: ldap_directory' in definitions
    assert (
        'configurable: true'
        in definitions.split('provider_key: ldap_directory', 1)[1].split('provider_key: google', 1)[0]
    )
    assert 'configuration_profile: ldap' in definitions
    assert 'validate_tls_mode' in forms
    assert 'Enabled LDAP providers require server, base DN, bind DN, and secret reference.' in forms


def test_review3_provider_header_guides_replace_static_input_helpers() -> None:
    from jinja2 import Environment

    form = read('app/templates/access/identity_providers/form.html')
    ldap = read('app/templates/access/identity_providers/partials/_ldap_configuration.html')
    sso = read('app/templates/access/identity_providers/partials/_sso_configuration.html')

    for template, count in ((form, 1), (ldap, 2), (sso, 2)):
        Environment().parse(template)
        assert template.count('info_tip.render(') == count
        assert template.count("variant='guide'") == count
        assert template.count("placement='right'") == count
        assert 'components/info_tip.html' in template
        assert '{{ helper }}' not in template

    for header in ('Provider Identity and State',):
        assert header in form
    for header in ('LDAP Adapter Connection', 'Directory Identity Mapping'):
        assert header in ldap
    for header in ('Admission and JIT Provisioning', 'data-browser-title'):
        assert header in sso

    assert 'data-enabled-copy' in form
    assert 'form.key.errors' in form and 'form.display_name.errors' in form
    assert 'form.enabled.errors' in form
    assert 'form.tls_mode.errors' in ldap
    assert 'for error in field.errors' in ldap
    assert 'form.client_id.errors' in sso
    assert 'form.client_secret_env.errors' in sso
    assert 'data-admission-help' in sso
    assert 'data-jit-off-note' in sso
    assert 'form.jit_enabled.errors' in sso
    assert 'form.admission_values.errors' in sso
    assert 'KAORI resolves the secret at runtime' in sso
    assert '{query} is escaped before substitution' in ldap
    assert 'plaintext LDAP is blocked' in ldap
    for source in (form, ldap, sso):
        assert 'whitespace-nowrap' not in source


def test_review3_provider_guidance_steps_and_authority_notes() -> None:
    from jinja2 import Environment

    github = read('app/templates/access/identity_providers/providers/github/_guidance.html')
    google = read('app/templates/access/identity_providers/providers/google/_guidance.html')
    ldap = read('app/templates/access/identity_providers/providers/ldap_directory/_guidance.html')
    for source in (github, google, ldap):
        Environment().parse(source)
        assert 'info_flow.render(' in source
        assert "note_icon='shield-check'" in source
        assert 'whitespace-nowrap' not in source

    assert 'Register the exact KAORI callback URL as the authorized OAuth callback' in github
    assert 'authorized Google redirect URI' in google
    assert 'runtime environment reference.' in github
    assert 'runtime environment reference.' in google
    assert 'non-admin KAORI role' in github and 'approved external subjects' in github
    assert 'non-admin KAORI role' in google and 'verified email domains' in google
    assert "note='Directory owns credentials; KAORI governs access.'" in ldap
    assert "note='Google signs in; KAORI governs access.'" in google
    assert "note='GitHub signs in; KAORI governs access.'" in github
    assert 'LDAP' not in github


def test_review4_ldap_mapping_example_placeholders_do_not_become_create_defaults() -> None:
    from jinja2 import Environment

    template = read('app/templates/access/identity_providers/partials/_ldap_configuration.html')
    forms = read('app/access/identity_providers/forms.py')
    Environment().parse(template)
    assert '{% if field == form.user_filter %}sm:col-span-2{% endif %}' not in template
    assert 'class="block min-w-0"' in template
    assert 'User Search Filter' in forms and 'TLS Mode' in forms
    assert 'sm:grid-cols-2' in template
    samples = {
        'username_attribute': 'sAMAccountName',
        'email_attribute': 'mail',
        'display_name_attribute': 'displayName',
        'stable_id_attribute': 'objectGUID',
    }
    for field, example in samples.items():
        declaration = next(line for line in forms.splitlines() if line.strip().startswith(f'{field} = StringField('))
        assert 'default=' not in declaration
        assert f"(form.{field}, '{example}')" in template
        assert f"form.{field}.data = config.get('{field}')" in forms
        assert 'self._require_ldap_attribute(field,' in forms
    assert 'def validate_tls_mode' in forms
    assert "if definition.configuration_profile == 'ldap':" in forms


def test_review4_provider_guidance_title_descriptions_are_compact() -> None:
    from jinja2 import Environment

    captions = (
        ('ldap_directory', 'Directory sign-in; KAORI grants access.'),
        ('github', 'GitHub sign-in; KAORI grants access.'),
        ('google', 'Google sign-in; KAORI grants access.'),
    )
    for provider, caption in captions:
        source = read(f'app/templates/access/identity_providers/providers/{provider}/_guidance.html')
        Environment().parse(source)
        assert source.count(caption) == 1
        assert len(caption) <= 42
        assert 'info_flow.render(' in source
        assert 'whitespace-nowrap' not in source
