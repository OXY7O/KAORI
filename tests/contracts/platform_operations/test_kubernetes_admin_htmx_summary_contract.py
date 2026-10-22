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
    ):
        if fragment.startswith('kubernetes-admin-overview-metric-'):
            assert 'id="kubernetes-admin-overview-metric-{{ loop.index }}"' in overview
        else:
            assert 'id="' + fragment + '"' in (page + overview)
        assert 'id="' + fragment + '"' in partial
    assert partial.count('hx-swap-oob="innerHTML"') == 9


def test_admin_overview_tab_navigation_preserves_current_url_parameters():
    page = (ROOT / 'app/templates/platform_operations/kubernetes/_overview_workspace.html').read_text()
    assert "setTab('secret-reveal')" in page
    assert 'history.replaceState(null' not in page



def test_kubernetes_admin_operational_hierarchy_keeps_authoritative_summary() -> None:
    page = (ROOT / 'app/templates/platform_operations/kubernetes/index.html').read_text()
    overview = (ROOT / 'app/templates/platform_operations/kubernetes/_overview_workspace.html').read_text()
    config = (ROOT / 'app/templates/platform_operations/kubernetes/_secret_reveal_workspace.html').read_text()
    cluster = (ROOT / 'app/templates/platform_operations/kubernetes/secret_reveal/_cluster_workspace.html').read_text()

    assert 'Kubernetes Administration</h1>' in page
    assert 'components/page_hero.html' in page
    assert 'framed_workspace_tabs.render(' in page
    assert 'kubernetes:load-secret-reveal from:window once' in page
    assert 'kubernetes-administration-overview-title' not in page
    assert 'Administration Readiness' in overview
    assert 'Configuration Checks' in overview
    assert 'Configure Secret Reveal' in overview
    for obsolete in ('Administration Capability Catalog', 'Recommended Administration Domains', 'Recommended Roadmap'):
        assert obsolete not in overview + page
    assert 'administration_status_detail' in overview
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


def test_kubernetes_admin_hero_is_one_line_and_tabs_use_canonical_workspace_shell() -> None:
    index = (ROOT / 'app/templates/platform_operations/kubernetes/index.html').read_text()
    summary = (ROOT / 'app/templates/platform_operations/kubernetes/_summary_oob.html').read_text()
    jobs = (ROOT / 'app/templates/platform_operations/jobs/index.html').read_text()

    # The existing Hero primitive owns viewport-dependent typography and wrapping;
    # shortened non-phone copy must not be forced into a clipped nowrap rule.
    description = 'Govern Kubernetes access with policy and audit evidence.'
    assert f'{{{{ page_hero.description_classes() }}}}">{description}</p>' in index
    assert len(description) <= 60
    assert 'whitespace-nowrap' not in index

    # Match the reviewed Jobs workspace shell: shared Framed Tabs in a single
    # bordered surface with padded tab panels, not an unframed gray tab slab.
    shell = 'overflow-hidden rounded-2xl border border-outline-default bg-surface-card shadow-sm'
    assert shell in jobs
    assert f'class="{shell}"' in index
    shell_start = index.index('id="kubernetes-administration-workspace-shell"')
    tab_start = index.index('framed_workspace_tabs.render(', shell_start)
    content_start = index.index('class="p-5 lg:p-6"', tab_start)
    overview_start = index.index('id="kubernetes-administration-panel-overview"', content_start)
    secret_start = index.index('id="kubernetes-administration-panel-secret-reveal"', overview_start)
    assert shell_start < tab_start < content_start < overview_start < secret_start
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
