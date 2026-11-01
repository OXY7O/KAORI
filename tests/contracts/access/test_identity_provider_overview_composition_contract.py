"""Identity Providers overview and workspace follow the Activity Audit pattern."""

from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_posture_and_governance_form_one_audit_style_overview() -> None:
    overview = read('app/templates/access/identity_providers/partials/_overview.html')
    audit = read('app/templates/access/activity_audit/partials/_activity_summary_cards.html')
    Environment().parse(overview)

    assert 'data-kaori-idp-overview' in overview
    assert 'data-kaori-idp-overview-metrics' in overview
    assert 'data-kaori-idp-governance-boundaries' in overview
    assert 'data-kaori-idp-posture-metric' in overview
    assert 'data-kaori-idp-governance-item' in overview

    for shared_structure in (
        'grid gap-px bg-outline-subtle md:grid-cols-2 xl:grid-cols-4',
        'border-t border-outline-subtle bg-surface-hover px-5 py-4 lg:px-6',
        'grid gap-3 md:grid-cols-2 xl:grid-cols-4',
    ):
        assert shared_structure in audit
        assert shared_structure in overview

    for count in (
        'summary.configured',
        'summary.enabled',
        'summary.directory',
        'summary.sso',
    ):
        assert count in overview
    # The human-approved compact Overview removes its redundant footer entirely.
    assert 'data-kaori-idp-posture-context' not in overview
    assert 'No external provider has been registered.' not in overview
    assert 'Configured means the adapter contract is complete;' not in overview
    assert 'table_label.status_indicator_label(summary.posture_label, summary.posture_tone)' in overview

    for boundary in (
        'Provider & Adapter',
        'Credential Ownership',
        'Identity Projection',
        'Authorization Boundary',
    ):
        assert boundary in overview

    for concise_description in (
        'Provider owns identity; adapter handles sign-in.',
        'External secrets; KAORI stores references.',
        'Linked identities need KAORI authorization.',
        'KAORI roles and account state gate access.',
    ):
        assert concise_description in overview
        assert len(concise_description) <= 48

    assert 'whitespace-nowrap' not in overview
    assert 'text-ellipsis' not in overview

    # Governance must remain within the same overview surface.
    assert 'operational_section.render(' not in overview
    assert '_directory_provisioning_strip.html' not in overview
    assert overview.count('<section ') == 1
    assert overview.count('{% for ') == overview.count('{% endfor %}')


def test_provider_setup_guidance_and_secret_helper_are_concise() -> None:
    runbook = read('app/templates/access/identity_providers/partials/_provider_guidance.html')
    google = read('app/templates/access/identity_providers/providers/google/_guidance.html')
    sso = read('app/templates/access/identity_providers/partials/_sso_configuration.html')

    for template in (runbook, google, sso):
        Environment().parse(template)

    assert 'Provider setup, validation, and controlled enablement.' in runbook
    assert 'Google sign-in; KAORI grants access.' in google
    assert 'Client Secret Environment Variable: enter only its name.' in sso
    assert 'KAORI resolves the secret at runtime and does not persist the value.' in sso
    assert "data_client_secret_input='true'" in sso
    assert 'form.client_secret_env.errors' in sso


def test_index_keeps_overview_above_activity_style_record_tabs() -> None:
    page = read('app/templates/access/identity_providers/index.html')
    workspace = read('app/templates/access/identity_providers/partials/_workspace.html')
    tabs = read('app/templates/access/identity_providers/partials/_tabs.html')
    audit_workspace = read('app/templates/access/activity_audit/partials/_audit_records_workspace.html')

    for template in (page, workspace, tabs):
        Environment().parse(template)

    assert page.index('partials/_overview.html') < page.index('partials/_workspace.html')
    assert 'section_intro.render(' in page
    assert '<section id="identity-provider-workspace"' in workspace
    assert 'table_ui.block_classes()' in workspace
    assert 'data-kaori-idp-records-workspace' in workspace
    assert "active_tab == 'directory'" in workspace
    assert 'partials/_registry.html' in workspace
    assert 'partials/_directory_provisioning_strip.html' in workspace
    assert '{% set embedded = true %}' in workspace

    assert 'framed_tabs.render_navigation(' in tabs
    assert 'framed_tabs.render_navigation(' in audit_workspace
    assert "'Provider Registry'" in tabs
    assert "'Directory Provisioning'" in tabs
    assert "'Overview'" not in tabs
    assert "url_for('identity_providers.index', tab='providers')" in tabs
    assert "url_for('identity_providers.index', tab='directory')" in tabs
    assert "hx_target='#identity-provider-workspace'" in tabs
    assert "hx_select='#identity-provider-workspace'" in tabs


def test_registry_filters_preserved_and_separately_targeted() -> None:
    registry = read('app/templates/access/identity_providers/partials/_registry.html')
    routes = read('app/access/identity_providers/routes.py')
    shared = read('app/templates/components/framed_workspace_tabs.html')
    Environment().parse(registry)
    Environment().parse(shared)

    assert 'embedded|default(false)' in registry
    assert 'id="identity-provider-registry"' in registry
    assert 'registry_ui.filter_form(' in registry
    assert 'registry_ui.clear_filters_link(' in registry
    assert 'registry_ui.footer(' in registry
    assert 'name="tab" value="providers"' in registry
    assert "footer_query.pop('per_page', none)" in registry
    assert 'expandable.static_detail_row(' in registry
    assert "'identity-provider-registry'," in registry
    assert "'identity-provider-registry-loading'," in registry

    assert "payload['active_tab'] = 'directory' if request.args.get('tab') == 'directory' else 'providers'" in routes
    assert "request.headers.get('HX-Target') == 'identity-provider-workspace'" in routes
    assert "request.headers.get('HX-History-Restore-Request') != 'true'" in routes
    assert "render_template('access/identity_providers/partials/_workspace.html'" in routes
    assert "render_template('access/identity_providers/partials/_registry.html'" in routes
    assert "render_template('access/identity_providers/index.html'" in routes
    assert 'hx-select="{{ hx_select }}"' in shared
    assert 'hx-push-url="{{ hx_push_url }}"' in shared


def test_directory_tab_is_read_only_summary_with_scoped_workflow_launch() -> None:
    directory = read('app/templates/access/identity_providers/partials/_directory_provisioning_strip.html')
    Environment().parse(directory)

    assert "current_user.has_permission('identity_providers.provision')" in directory
    assert '{% if can_provision %}' in directory
    assert '{% if not can_provision %}' in directory
    assert "url_for('identity_providers.directory_provisioning')" in directory
    assert 'data-kaori-idp-directory-launch' in directory
    assert 'Open Directory Provisioning' in directory
    assert "table_label.status_indicator_label('Read Only', 'unknown')" in directory
    assert 'data-kaori-idp-directory-flow' in directory
    assert 'summary.directory' in directory
    assert 'summary.directory_identity_links' in directory
    assert 'KAORI Roles' in directory
    assert 'provider-owned' in directory
    assert 'credentials remain external' in directory.lower()
    assert '<form ' not in directory


def test_identity_provider_workspace_guides_own_title_context_only() -> None:
    registry = read('app/templates/access/identity_providers/partials/_registry.html')
    directory = read('app/templates/access/identity_providers/partials/_directory_provisioning_strip.html')

    for template in (registry, directory):
        Environment().parse(template)
        assert '{% import "components/info_tip.html" as info_tip %}' in template
        assert "placement='right'" in template
        assert "variant='guide'" in template

    assert (
        registry.index('>Provider Registry</h2>')
        < registry.index("info_tip.render('identity-provider-registry-guide'")
        < registry.index('table_label.result_count(summary.matching)')
    )
    assert 'registry_ui.clear_filters_link(' in registry
    assert 'registry_ui.footer(' in registry

    assert (
        directory.index('>Directory Provisioning</h2>')
        < directory.index("info_tip.render('identity-provider-directory-provisioning-guide'")
        < directory.index('Review directory projection evidence')
    )
    assert "current_user.has_permission('identity_providers.provision')" in directory
    assert "table_label.status_indicator_label('Read Only', 'unknown')" in directory
    assert 'data-kaori-idp-directory-launch' in directory
