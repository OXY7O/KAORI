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


def test_welcome_hero_and_headings_follow_current_presentation_contract() -> None:
    template = (ROOT / 'app/templates/welcome/index.html').read_text()

    assert 'page_hero.context_panel_classes()' in template
    assert 'bg-white p-4 text-content-primary' not in template
    assert 'Only workspaces permitted for your current role are displayed.' in template
    assert 'Open The Capability You Need' in template
    assert '{{ shortcut_count }} Workspaces Available' in template
    assert '<strong>Open Workspace</strong>' in template
    assert 'No Permitted Workspace Matches This Search' in template
