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
    assert 'for control in administration_controls' in rows
    assert 'administration_control_count' in overview
    assert 'id="kubernetes-admin-controls-list"' in overview
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
    description = overview.index('Manage Secret Reveal prerequisites and Namespace access policies.', start)
    badge = overview.index('header_badge=controls_badge', description)
    contents = overview.index('id="kubernetes-admin-controls-list"', badge)
    close = overview.index('{% endcall %}', contents)
    assert start < description < badge < contents < close
    assert overview.count("'Managed Administration Controls'") == 2  # Title + aria-label
    assert "body_classes='p-0'" in overview[start:contents]
    assert 'kubernetes-admin-controls-title' not in overview
    assert "'Administration Coverage'," in overview
    assert overview.index("'Administration Coverage',") < start
    assert 'kubernetes-admin-summary-section' in overview
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
    summary = overview.index("'Administration Coverage',")
    operations_intro = overview.index("'Kubernetes Operations',", summary)
    card = overview.index("'Managed Administration Controls',", operations_intro)
    contents = overview.index('id="kubernetes-admin-controls-list"', card)
    assert summary < operations_intro < card < contents
    assert "'Administration Coverage'," in overview
    assert 'kubernetes-admin-controls-heading' in overview
    assert "'Kubernetes Operations'," in overview
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

    # Fleet-wide Overview summary and operational control management are two
    # separate canonical cards. The summary must not regress into a footer.
    assert overview.count('operational_section.render(') == 2
    assert overview.count('section_intro.render(') == 1
    assert 'components/section_intro.html' in overview
    summary = overview.index("'Administration Coverage',")
    summary_metrics = overview.index('id="kubernetes-admin-overview-metric-{{ loop.index }}"')
    operations = overview.index("'Kubernetes Operations',")
    controls = overview.index('id="kubernetes-admin-controls-list"')
    assert summary < summary_metrics < operations < controls
    assert 'id="kubernetes-admin-summary-section"' not in overview
    assert "id='kubernetes-admin-summary-section'" in overview
    assert 'id="kubernetes-admin-overview-status"' in overview
    assert 'header_badge=overview_posture' in overview
    assert 'Counts represent committed KAORI configuration.' in overview
    assert 'id="kubernetes-admin-control-count"' in overview
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
    namespace = (
        ROOT / 'app/templates/platform_operations/kubernetes/secret_reveal/_namespace_policy_section.html'
    ).read_text()
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
    policies = cluster.index(
        'platform_operations/kubernetes/secret_reveal/_namespace_policy_section.html', policy_panel
    )
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
    assert cluster.count('section_intro.render(') == 1
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
        'id="secret-reveal-cluster"',
        'data-kaori-auto-submit',
        'platform_operations.kubernetes.secret_reveal.workspace',
        'platform_operations.kubernetes.secret_reveal.update_readiness',
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
        'empty_state_permission = "clusters.manage"',
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

    # Final lock requires the approved shared intro while rejecting retired cramped grids.
    assert "'section_intro.render('," in verifier
    assert "for retired in ('xl:col-span-7', 'xl:col-span-5')" in verifier
    assert 'operational_section.shell_classes()' in verifier
    assert 'content_tabs.render_controlled_links(' in verifier
    assert 'embedded=true' in verifier
    assert 'secret-reveal-kubernetes-boundary-heading' in verifier
    assert 'Configured prerequisites and policies do not prove live access.' in verifier
    assert 'Reveal execution rechecks Namespace policy, user authorization, session verification' in verifier
    assert "'Step-Up Required'" in verifier
    assert "'Approval by Policy'" in verifier
    assert 'Protected Reveal policy engine boundary missing' in verifier
    assert 'Protected Reveal request guidance must stay neutral and payload-free' in verifier
    assert 'UPPERCASE_UTILITY.search(source)' in verifier
    assert 'uppercase tracking-wide' not in cluster


def test_secret_reveal_controlled_content_tabs_preserve_security_and_scope() -> None:
    workspace = (
        ROOT / 'app/templates/platform_operations/kubernetes/secret_reveal/_cluster_workspace.html'
    ).read_text()
    component = (ROOT / 'app/templates/components/content_tabs.html').read_text()
    page = (ROOT / 'app/templates/platform_operations/kubernetes/index.html').read_text()
    namespace = (
        ROOT / 'app/templates/platform_operations/kubernetes/secret_reveal/_namespace_policy_section.html'
    ).read_text()
    table = (
        ROOT / 'app/templates/platform_operations/kubernetes/secret_reveal/_namespace_policy_table_content.html'
    ).read_text()

    assert 'components/content_tabs.html' in workspace
    assert 'content_tabs.render_controlled_links(' in workspace
    assert "('prerequisites', 'Cluster Prerequisites'" in workspace
    assert "('policies', 'Namespace Policies', 'boxes', none," in workspace
    assert "('policies', 'Namespace Policies', 'boxes', namespace_summary.total" not in workspace
    # Only the tab badge is removed; the unfiltered total stays explicitly scoped in the header.
    assert "table_label.metadata_label(namespace_summary.total ~ ' Total Namespaces', icon='list-filter')" in namespace
    assert 'result_count=namespace_summary.total' not in namespace
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
    assert 'render_controlled_links(' in component
    assert 'data-kaori-tab-fallback="server-navigation"' in component
    assert '@keydown.arrow-right.prevent' in component
    assert '@keydown.home.prevent' in component
    assert 'workspace_tabs.render(' in page  # The outer peer navigation is unchanged.
    assert 'id="secret-reveal-cluster-workspace"' in workspace
    assert 'name="view" value="prerequisites"' in workspace
    assert 'name="view" value="{{ secret_reveal_view }}" :value="activeTab"' in ' '.join(workspace.split())
    assert 'name="view" value="policies"' in namespace
    assert 'name="view" value="policies"' in table
    assert 'hx-swap="outerHTML show:none"' in workspace
    assert 'hx-swap="outerHTML show:none"' in table
    assert 'name="csrf_token"' in workspace
    assert 'name="csrf_token"' in table
    assert 'id="secret-reveal-cluster-loading"' not in workspace
    assert "'secret-reveal-namespace-loading'" in namespace
    assert 'secret-reveal-selected-cluster-posture' in workspace
    assert 'empty_state_permission = "clusters.manage"' in workspace


def test_namespace_policies_use_canonical_table_geometry_and_scoped_loading() -> None:
    cluster = (ROOT / 'app/templates/platform_operations/kubernetes/secret_reveal/_cluster_workspace.html').read_text()
    namespace = (
        ROOT / 'app/templates/platform_operations/kubernetes/secret_reveal/_namespace_policy_section.html'
    ).read_text()
    table = (
        ROOT / 'app/templates/platform_operations/kubernetes/secret_reveal/_namespace_policy_table_content.html'
    ).read_text()

    assert 'id="secret-reveal-cluster-loading"' not in cluster
    assert 'hx-indicator="#secret-reveal-cluster-loading"' not in cluster
    source = namespace.index('id="secret-reveal-live-source"')
    block = namespace.index('id="secret-reveal-namespace-section"')
    header = namespace.index('table_ui.inventory_block_header(', block)
    loader = namespace.index("'secret-reveal-namespace-loading'", header)
    filters = namespace.index('table_ui.filter_bar_classes()', loader)
    content = namespace.index('id="secret-reveal-namespace-table-content"', filters)
    assert source < block < header < loader < filters < content
    assert namespace.count('id="secret-reveal-live-source"') == 1
    assert namespace.count("'secret-reveal-namespace-loading'") >= 1
    for primitive in ('block_classes()', 'inventory_block_header(', 'filter_bar_classes()', 'action_classes()'):
        assert 'table_ui.' + primitive in namespace
    assert "'Loading Namespace Policies'" in namespace
    assert 'registry_ui.clear_filters_action(' in namespace
    assert 'hx-target="#secret-reveal-namespace-table-content"' in namespace
    assert 'hx-target="#secret-reveal-cluster-workspace"' in namespace

    for primitive in (
        'table_classes(',
        'head_classes()',
        'header_cell_classes()',
        'header_cell_classes(action=true)',
        'body_classes()',
        'row_classes()',
        'cell_classes()',
        'cell_classes(action=true)',
        'title_cell(',
        'action_classes()',
        'filter_select_classes()',
    ):
        assert 'table_ui.' + primitive in table
    assert "table_ui.table_classes('w-full table-fixed')" in table
    assert all(f'<col class="w-[{width}%]">' in table for width in (38, 16, 20, 26))
    assert 'min-w-[980px]' not in table
    assert 'overflow-x-auto' in table
    assert 'scope="col"' in table
    assert 'table_ui.title_cell(row.namespace,' in table
    assert ':disabled="current === initial"' in table
    assert ':class="current !== initial' not in table
    assert 'aria-label="Reveal policy for {{ row.namespace }}"' in table
    assert 'hx-disabled-elt="button[type=\'submit\']"' in table
    assert 'name="csrf_token"' in table
    assert 'name="view" value="policies"' in table
    assert 'name="namespace"' in table
    assert 'name="policy"' in table
    assert 'enable_option_blocked' in table
    assert 'pagination_ui.footer_classes()' in table
    assert 'pagination_ui.numeric_pages(' in table


def test_namespace_policy_editor_uses_full_width_companion_row() -> None:
    section = (
        ROOT / 'app/templates/platform_operations/kubernetes/secret_reveal/_namespace_policy_section.html'
    ).read_text()
    table = (
        ROOT / 'app/templates/platform_operations/kubernetes/secret_reveal/_namespace_policy_table_content.html'
    ).read_text()
    shared = (ROOT / 'app/templates/components/table.html').read_text()

    # Action controls remain in regular-height rows. One at a time opens an
    # independent full-width editor, never a growing form inside a table cell.
    assert 'x-data="{ openEditor: null }"' not in table
    assert 'data-detail-group="secret-reveal-policy-{{ selected_cluster.id }}"' in table
    assert 'data-detail-toggle' in table
    assert 'data-detail-static="true"' in table
    assert 'data-open="false"' in table
    assert 'data-kaori-namespace-policy-editor' in table
    assert 'aria-controls="secret-reveal-policy-editor-{{ loop.index }}"' in table
    assert 'aria-expanded="false"' in table
    assert 'data-detail-target="secret-reveal-policy-form-{{ loop.index }}"' in table
    assert 'data-detail-row="secret-reveal-policy-editor-{{ loop.index }}"' in table
    assert 'data-detail-open-label="Edit Policy"' in table
    assert 'data-detail-close-label="Close Editor"' in table
    assert 'class="hidden bg-surface-hover"' in table
    assert 'x-show="openEditor === {{ loop.index }}"' not in table
    assert 'x-cloak' not in table
    assert '<td colspan="4" class="border-t border-outline-subtle px-5 py-4 sm:px-6">' in table
    assert '<details ' not in table
    assert 'Edit Namespace Policy' in table
    assert 'New Reveal Policy' in table
    assert 'for="secret-reveal-policy-{{ loop.index }}"' in table
    assert 'id="secret-reveal-policy-{{ loop.index }}"' in table
    assert 'name="policy"' in table
    assert 'table_ui.filter_select_classes()' in table
    assert ':disabled="current === initial"' in table
    assert 'hx-disabled-elt="button[type=\'submit\']"' in table
    assert 'enable_option_blocked' in table
    assert "selected_cluster_ready or row.live_state != 'available'" in table
    assert 'name="csrf_token"' in table
    assert 'name="namespace"' in table
    assert 'name="view" value="policies"' in table
    assert 'name="page"' in table
    assert 'name="per_page"' in table
    assert 'min-w-[280px]' not in table
    assert 'min-w-[980px]' not in table
    assert table.count('table_ui.action_classes()') >= 3
    assert 'macro action_classes(' in shared
    assert 'header_actions=namespace_policy_header_actions' in section
    assert "table_label.metadata_label(namespace_summary.total ~ ' Total Namespaces', icon='list-filter')" in section
    assert 'id="secret-reveal-live-source"' in section
    assert "'secret-reveal-namespace-loading'" in section
    assert 'hx-target="#secret-reveal-namespace-table-content"' in section


def test_namespace_live_source_refresh_and_clear_filters_have_distinct_owners() -> None:
    section = (
        ROOT / 'app/templates/platform_operations/kubernetes/secret_reveal/_namespace_policy_section.html'
    ).read_text()
    source = section.index('id="secret-reveal-live-source"')
    block = section.index('id="secret-reveal-namespace-section"')
    loading = section.index("'secret-reveal-namespace-loading'", block)
    filters = section.index('table_ui.filter_bar_classes()', loading)
    assert source < block < loading < filters
    assert 'class="mb-4 min-w-0 overflow-hidden rounded-xl border border-outline-subtle bg-surface-card"' in section
    assert 'refresh_namespace=1' in section[source:block]
    assert 'hx-target="#secret-reveal-cluster-workspace"' in section[source:block]
    assert 'table_ui.action_classes()' in section[source:block]
    assert 'refresh_namespace=1' not in section[block:]
    assert 'registry_ui.clear_filters_action(' in section[block:loading]
    assert ':hidden="!query.trim() && policy === \'all\'"' in section
    assert "{% if not namespace_filters.query and namespace_filters.policy == 'all' %}hidden{% endif %}" in section
    assert 'table_ui.inventory_block_header(' in section
    assert 'class="{{ table_ui.loading_bar_classes() }}"' not in section
    assert 'relative h-2 bg-surface-card' not in section
    assert "'Loading Namespace Policies'" in section
    assert section.count("'secret-reveal-namespace-loading'") >= 1


def test_secret_reveal_view_survives_url_loading_saves_and_table_navigation() -> None:
    routes = (ROOT / 'app/platform_operations/kubernetes/secret_reveal/routes.py').read_text()
    administration = (ROOT / 'app/platform_operations/kubernetes/routes.py').read_text()
    namespace = (
        ROOT / 'app/templates/platform_operations/kubernetes/secret_reveal/_namespace_policy_section.html'
    ).read_text()
    table = (
        ROOT / 'app/templates/platform_operations/kubernetes/secret_reveal/_namespace_policy_table_content.html'
    ).read_text()

    assert "'per_page', 'view'" in administration
    assert "'view': 'policies' if request.form.get('view') == 'policies' else 'prerequisites'" in routes
    assert "('cluster_id', 'namespace_q', 'namespace_policy', 'page', 'per_page', 'view')" in routes
    assert "'view': 'policies' if request.args.get('view') == 'policies' else 'prerequisites'" in routes
    assert 'settings_args[key] = value' in routes
    assert "response.headers['HX-Push-Url'] = page_url" in routes
    assert "response.headers['HX-Push-Url'] = url_for(" in routes
    assert "tab='secret-reveal', view='policies'" in namespace
    assert "secret_reveal.workspace', view='policies'" in namespace
    assert "tab='secret-reveal', view='policies'" in table
    assert "secret_reveal.workspace', view='policies'" in table
    for template in (namespace, table):
        assert 'name="view" value="policies"' in template
    assert 'default 5' not in namespace  # pagination source is unchanged.


def test_kubernetes_overview_restores_separate_summary_and_operations_blocks() -> None:
    overview = (ROOT / 'app/templates/platform_operations/kubernetes/_overview_workspace.html').read_text()
    summary = (ROOT / 'app/templates/platform_operations/kubernetes/_summary_oob.html').read_text()

    assert "'Overview'," not in overview
    assert "'Kubernetes Operations'," in overview
    assert overview.index("'Administration Coverage',") < overview.index("'Kubernetes Operations',")
    assert "'Administration Coverage'," in overview
    assert "'Managed Administration Controls'," in overview
    assert overview.index("'Administration Coverage',") < overview.index("'Managed Administration Controls',")
    assert "id='kubernetes-admin-summary-section'" in overview
    assert "id='kubernetes-admin-controls-section'" in overview
    assert overview.count('{% endcall %}') == 2
    assert overview.count('operational_section.render(') == 2
    assert overview.count('section_intro.render(') == 1
    assert 'Kubernetes administration coverage and configured security posture at a glance.' not in overview

    # Keep the source-owned summary metric IDs and status for every mutation.
    assert 'id="kubernetes-admin-overview-metric-{{ loop.index }}"' in overview
    assert 'id="kubernetes-admin-overview-status"' in overview
    for metric in range(1, 5):
        assert f'id="kubernetes-admin-overview-metric-{metric}"' in summary
    assert 'id="kubernetes-admin-overview-status"' in summary
    assert 'id="kubernetes-admin-controls-list"' in summary

    # The summary does not claim live authorization on configured counts.
    assert 'Live access is verified at execution.' in overview
    assert 'selected_cluster.secret_reveal_encryption_verified' not in overview


def test_cluster_prerequisites_use_one_responsive_checklist_surface() -> None:
    workspace = (
        ROOT / 'app/templates/platform_operations/kubernetes/secret_reveal/_cluster_workspace.html'
    ).read_text()
    start = workspace.index('Readiness Controls')
    finish = workspace.index('Kubernetes Boundary', start)
    readiness = workspace[start:finish]

    assert 'sm:grid-cols-2 lg:grid-cols-3' in readiness
    assert 'divide' not in readiness or 'border-outline-subtle' in readiness
    assert readiness.count('rounded-xl border border-outline-subtle bg-surface-card') == 1
    assert 'Read-only prerequisite' in readiness
    assert readiness.count('Operator attestation') == 2
    assert 'Activation Boundary' in readiness
    assert 'Save Readiness' in readiness
    assert 'bg-kaori-soft' in readiness
    assert 'name="encryption_verified"' in readiness
    assert 'name="audit_verified"' in readiness
    assert 'name="csrf_token"' in workspace
    assert 'hx-disabled-elt="button[type=\'submit\']"' in workspace
    assert 'Least-privilege Kubernetes RBAC remains the final authorization boundary' in workspace
    assert 'sm:grid-cols-2 xl:grid-cols-4' in workspace


def test_namespace_policy_table_actions_use_public_shared_macro_signature() -> None:
    """Regression: unsupported size kwarg in table wrapper caused workspace HTTP 500."""
    section = (
        ROOT / 'app/templates/platform_operations/kubernetes/secret_reveal/_namespace_policy_section.html'
    ).read_text()
    shared_table = (ROOT / 'app/templates/components/table.html').read_text()

    # The public table wrapper only supports destructive=..., not size=...
    assert 'macro action_classes(destructive=false)' in shared_table
    assert section.count('table_ui.action_classes()') == 2
    assert 'table_ui.action_classes(size=' not in section
    assert 'registry_ui.clear_filters_action(' in section
    assert 'refresh_namespace=1' in section
    assert 'id="secret-reveal-namespace-section"' in section
    assert 'id="secret-reveal-live-source"' in section


def test_secret_reveal_density_uses_source_truth_and_contextual_actions() -> None:
    cluster = (ROOT / 'app/templates/platform_operations/kubernetes/secret_reveal/_cluster_workspace.html').read_text()
    section = (
        ROOT / 'app/templates/platform_operations/kubernetes/secret_reveal/_namespace_policy_section.html'
    ).read_text()
    table = (
        ROOT / 'app/templates/platform_operations/kubernetes/secret_reveal/_namespace_policy_table_content.html'
    ).read_text()

    # Copy remains concise without weakening the underlying RBAC checks.
    assert 'Kubeconfig available from cluster configuration.' in cluster
    assert 'Avoid Secret list/watch unless explicitly required.' in cluster
    assert 'Primary cluster kubeconfig availability, managed from cluster configuration.' not in cluster
    assert 'Avoid broad Secret discovery unless another feature requires it.' not in cluster

    # Live-source provenance is a full-width self-contained utility block.
    assert 'Live Namespace Source' in section
    assert 'Kubernetes reports Namespace presence; KAORI governs reveal policies.' in section
    assert 'Selected cluster: {{ selected_cluster.name }}' in section
    assert 'namespace_source.has_successful_snapshot' in section
    assert section.index('id="secret-reveal-live-source"') < section.index('id="secret-reveal-namespace-section"')
    assert 'hx-target="#secret-reveal-cluster-workspace"' in section
    assert 'refresh_namespace=1' in section
    assert 'namespace_pagination.per_page, refresh_namespace=1)' in section
    assert section.count("'secret-reveal-namespace-loading'") >= 1
    assert 'table_ui.inventory_block_header(' in section
    assert 'class="{{ table_ui.loading_bar_classes() }}"' not in section
    assert 'relative h-2 bg-surface-card' not in section

    # Clear Filters uses the existing KAORI action owner and appears only
    # when either search or policy filter is actually active.
    assert 'registry_ui.clear_filters_action(' in section
    assert "(namespace_filters.query or '') | tojson" in section
    assert "(namespace_filters.policy or 'all') | tojson" in section
    assert 'x-model="query"' in section
    assert 'x-model="policy"' in section
    assert ':hidden="!query.trim() && policy === \'all\'"' in section
    assert "{% if not namespace_filters.query and namespace_filters.policy == 'all' %}hidden{% endif %}" in section
    assert 'hx-target="#secret-reveal-namespace-table-content"' in section

    # Every live/policy state has source-grounded supporting context.
    assert 'Observed in Kubernetes' in table
    assert 'Not found in cluster' in table
    assert 'Live presence unverified' in table
    assert 'Reveal access disabled' in table
    assert 'Approval required' in table
    assert 'Step-up check required' in table

    # Editor keeps row identity, current→new semantics and security boundary
    # in one responsive band, not another nested or mostly empty card.
    assert 'lg:grid-cols-12 lg:gap-6' in table
    assert 'Current policy:' in table
    assert 'This change applies only to the selected Namespace.' in table
    assert 'Available choices depend on cluster readiness and live Namespace state.' in table
    assert 'cancel_workspace_url' in table
    assert 'hx-target="#secret-reveal-namespace-table-content"' in table
    assert 'name="csrf_token"' in table
    assert 'enable_option_blocked' in table
    assert ':disabled="current === initial"' in table
    assert 'pagination_ui.numeric_pages(' in table


def test_namespace_policy_row_toggle_uses_existing_detail_controller_and_loading_component() -> None:
    table = (
        ROOT / 'app/templates/platform_operations/kubernetes/secret_reveal/_namespace_policy_table_content.html'
    ).read_text()
    section = (
        ROOT / 'app/templates/platform_operations/kubernetes/secret_reveal/_namespace_policy_section.html'
    ).read_text()
    shared = (ROOT / 'app/templates/components/table.html').read_text()
    loading = (ROOT / 'app/templates/components/loading_bar.html').read_text()
    detail_js = (ROOT / 'app/static/js/detail_rows.js').read_text()

    # Server-rendered collapsed state must never depend on Alpine initialization
    # of an HTMX-replaced <tbody>. Shared detail_rows.js enforces single-open group.
    assert 'data-detail-toggle' in table
    assert 'data-detail-row="secret-reveal-policy-editor-{{ loop.index }}"' in table
    assert 'data-detail-target="secret-reveal-policy-form-{{ loop.index }}"' in table
    assert 'data-detail-group="secret-reveal-policy-{{ selected_cluster.id }}"' in table
    assert 'data-detail-static="true"' in table
    assert 'data-open="false"' in table
    assert 'class="hidden bg-surface-hover"' in table
    assert 'aria-expanded="false"' in table
    assert 'data-detail-toggle-label' in table
    assert 'data-detail-chevron' in table
    assert 'x-show="openEditor === {{ loop.index }}"' not in table
    assert 'x-data="{ openEditor: null }"' not in table
    assert "const SELECTOR = '[data-detail-toggle]'" in detail_js
    assert 'closeGroup(button.dataset.detailGroup' in detail_js
    assert "row.classList.remove('hidden')" in detail_js
    assert "row.classList.add('hidden')" in detail_js
    assert "target.dataset.detailStatic === 'true'" in detail_js

    # Use the complete approved table header + loading-bar contract rather
    # than a free-floating indicator leaving a permanent empty line.
    assert 'table_ui.inventory_block_header(' in section
    assert "'secret-reveal-namespace-loading'" in section
    assert "'Loading Namespace Policies'" in section
    assert 'loading_bar.render(loading_id, label=loading_label)' in shared
    assert 'htmx-indicator' in loading
    assert 'kaori-loading-bar-segment' in loading
    assert 'class="{{ table_ui.loading_bar_classes() }}"' not in section
    assert 'relative h-2 bg-surface-card' not in section

    # Cancel is safe and restores the read-only table by GET without mutation.
    assert 'cancel_workspace_url' in table
    assert 'hx-get="{{ cancel_workspace_url }}"' in table
    assert 'hx-target="#secret-reveal-namespace-table-content"' in table
    assert 'hx-select="#secret-reveal-namespace-table-content"' in table
    assert 'hx-swap="innerHTML"' in table
    assert 'name="csrf_token"' in table
    assert 'enable_option_blocked' in table
    assert 'hx-post=' in table


def test_kubernetes_posture_cards_share_operational_section_hierarchy() -> None:
    overview = (ROOT / 'app/templates/platform_operations/kubernetes/_overview_workspace.html').read_text()
    config = (ROOT / 'app/templates/platform_operations/kubernetes/_secret_reveal_workspace.html').read_text()
    cluster = (ROOT / 'app/templates/platform_operations/kubernetes/secret_reveal/_cluster_workspace.html').read_text()
    shared = (ROOT / 'app/templates/components/operational_section_card.html').read_text()

    # Overview and Secret Reveal must render through the same approved shell;
    # do not reintroduce a hand-built header and custom metric typography.
    assert overview.count('operational_section.render(') == 2
    assert config.count('operational_section.render(') == 1
    assert 'components/operational_section_card.html' in overview
    assert 'components/operational_section_card.html' in config
    assert "'Administration Coverage'," in overview
    assert "'Secret Reveal Configuration'," in config
    assert 'header_badge=overview_posture' in overview
    assert 'header_badge=global_gate_badge' in config
    assert "body_classes='p-0'" in config
    assert "id='secret-reveal-configuration-section'" in config
    assert 'macro render(' in shared
    assert 'header_badge' in shared

    # Metric label, value, responsive columns and evidence footer must have
    # exactly the same layout classes; status semantics remain domain-owned.
    layout_fragments = (
        'grid min-w-0 gap-px bg-outline-subtle sm:grid-cols-2 xl:grid-cols-4',
        'min-w-0 bg-surface-card px-5 py-4 sm:px-6',
        'flex min-w-0 items-center gap-2 text-xs font-semibold leading-5 text-content-secondary',
        'mt-2 text-2xl font-semibold tracking-tight',
        'mt-1 text-xs leading-5 text-content-muted',
        'border-t border-outline-subtle bg-surface-hover px-5 py-3 text-xs leading-5',
    )
    for fragment in layout_fragments:
        assert fragment in overview
        assert fragment in config
    assert config.count('min-w-0 bg-surface-card px-5 py-4 sm:px-6') == 4
    assert '<dl class="grid' in config
    assert 'Global Gate Enabled' in config and 'Global Gate Disabled' in config
    assert 'text-status-normal-text' in config and 'text-status-warning-text' in config
    assert 'Deployment-managed. Read-only here.' in config
    assert 'Configured prerequisites and policies do not prove live access.' in config
    assert 'Counts represent committed KAORI configuration.' in overview

    # HTMX still updates the actual four summary metrics. The fourth target is
    # now the entire metric cell, including its status and cluster caption.
    for key in (
        'secret-reveal-protected-cluster-count',
        'secret-reveal-enabled-namespace-count',
        'secret-reveal-selected-cluster-posture',
        'secret-reveal-selected-cluster-summary',
    ):
        assert f'id="{key}"' in config
        assert f'id="{key}"' in cluster
    posture = cluster.split('id="secret-reveal-selected-cluster-posture"', 1)[1].split('{% endif %}', 1)[0]
    assert 'hx-swap-oob="outerHTML"' in posture
    assert 'min-w-0 bg-surface-card px-5 py-4 sm:px-6' in posture
    assert 'Selected Cluster Readiness' in posture
    assert 'secret-reveal-selected-cluster-summary' in posture
    assert 'mt-2 text-2xl font-semibold tracking-tight' in posture
    assert 'hx-swap-oob="innerHTML"' in cluster
    assert 'Global Reveal Remains Disabled' in config
    assert 'platform_operations/kubernetes/secret_reveal/_cluster_workspace.html' in config


def test_namespace_numeric_pagination_uses_canonical_htmx_and_url_context() -> None:
    """Numbered pages must match working Previous/Next controls."""
    table = (
        ROOT / 'app/templates/platform_operations/kubernetes/secret_reveal/_namespace_policy_table_content.html'
    ).read_text()
    macro = (ROOT / 'app/templates/components/pagination.html').read_text()
    workspace = (ROOT / 'app/platform_operations/kubernetes/secret_reveal/routes.py').read_text()

    assert table.count('pagination_ui.numeric_pages(') == 1
    assert 'pagination_ui.numeric_pages(namespace_pagination.page, namespace_pagination.total_pages)' not in table
    assert "endpoint='platform_operations.kubernetes.secret_reveal.workspace'" in table
    assert "href_endpoint='platform_operations.kubernetes.index'" in table
    assert 'query_params=namespace_page_query' in table
    assert "hx_target='#secret-reveal-namespace-table-content'" in table
    assert "hx_indicator='#secret-reveal-namespace-loading'" in table
    assert "hx_swap='innerHTML'" in table
    assert '<span hx-select="#secret-reveal-namespace-table-content"' in table
    assert 'hx-push-url="true"' in table
    for param in ('tab', 'view', 'cluster_id', 'namespace_q', 'namespace_policy', 'per_page'):
        assert f"'{param}':" in table
    assert "'tab': 'secret-reveal'" in table
    assert "'view': 'policies'" in table

    # The existing shared macro emits live links when given a target, while
    # the same partial selector/history pattern is already used by prev/next.
    assert 'hx_target=None' in macro
    assert 'hx-get="{{ page_hx_url }}"' in macro
    assert 'hx-target="{{ hx_target }}"' in macro
    assert 'hx-swap="{{ hx_swap }}"' in macro
    assert 'hx-select="#secret-reveal-namespace-table-content"' in table
    assert "response.headers['HX-Push-Url']" in workspace
    assert 'hx-select="#secret-reveal-namespace-table-content"' in table
    assert 'namespace_pagination.prev_page' in table
    assert 'namespace_pagination.next_page' in table


def test_shared_numeric_page_links_render_valid_routes_and_filters() -> None:
    """Render the canonical macro to guard real generated links, not just source markers."""
    from html.parser import HTMLParser
    from types import SimpleNamespace
    from urllib.parse import parse_qs, urlencode, urlsplit

    from jinja2 import Environment, FileSystemLoader

    class Links(HTMLParser):
        def __init__(self) -> None:
            super().__init__()
            self.items: list[dict[str, str | None]] = []

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            if tag == 'a':
                self.items.append(dict(attrs))

    templates = ROOT / 'app/templates'
    env = Environment(loader=FileSystemLoader(str(templates)), autoescape=True)
    env.globals['request'] = SimpleNamespace(endpoint='wrong.current.endpoint', view_args={}, args={})
    env.globals['url_for'] = lambda endpoint, **params: '/' + endpoint + '?' + urlencode(params)

    params = {
        'tab': 'secret-reveal',
        'view': 'policies',
        'cluster_id': 'cluster-123',
        'namespace_q': 'kaori',
        'namespace_policy': 'disabled',
        'per_page': 5,
    }
    rendered = env.get_template('components/pagination.html').module.numeric_pages(
        2,
        5,
        endpoint='platform_operations.kubernetes.secret_reveal.workspace',
        href_endpoint='platform_operations.kubernetes.index',
        query_params=params,
        hx_target='#secret-reveal-namespace-table-content',
        hx_indicator='#secret-reveal-namespace-loading',
        hx_swap='innerHTML',
    )
    parser = Links()
    parser.feed(str(rendered))
    assert len(parser.items) >= 3
    assert all('hx-get' in item for item in parser.items)
    assert all(item.get('hx-target') == '#secret-reveal-namespace-table-content' for item in parser.items)
    assert all(item.get('hx-indicator') == '#secret-reveal-namespace-loading' for item in parser.items)
    assert all(item.get('hx-swap') == 'innerHTML' for item in parser.items)
    for item in parser.items:
        page = urlsplit(item['href'] or '')
        partial = urlsplit(item['hx-get'] or '')
        assert page.path == '/platform_operations.kubernetes.index'
        assert partial.path == '/platform_operations.kubernetes.secret_reveal.workspace'
        href_args = parse_qs(page.query)
        hx_args = parse_qs(partial.query)
        assert href_args == hx_args
        for key, value in params.items():
            assert href_args[key] == [str(value)]
        assert int(href_args['page'][0]) in {1, 3, 4, 5}


def test_numeric_pagination_renderer_keeps_canonical_link_source_on_repeated_htmx_events() -> None:
    """Regression for inert 1–5 links after htmx:afterSwap + htmx:afterSettle."""
    script = (ROOT / 'app/static/js/pagination.js').read_text()
    browser_test = (ROOT / 'tests/ui/test_browser_smoke.py').read_text()
    macro = (ROOT / 'app/templates/components/pagination.html').read_text()
    layout = (ROOT / 'app/templates/layouts/app.html').read_text()

    # The original link must survive replacement of all generated children:
    # both lifecycle events subsequently redraw the numeric pagination.
    assert 'const sourceLinks = new WeakMap()' in script
    assert 'sourceLinks.set(container, original)' in script
    assert 'return sourceLinks.get(container) || null' in script
    assert 'a[hx-get]:not([data-kaori-generated-page])' in script
    assert "link.setAttribute('hx-get', replacePage(hxGet, page, pageParam))" in script
    assert "'hx-select'," in script
    assert "'hx-push-url'," in script
    assert "document.addEventListener('htmx:afterSwap', renderAfterHtmxSwap)" in script
    assert "document.addEventListener('htmx:afterSettle', renderAfterHtmxSwap)" in script
    assert 'window.htmx.process(root)' in script
    assert 'data-kaori-generated-page' in script
    assert 'data-kaori-numeric-pagination' in macro
    assert "filename='js/pagination.js'" in layout

    # Browser regression exercises two renders, a real click, and a new
    # server pagination window; not just static href attributes.
    assert 'test_numeric_pagination_survives_repeated_htmx_renders' in browser_test
    assert 'window.paginationTestClick' in browser_test
    assert 'htmx:afterSwap' in browser_test
    assert 'htmx:afterSettle' in browser_test


def test_cluster_access_has_external_section_intro_inside_htmx_swap_root() -> None:
    """The plain shared heading stays outside the card across lazy/HTMX reloads."""
    cluster = (ROOT / 'app/templates/platform_operations/kubernetes/secret_reveal/_cluster_workspace.html').read_text()
    overview = (ROOT / 'app/templates/platform_operations/kubernetes/_overview_workspace.html').read_text()
    intro_component = (ROOT / 'app/templates/components/section_intro.html').read_text()

    assert 'components/section_intro.html' in cluster
    assert 'components/section_intro.html' in overview
    assert cluster.count('section_intro.render(') == 1
    assert "'Cluster Access'," in cluster
    assert "        'Manage readiness and protected Namespace policies for the selected cluster.'," in cluster
    assert "'secret-reveal-cluster-access-intro-heading'" in cluster
    assert 'macro render(title, description, id=None' in intro_component

    # The heading must be outside the existing operational card but inside
    # the one root replaced by GET cluster switch / readiness POST / policy POST.
    root = cluster.index('id="secret-reveal-cluster-workspace"')
    intro = cluster.index('section_intro.render(', root)
    shell = cluster.index('operational_section.shell_classes()', intro)
    card_header = cluster.index('id="secret-reveal-cluster-readiness-heading"', shell)
    selector = cluster.index('id="secret-reveal-cluster"', card_header)
    tabs = cluster.index('content_tabs.render_controlled_links(', selector)
    assert root < intro < shell < card_header < selector < tabs
    assert 'class="min-w-0 space-y-4"' in cluster
    assert 'aria-label="Kubernetes Cluster Access Configuration"' in cluster
    assert 'aria-labelledby="secret-reveal-cluster-readiness-heading"' in cluster
    assert 'hx-target="#secret-reveal-cluster-workspace"' in cluster
    assert 'hx-swap="outerHTML"' in cluster
    assert "activeTab: '{{ secret_reveal_view }}'" in cluster
    assert '@popstate.window=' in cluster

    # No duplicate card or additional HTMX target after introducing the wrapper.
    assert cluster.count('id="secret-reveal-cluster-workspace"') == 1
    assert cluster.count('operational_section.shell_classes()') == 1
    assert cluster.count('id="secret-reveal-cluster-readiness-heading"') == 1
    assert cluster.count('id="secret-reveal-cluster-access-intro-heading"') == 0
    assert cluster.rstrip().endswith('</section>\n</div>')
