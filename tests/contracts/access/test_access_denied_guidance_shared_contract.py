"""Access Denied guidance uses the shared Analytics interpretation surface (#2962)."""

from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_403_preserves_server_side_authorization_and_existing_navigation() -> None:
    page = read("app/templates/errors/403.html")
    Environment().parse(page)

    assert "Access Role Unavailable" in page
    assert "Access Denied" in page
    assert "current_user.role_record" in page
    assert "not assigned_role.is_active" in page
    assert "page_hero.shell_classes()" in page
    assert "page_hero.context_panel_classes()" in page
    assert "page_hero.context_metric(" in page
    assert "url_for('welcome.index')" in page
    assert "url_for('settings.account')" in page
    assert "Server-Side Enforcement" in page
    assert "Requested Access" in page


def test_403_uses_one_canonical_analytics_guidance_surface() -> None:
    page = read("app/templates/errors/403.html")
    shared = read("app/templates/analytics/components/_analysis_surfaces.html")
    standard = read("docs/design/components/ANALYTICS_OVERVIEW_GUIDANCE_STANDARD.md")

    Environment().parse(page)
    assert '{% import "analytics/components/_analysis_surfaces.html" as analysis_surface %}' in page
    assert page.count("analysis_surface.guidance_card_classes()") == 1
    assert page.count("analysis_surface.snapshot_header_classes()") == 1
    assert page.count("analysis_surface.interpretation_grid_classes()") == 1
    assert page.count("analysis_surface.interpretation_callout(") == 2
    assert "data-kaori-access-resolution-guidance" in page
    assert 'aria-labelledby="access-guidance-title"' in page
    assert 'id="access-guidance-title"' in page
    assert "Access Resolution Guidance" in page

    assert "'Required Action'" in page
    assert "'Request Access Review'" in page
    assert "'Ask an administrator to review your role and permissions.'" in page
    assert "icon='user-cog'" in page
    assert "role='brand'" in page
    assert "'Security Boundary'" in page
    assert "'Server-Side Authorization'" in page
    assert "'Navigation is guidance; server-side permissions enforce access.'" in page
    assert "icon='shield-check'" in page
    assert "role='insight'" in page

    assert "macro guidance_card_classes" in shared
    assert "macro interpretation_grid_classes" in shared
    assert "macro interpretation_callout" in shared
    assert "lg:grid-cols-2" in shared
    assert "border-outline-subtle" in shared
    assert "bg-surface-card" in shared
    assert "Analytics Guidance Standard" in standard


def test_403_does_not_restore_duplicate_cards_or_client_permission_logic() -> None:
    page = read("app/templates/errors/403.html")
    assert "operational_callout.render(" not in page
    assert "components/operational_callout.html" not in page
    assert "lg:grid-cols-2" not in page  # Shared grid owns responsiveness.
    assert "rounded-xl border border-kaori-primary/20 bg-kaori-soft p-5" not in page
    assert "rounded-xl border border-outline-default bg-surface-card p-5 shadow-sm" not in page
    assert "has_permission(" not in page
    assert "<script" not in page
    assert "form method=" not in page
