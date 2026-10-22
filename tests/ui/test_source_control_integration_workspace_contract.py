"""Source Control uses canonical KAORI Integrations UI, not a GitHub clone."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_planned_source_control_reuses_canonical_integration_templates() -> None:
    domain = (ROOT / 'app/templates/integrations/domain.html').read_text()
    workspace = (ROOT / 'app/templates/integrations/partials/_domain_workspace.html').read_text()
    assert 'page_hero.shell_classes()' in domain
    assert 'integration_ui.section_shell_classes()' in domain
    assert 'content_tabs.render_links(' in workspace
    assert 'loading_bar.render(' in workspace
    assert 'registry_ui.filter_form(' in workspace
    assert "domain.key == 'source_control'" in workspace
    assert "workspace_tabs = [workspace_tabs[0]]" in workspace
    assert 'GitHub App onboarding remains planned' in workspace


def test_source_control_route_reuses_existing_shared_domain_renderer() -> None:
    routes = (ROOT / 'app/integrations/routes.py').read_text()
    assert "@integrations_bp.get('/source-control')" in routes
    assert "@permission_required('integrations.manage')" in routes
    assert "return _render_domain_page('source_control')" in routes
