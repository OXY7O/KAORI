from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_sidebar_controller_uses_valid_statement_separators() -> None:
    layout = (ROOT / 'app/templates/layouts/app.html').read_text()

    assert 'this.sidebarExpanded = !this.sidebarExpanded;' in layout
    assert "localStorage.setItem('kaori.sidebarExpanded'" in layout
    assert "document.documentElement.classList.toggle('sidebar-collapsed'" in layout


def test_sidebar_toggle_icons_are_supported_by_bundled_lucide() -> None:
    navbar = (ROOT / 'app/templates/components/navigation/navbar.html').read_text()
    license_text = (ROOT / 'app/static/vendor/lucide/LICENSE.txt').read_text()

    assert 'data-lucide="chevrons-left"' in navbar
    assert 'data-lucide="chevrons-right"' in navbar
    assert 'chevrons-left' in license_text
    assert 'chevrons-right' in license_text
    assert 'panel-left-close' not in navbar
    assert 'panel-left-open' not in navbar


def test_welcome_uses_the_canonical_catalog_components() -> None:
    template = (ROOT / 'app/templates/welcome/index.html').read_text()
    hero = (ROOT / 'app/templates/components/page_hero.html').read_text()

    assert 'page_hero.context_panel_classes()' in template
    assert "components/welcome_capability_group.html" in template
    assert "components/workspace_link_card.html" in template
    assert "components/states/_empty_state.html" in template
    assert "table_label.metadata_label('Available Workspaces', 'layout-grid')" in template
    assert 'placeholder="Search Workspaces"' in template
    assert '{{ current_user.role_display_name }} Access' in template
    assert 'data-workspace-result-count>{{ shortcut_count }} Workspaces</strong>' in template
    assert 'Choose a Workspace' in template
    assert 'No Permitted Workspace Matches This Search' in template
    assert 'Only workspaces permitted for your current role are displayed.' not in template
    assert "macro context_note(" not in hero


def test_welcome_template_has_no_page_local_style_drift() -> None:
    template = (ROOT / 'app/templates/welcome/index.html').read_text()

    assert 'text-[' not in template
    assert 'font-extrabold' not in template
    assert 'rounded-full' not in template
    assert 'hover:-translate-y' not in template
    assert 'shadow-xl' not in template
    assert 'Open The Capability You Need' not in template
    assert 'rounded-lg border border-kaori-primary/15 bg-kaori-soft' not in template


def test_workspace_link_card_owns_destination_card_geometry() -> None:
    component = (ROOT / 'app/templates/components/workspace_link_card.html').read_text()

    assert 'table_label.metadata_label(workspace.scope)' in component
    assert 'data-workspace-card' in component
    assert 'Open Workspace' in component
    assert 'rounded-xl border border-outline-default bg-surface-card' in component
    assert 'hover:shadow-md' in component
    assert 'hover:-translate-y' not in component
    assert 'shadow-xl' not in component
    assert 'rounded-full' not in component


def test_welcome_capability_group_is_a_restrained_landing_pattern() -> None:
    component = (ROOT / 'app/templates/components/welcome_capability_group.html').read_text()

    assert 'bg-kaori-primary-dark' in component
    assert 'data-group-result-count' in component
    assert 'text-lg font-semibold' in component
    assert 'data-lucide="star"' not in component
    assert '-bottom-' not in component
    assert 'shadow-lg' not in component


def test_welcome_search_only_filters_rendered_authorized_cards() -> None:
    script = (ROOT / 'app/static/js/welcome.js').read_text()

    assert "querySelectorAll('[data-workspace-card]')" in script
    assert 'card.hidden = !matches' in script
    assert 'group.hidden = visibleGroupCards.length === 0' in script
    assert 'group.open =' not in script
    assert '`${visibleCardCount} ${noun}`' in script


def test_welcome_catalog_matches_current_primary_navigation_domains() -> None:
    shortcuts = (ROOT / 'app/welcome/shortcuts.py').read_text()

    expected_titles = (
        'Dashboards',
        'K8s Inventory',
        'K8s Analytics',
        'Intelligence',
        'Integrations',
        'K8s Operations',
        'Platform Operations',
        'K8s Governance',
        'Reports',
        'Access',
        'Settings',
    )
    for title in expected_titles:
        assert f"'title': '{title}'" in shortcuts

    assert "'title': 'Kubernetes Cluster'" not in shortcuts
    assert "('jobs.view', 'jobs.executions')" in shortcuts
    assert "('jobs.configure', 'jobs.configuration')" in shortcuts
