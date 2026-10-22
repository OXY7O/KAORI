"""Kubernetes Admin HTMX policy mutations reconcile every Overview metric from server state."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_administration_mutations_refresh_hero_overview_and_posture():
    route = (ROOT / 'app/platform_operations/kubernetes/secret_reveal/routes.py').read_text()
    page = (ROOT / 'app/templates/platform_operations/kubernetes/index.html').read_text()
    overview = (ROOT / 'app/templates/platform_operations/kubernetes/_overview_workspace.html').read_text()
    partial = (ROOT / 'app/templates/platform_operations/kubernetes/_summary_oob.html').read_text()
    assert 'build_kubernetes_administration_summary()' in route
    assert 'workspace_html + summary_html + feedback_html' in route
    for fragment in (
        'kubernetes-admin-hero-registered',
        'kubernetes-admin-hero-configured',
        'kubernetes-admin-hero-protected',
        'kubernetes-admin-context-ready',
        'kubernetes-admin-context-status',
        'kubernetes-admin-overview-status',
        'kubernetes-admin-overview-metric-2',
        'kubernetes-admin-overview-metric-3',
        'kubernetes-admin-overview-metric-4',
        'kubernetes-admin-overview-metric-1',
        'kubernetes-admin-control-count',
        'kubernetes-admin-controls-list',
    ):
        if fragment.startswith('kubernetes-admin-overview-metric-'):
            assert 'id="kubernetes-admin-overview-metric-{{ loop.index }}"' in overview
        else:
            assert 'id="' + fragment + '"' in (page + overview)
        assert 'id="' + fragment + '"' in partial
    assert partial.count('hx-swap-oob="innerHTML"') == 12


def test_admin_overview_tab_navigation_preserves_current_url_parameters():
    page = (ROOT / 'app/templates/platform_operations/kubernetes/_overview_workspace.html').read_text()
    rows = (ROOT / 'app/templates/platform_operations/kubernetes/_administration_control_rows.html').read_text()
    presentation = (ROOT / 'app/platform_operations/kubernetes/presentation.py').read_text()
    assert "setTab('{{ control.workspace_tab }}')" in rows
    assert "'workspace_tab': 'secret-reveal'" in presentation
    assert 'history.replaceState(null' not in page



def test_kubernetes_admin_operational_hierarchy_keeps_authoritative_summary() -> None:
    page = (ROOT / 'app/templates/platform_operations/kubernetes/index.html').read_text()
    overview = (ROOT / 'app/templates/platform_operations/kubernetes/_overview_workspace.html').read_text()
    config = (ROOT / 'app/templates/platform_operations/kubernetes/_secret_reveal_workspace.html').read_text()
    cluster = (ROOT / 'app/templates/platform_operations/kubernetes/secret_reveal/_cluster_workspace.html').read_text()

    assert 'Kubernetes Administration</h1>' in page
    assert 'components/page_hero.html' in page
    assert 'workspace_tabs.render(' in page
    assert 'kubernetes:load-secret-reveal from:window once' in page
    assert 'kubernetes-administration-overview-title' not in page
    assert 'Administration Coverage' in overview
    assert 'Managed Administration Controls' in overview
    assert 'Administration Readiness' not in overview
    assert 'Configuration Checks' not in overview
    assert 'administration_controls' in (ROOT / 'app/platform_operations/kubernetes/presentation.py').read_text()
    assert 'Configure Secret Reveal' in (ROOT / 'app/platform_operations/kubernetes/presentation.py').read_text()
    for obsolete in ('Administration Capability Catalog', 'Recommended Administration Domains', 'Recommended Roadmap'):
        assert obsolete not in overview + page
    rows = (ROOT / 'app/templates/platform_operations/kubernetes/_administration_control_rows.html').read_text()
    assert 'control.status_detail' in rows
    assert 'control.status_tone' in rows
    assert 'control.metrics' in rows
    assert 'Secret Reveal Configuration' in config
    assert 'Deployment-managed. Read-only here.' in config
    assert 'do not prove live access' in config
    for marker in (
        'secret-reveal-protected-cluster-count',
        'secret-reveal-enabled-namespace-count',
        'secret-reveal-selected-cluster-posture',
        'secret-reveal-selected-cluster-summary',
    ):
        assert f'id="{marker}"' in config
        assert f'id="{marker}"' in cluster
    assert 'hx-swap-oob="outerHTML"' in cluster
    assert 'Selected Cluster Readiness' in config
    assert 'Selected Cluster Readiness' in cluster
    assert 'platform_operations/kubernetes/secret_reveal/_cluster_workspace.html' in config


def test_kubernetes_admin_hero_is_one_line_and_tabs_use_integrated_workspace() -> None:
    index = (ROOT / 'app/templates/platform_operations/kubernetes/index.html').read_text()
    summary = (ROOT / 'app/templates/platform_operations/kubernetes/_summary_oob.html').read_text()
    # The existing Hero primitive owns viewport-dependent typography and wrapping;
    # shortened non-phone copy must not be forced into a clipped nowrap rule.
    description = 'Govern Kubernetes access with policy and audit evidence.'
    assert f'{{{{ page_hero.description_classes() }}}}">{description}</p>' in index
    assert len(description) <= 60
    assert 'whitespace-nowrap' not in index

    # KAORI level-3 navigation precedes the Hero (Domain Workspace Navigation).
    # Style 1 remains shared; both panels stay below the Hero and retain ARIA.
    tab_start = index.index('workspace_tabs.render(')
    hero_start = index.index('<section class="{{ page_hero.shell_classes() }}">')
    shell_start = index.index('id="kubernetes-administration-workspace-shell"')
    overview_start = index.index('id="kubernetes-administration-panel-overview"', shell_start)
    secret_start = index.index('id="kubernetes-administration-panel-secret-reveal"', overview_start)
    assert tab_start < hero_start < shell_start < overview_start < secret_start
    assert index.count('workspace_tabs.render(') == 1
    assert 'class="min-w-0"' in index[shell_start:overview_start]
    assert 'framed_workspace_tabs' not in index
    assert 'kubernetes:load-secret-reveal from:window once' in index
    assert 'role="tabpanel"' in index
    assert 'moveTab(' in index

    # Metadata labels must remain byte-identical across initial page and the
    # source-owned HTMX OOB response after changes to readiness or policy.
    for key in ('registered', 'configured', 'protected'):
        marker = f'id="kubernetes-admin-hero-{key}"'
        assert marker in index
        assert marker in summary
    for phrase in (
        "cluster_count ~ (' Registered Cluster' if cluster_count == 1 else ' Registered Clusters')",
        "ready_cluster_count ~ (' Configured Cluster' if ready_cluster_count == 1 else ' Configured Clusters')",
        "enabled_namespace_count ~ (' Protected Namespace' if enabled_namespace_count == 1 else ' Protected Namespaces')",
    ):
        assert phrase in index
        assert phrase in summary

def test_kubernetes_admin_integrated_tabs_have_explicit_panel_labels() -> None:
    page = (ROOT / 'app/templates/platform_operations/kubernetes/index.html').read_text()
    shared = (ROOT / 'app/templates/components/workspace_tabs.html').read_text()

    # Shared tab owner supplies button IDs, ARIA selection, and keyboard behavior.
    # The page connects each rendered panel to that exact tab ID.
    for tab in ('overview', 'secret-reveal'):
        assert f'id="kubernetes-administration-panel-{tab}"' in page
        assert f'aria-labelledby="kubernetes-administration-tab-{tab}"' in page
        assert 'role="tabpanel"' in page
        assert 'id="{{ prefix }}-tab-{{ tab_key }}"' in shared
        assert 'aria-controls="{{ prefix }}-panel-{{ tab_key }}"' in shared

    assert 'workspace_tabs.render(' in page
    assert 'role="tablist"' not in page
    assert 'kubernetes:load-secret-reveal from:window once' in page


def test_administration_control_projection_scales_without_placeholder_roadmap() -> None:
    source = (ROOT / 'app/platform_operations/kubernetes/presentation.py').read_text()
    overview = (ROOT / 'app/templates/platform_operations/kubernetes/_overview_workspace.html').read_text()
    rows = (ROOT / 'app/templates/platform_operations/kubernetes/_administration_control_rows.html').read_text()
    oob = (ROOT / 'app/templates/platform_operations/kubernetes/_summary_oob.html').read_text()

    # Capability-first, only authorized implemented administration controls;
    # their source-owned states are not duplicated by a static Jinja catalog.
    assert "'administration_controls': controls" in source
    assert "'administration_control_count': len(controls)" in source
    assert "'key': 'secret-reveal'" in source
    assert "'status_label': status_label" in source
    assert "'status_tone': status_tone" in source
    assert "'eligible_policy_count'" in source
    assert "for control in administration_controls" in rows
    assert "administration_control_count" in overview
    assert "id=\"kubernetes-admin-controls-list\"" in overview
    assert 'id="kubernetes-admin-controls-list" hx-swap-oob="innerHTML"' in oob
    assert 'platform_operations/kubernetes/_administration_control_rows.html' in overview
    assert 'platform_operations/kubernetes/_administration_control_rows.html' in oob
    for obsolete in ('Recommended Roadmap', 'Configuration Checks', "'1 Managed Control'"):
        assert obsolete not in overview + rows
    assert 'Live access is verified at execution.' in overview


def test_kubernetes_admin_controls_heading_is_inside_shared_card() -> None:
    overview = (ROOT / 'app/templates/platform_operations/kubernetes/_overview_workspace.html').read_text()
    shared = (ROOT / 'app/templates/components/operational_section_card.html').read_text()
    oob = (ROOT / 'app/templates/platform_operations/kubernetes/_summary_oob.html').read_text()

    # The approved section header (title, short copy and dynamic badge) belongs
    # INSIDE the shared Operational Section Card, not above a second shell.
    start = overview.index("'Managed Administration Controls',")
    description = overview.index('Select a capability to configure its prerequisites and namespace access policies.', start)
    badge = overview.index('header_badge=controls_badge', description)
    contents = overview.index('id="kubernetes-admin-controls-list"', badge)
    close = overview.index('{% endcall %}', contents)
    assert start < description < badge < contents < close
    assert overview.count("'Managed Administration Controls'") == 2  # Title + aria-label
    assert "body_classes='p-0'" in overview[start:contents]
    assert 'kubernetes-admin-controls-title' not in overview
    assert 'Administration Coverage</h3>' in overview
    assert 'macro render(' in shared
    assert 'header_badge' in shared
    assert 'id="kubernetes-admin-controls-list" hx-swap-oob="innerHTML"' in oob


def test_kubernetes_admin_navigation_uses_inventory_shell_spacing() -> None:
    index = (ROOT / 'app/templates/platform_operations/kubernetes/index.html').read_text()
    app_shell = (ROOT / 'app/templates/layouts/app.html').read_text()
    tabs = (ROOT / 'app/templates/components/workspace_tabs.html').read_text()

    # Inventory is server-route navigation; Administration is two Alpine
    # panels, but both share Tab Style 1 and the same shell rhythm.
    assert '<div class="mb-4 min-w-0">' in index
    assert '<div class="mb-4 min-w-0"' in app_shell
    assert 'workspace_tabs.render_navigation(' in app_shell
    assert index.count('workspace_tabs.render(') == 1
    assert 'data-kaori-tab-variant="integrated-workspace"' in tabs
    nav = index.index('workspace_tabs.render(')
    hero = index.index('<section class="{{ page_hero.shell_classes() }}">')
    assert nav < hero
    assert 'moveTab(' in index
    assert 'kubernetes:load-secret-reveal from:window once' in index

def test_kubernetes_admin_controls_have_inventory_section_intro_and_operational_rows() -> None:
    overview = (ROOT / 'app/templates/platform_operations/kubernetes/_overview_workspace.html').read_text()
    inventory = (ROOT / 'app/templates/kubernetes/inventory/overview/index.html').read_text()
    rows = (ROOT / 'app/templates/platform_operations/kubernetes/_administration_control_rows.html').read_text()
    oob = (ROOT / 'app/templates/platform_operations/kubernetes/_summary_oob.html').read_text()

    # Reuse the same visible external section-intro hierarchy as Inventory,
    # without relocating the approved shared Operational Section Card header.
    assert 'components/section_intro.html' in inventory
    assert 'components/section_intro.html' in overview
    external_intro = overview.index('section_intro.render(')
    card = overview.index("'Managed Administration Controls',", external_intro)
    contents = overview.index('id="kubernetes-admin-controls-list"', card)
    assert external_intro < card < contents
    assert 'kubernetes-admin-controls-heading' in overview
    assert "'Administration Controls'," in overview
    assert 'kubernetes-admin-controls-section' in overview
    assert 'header_badge=controls_badge' in overview

    # Capability data and HTMX OOB own the rows, not copied/static cards.
    assert 'for control in administration_controls' in rows
    for field in (
        'control.key',
        'control.label',
        'control.description',
        'control.metrics',
        'control.status_label',
        'control.status_tone',
        'control.status_detail',
        'control.evidence_label',
        'control.action_label',
    ):
        assert field in rows
    assert 'components/action_button.html' in rows
    assert "action_button.classes('primary')" in rows
    assert "setTab('{{ control.workspace_tab }}')" in rows
    assert 'Configuration Evidence' in rows
    assert 'Runtime Authorization' in rows
    assert 'id="kubernetes-admin-controls-list" hx-swap-oob="innerHTML"' in oob
    assert 'platform_operations/kubernetes/_administration_control_rows.html' in oob


def test_managed_controls_are_a_compact_operator_brief() -> None:
    rows = (ROOT / 'app/templates/platform_operations/kubernetes/_administration_control_rows.html').read_text()
    overview = (ROOT / 'app/templates/platform_operations/kubernetes/_overview_workspace.html').read_text()
    oob = (ROOT / 'app/templates/platform_operations/kubernetes/_summary_oob.html').read_text()

    action = rows.index('control.action_label')
    evidence = rows.index('Configuration Evidence')
    metrics = rows.index('for icon, label, value in control.metrics')
    runtime = rows.index('Runtime Authorization')
    detail = rows.index('control.status_detail')
    assert action < evidence < metrics < runtime < detail
    assert 'sm:grid-cols-2' in rows
    assert "table_label.metadata_label('Committed KAORI State'" in rows
    assert "table_label.status_label('Checked at Execution', 'warning')" in rows
    assert rows.count('control.status_detail') == 1
    assert rows.count('control.evidence_label') == 1
    assert 'Control Readiness Path' not in rows
    assert '<ol ' not in rows
    assert 'Managed Control {{ loop.index }}' not in rows
    assert "action_button.classes('primary')" in rows
    assert "setTab('{{ control.workspace_tab }}')" in rows
    assert 'No Administrative Control Available' in rows

    # A single shared card contains control management and the fleet coverage
    # read model, instead of two independent nested metric decks.
    assert overview.count('operational_section.render(') == 1
    assert 'components/section_intro.html' in overview
    assert 'id="kubernetes-admin-controls-list"' in overview
    assert 'Administration Coverage</h3>' in overview
    assert overview.index('id="kubernetes-admin-controls-list"') < overview.index('Administration Coverage</h3>')
    assert 'id="kubernetes-admin-overview-status"' in overview
    assert 'id="kubernetes-admin-overview-metric-{{ loop.index }}"' in overview
    assert 'id="kubernetes-admin-controls-list" hx-swap-oob="innerHTML"' in oob


def test_managed_control_metrics_do_not_claim_live_authorization() -> None:
    rows = (ROOT / 'app/templates/platform_operations/kubernetes/_administration_control_rows.html').read_text()
    presentation = (ROOT / 'app/platform_operations/kubernetes/presentation.py').read_text()
    assert '{{ value }}' in rows
    assert '{{ control.status_detail }}' in rows
    assert '{{ control.evidence_label }}' in rows
    assert 'Runtime Authorization' in rows
    assert 'Checked at Execution' in rows
    assert 'Verification Required' in presentation
    assert "'status_tone': status_tone" in presentation
    assert 'Live Namespace presence, Kubernetes RBAC, and Secret identity' in presentation


def test_secret_reveal_workspace_uses_integrated_header_tabs_and_panels() -> None:
    cluster = (ROOT / 'app/templates/platform_operations/kubernetes/secret_reveal/_cluster_workspace.html').read_text()
    namespace = (ROOT / 'app/templates/platform_operations/kubernetes/secret_reveal/_namespace_policy_section.html').read_text()
    shared_tabs = (ROOT / 'app/templates/components/content_tabs.html').read_text()

    # Match the canonical Integration domain hierarchy: one enclosing shell,
    # one workspace header, embedded shared tab strip, one panel at a time.
    shell = cluster.index('id="secret-reveal-cluster-workspace"')
    heading = cluster.index('id="secret-reveal-cluster-readiness-heading"', shell)
    selector = cluster.index('id="secret-reveal-cluster"', heading)
    tabs = cluster.index('content_tabs.render_controlled_links(', selector)
    prereq_panel = cluster.index('id="secret-reveal-management-panel-prerequisites"', tabs)
    readiness = cluster.index('id="secret-reveal-readiness-section"', prereq_panel)
    boundary = cluster.index('secret-reveal-kubernetes-boundary-heading', readiness)
    policy_panel = cluster.index('id="secret-reveal-management-panel-policies"', boundary)
    policies = cluster.index('platform_operations/kubernetes/secret_reveal/_namespace_policy_section.html', policy_panel)
    assert shell < heading < selector < tabs < prereq_panel < readiness < boundary < policy_panel < policies
    assert 'operational_section.shell_classes()' in cluster
    assert 'Cluster Access Configuration' in cluster
    assert 'Secret Reveal Workspace' in cluster
    assert 'embedded=true' in cluster
    assert 'components/content_tabs.html' in cluster
    assert 'components/action_button.html' in cluster
    assert 'data_namespace=' in cluster
    assert 'content_tabs.render_controlled_links(' in cluster
    assert 'role="tabpanel"' in cluster
    assert 'section_intro.render(' not in cluster
    assert 'operational_section.render(' not in cluster
    assert cluster.count('rounded-xl border border-outline-default bg-surface-card px-5 py-4 shadow-sm') == 0
    assert 'secret-reveal-management-panel-prerequisites' in cluster
    assert 'secret-reveal-management-panel-policies' in cluster
    assert 'min-w-0 p-4 sm:p-5' in cluster
    assert 'min-w-0 overflow-hidden rounded-xl border border-outline-subtle' in cluster
    assert 'sm:grid-cols-2 lg:grid-cols-3' in cluster
    assert 'xl:col-span-7' not in cluster
    assert 'xl:col-span-5' not in cluster
    assert 'Read-only prerequisite' in cluster
    assert 'Operator attestation' in cluster
    assert "action_button.classes('primary')" in cluster
    assert 'data-kaori-tab-variant="content-tabs-controlled"' in shared_tabs
    assert 'rounded-xl border border-outline-subtle bg-surface-card' in namespace
    assert 'shadow-sm' not in namespace.split('<section id="secret-reveal-namespace-section"', 1)[1].split('>', 1)[0]


def test_cluster_readiness_preserves_forms_htmx_scope_and_authorization_boundary() -> None:
    cluster = (ROOT / 'app/templates/platform_operations/kubernetes/secret_reveal/_cluster_workspace.html').read_text()
    verifier = (ROOT / 'scripts/verify_platform_operations_final_lock.py').read_text()

    # GET switches the selected cluster; POST only records the two attestations.
    for marker in (
        'id="secret-reveal-cluster-workspace"',
        'id="secret-reveal-cluster-loading"',
        'id="secret-reveal-cluster"',
        'data-kaori-auto-submit',
        "platform_operations.kubernetes.secret_reveal.workspace",
        "platform_operations.kubernetes.secret_reveal.update_readiness",
        'hx-target="#secret-reveal-cluster-workspace"',
        'hx-swap="outerHTML"',
        'hx-swap="outerHTML show:none"',
        'hx-disabled-elt="button[type=\'submit\']"',
        'name="csrf_token"',
        'name="refresh_namespace"',
        'name="namespace_q"',
        'name="namespace_policy"',
        'name="page"',
        'name="per_page"',
        'name="encryption_verified"',
        'name="audit_verified"',
        'for="secret-reveal-encryption-verified"',
        'for="secret-reveal-audit-verified"',
        'selected_cluster_readiness.credential_configured',
        'selected_cluster.secret_reveal_encryption_verified',
        'selected_cluster.secret_reveal_audit_verified',
        'selected_cluster_ready',
        'secret-reveal-selected-cluster-posture',
        'hx-swap-oob="outerHTML"',
        "empty_state_permission = \"clusters.manage\"",
        'components/states/_empty_state.html',
    ):
        assert marker in cluster
    assert cluster.count('method="post"') == 1
    assert cluster.count('method="get"') == 1
    assert 'Save Readiness' in cluster
    assert 'Changes apply to' in cluster
    assert 'Kubernetes RBAC remains the final authorization boundary' in cluster
    assert 'Configured readiness does not establish live Secret access.' in cluster
    for marker in ('Secret Get Only', 'Avoid List and Watch', 'Namespace Scope', 'Credential Scope'):
        assert marker in cluster

    # Existing final-lock verifier must reject the retired squeezed nested cards.
    assert "for retired in ('xl:col-span-7', 'xl:col-span-5')" in verifier
    assert 'operational_section.shell_classes()' in verifier
    assert 'content_tabs.render_controlled_links(' in verifier
    assert 'embedded=true' in verifier
    assert 'secret-reveal-kubernetes-boundary-heading' in verifier


def test_secret_reveal_controlled_content_tabs_preserve_security_and_scope() -> None:
    workspace = (ROOT / 'app/templates/platform_operations/kubernetes/secret_reveal/_cluster_workspace.html').read_text()
    component = (ROOT / 'app/templates/components/content_tabs.html').read_text()
    page = (ROOT / 'app/templates/platform_operations/kubernetes/index.html').read_text()
    namespace = (ROOT / 'app/templates/platform_operations/kubernetes/secret_reveal/_namespace_policy_section.html').read_text()
    table = (ROOT / 'app/templates/platform_operations/kubernetes/secret_reveal/_namespace_policy_table_content.html').read_text()

    assert 'components/content_tabs.html' in workspace
    assert 'content_tabs.render_controlled_links(' in workspace
    assert "('prerequisites', 'Cluster Prerequisites'" in workspace
    assert "('policies', 'Namespace Policies'" in workspace
    assert "request.values.get('view') == 'policies'" in workspace
    assert "view='prerequisites'" in workspace
    assert "view='policies'" in workspace
    assert 'secret-reveal-management-panel-prerequisites' in workspace
    assert 'secret-reveal-management-panel-policies' in workspace
    assert 'aria-labelledby="secret-reveal-management-tab-prerequisites"' in workspace
    assert 'aria-labelledby="secret-reveal-management-tab-policies"' in workspace
    assert ':hidden="activeTab !==' in workspace
    assert '@popstate.window' in workspace
    assert 'window.history.pushState' in workspace
    assert 'role="tabpanel"' in workspace
    assert "render_controlled_links(" in component
    assert 'data-kaori-tab-fallback="server-navigation"' in component
    assert '@keydown.arrow-right.prevent' in component
    assert '@keydown.home.prevent' in component
    assert 'workspace_tabs.render(' in page  # The outer peer navigation is unchanged.
    assert 'id="secret-reveal-cluster-workspace"' in workspace
    assert 'name="view" value="prerequisites"' in workspace
    assert 'name="view" value="{{ secret_reveal_view }}" :value="activeTab"' in workspace
    assert 'name="view" value="policies"' in namespace
    assert 'name="view" value="policies"' in table
    assert 'hx-swap="outerHTML show:none"' in workspace
    assert 'hx-swap="outerHTML show:none"' in table
    assert 'name="csrf_token"' in workspace
    assert 'name="csrf_token"' in table
    assert 'id="secret-reveal-cluster-loading"' in workspace
    assert 'secret-reveal-selected-cluster-posture' in workspace
    assert "empty_state_permission = \"clusters.manage\"" in workspace


def test_secret_reveal_view_survives_url_loading_saves_and_table_navigation() -> None:
    routes = (ROOT / 'app/platform_operations/kubernetes/secret_reveal/routes.py').read_text()
    administration = (ROOT / 'app/platform_operations/kubernetes/routes.py').read_text()
    namespace = (ROOT / 'app/templates/platform_operations/kubernetes/secret_reveal/_namespace_policy_section.html').read_text()
    table = (ROOT / 'app/templates/platform_operations/kubernetes/secret_reveal/_namespace_policy_table_content.html').read_text()

    assert "'per_page', 'view'" in administration
    assert "'view': 'policies' if request.form.get('view') == 'policies' else 'prerequisites'" in routes
    assert "('cluster_id', 'namespace_q', 'namespace_policy', 'page', 'per_page', 'view')" in routes
    assert "'view': 'policies' if request.args.get('view') == 'policies' else 'prerequisites'" in routes
    assert "settings_args[key] = value" in routes
    assert "response.headers['HX-Push-Url'] = page_url" in routes
    assert "response.headers['HX-Push-Url'] = url_for(" in routes
    assert "tab='secret-reveal', view='policies'" in namespace
    assert "secret_reveal.workspace', view='policies'" in namespace
    assert "tab='secret-reveal', view='policies'" in table
    assert "secret_reveal.workspace', view='policies'" in table
    for template in (namespace, table):
        assert 'name="view" value="policies"' in template
    assert 'default 5' not in namespace  # pagination source is unchanged.
