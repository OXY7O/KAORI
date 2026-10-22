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
    start = overview.index("{% call operational_section.render(\\n        'Managed Administration Controls',")
    description = overview.index('Configure implemented controls and review their security posture.', start)
    badge = overview.index('header_badge=controls_badge', description)
    contents = overview.index('id="kubernetes-admin-controls-list"', badge)
    close = overview.index('{% endcall %}', contents)
    assert start < description < badge < contents < close
    assert overview.count("'Managed Administration Controls'") == 2  # Title + aria-label
    assert "body_classes='p-0'" in overview[start:contents]
    assert 'kubernetes-admin-controls-title' not in overview
    assert "{% call operational_section.render(\\n        'Administration Coverage'," in overview
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
