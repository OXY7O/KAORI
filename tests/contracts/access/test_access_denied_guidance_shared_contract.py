"""Access Denied guidance explains a safe reason and administrator escalation (#2962)."""

from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_403_preserves_access_boundary_and_existing_navigation() -> None:
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


def test_403_explains_reason_without_claiming_unknown_permission_details() -> None:
    page = read("app/templates/errors/403.html")

    assert "Why You Can't Access This Page" in page
    assert "'Access Reason'" in page
    assert "'No Active Role' if role_unavailable else 'Permission Not Granted'" in page
    assert "'Your KAORI account has no active role." in page
    assert "'Your current access (' ~ role_label ~ ') does not permit this page or action.'" in page
    assert "KAORI restricts pages and actions using server-side permissions." in page

    # Explain role unavailable separately; don't invent specific RBAC permission codes.
    assert "permission_key" not in page
    assert "permission_name" not in page
    assert "has_permission(" not in page


def test_403_explains_where_and_how_to_request_help() -> None:
    page = read("app/templates/errors/403.html")

    assert "'Who To Contact'" in page
    assert "'KAORI Access Administrator'" in page
    assert "internal IT helpdesk" in page
    assert "Access → Users" in page
    assert "Share your KAORI username, the page URL, and what you need to do." in page
    assert "Never share your password." in page
    assert "View My Account" in page
    assert 'href="{{ url_for(\'settings.account\') }}"' in page
    assert "action_button.classes('secondary')" in page
    assert "Request Access" not in page  # No fake request form or unimplemented action.


def test_guidance_remains_one_shared_analytics_surface() -> None:
    page = read("app/templates/errors/403.html")
    shared = read("app/templates/analytics/components/_analysis_surfaces.html")
    standard = read("docs/design/components/ANALYTICS_OVERVIEW_GUIDANCE_STANDARD.md")

    assert '{% import "analytics/components/_analysis_surfaces.html" as analysis_surface %}' in page
    assert '{% import "components/action_button.html" as action_button %}' in page
    assert page.count("analysis_surface.guidance_card_classes()") == 1
    assert page.count("analysis_surface.snapshot_header_classes()") == 1
    assert page.count("analysis_surface.interpretation_grid_classes()") == 1
    assert page.count("analysis_surface.interpretation_callout(") == 2
    assert page.count("analysis_surface.boundary_zone_classes(") == 1
    assert 'aria-labelledby="access-guidance-title"' in page
    assert 'id="access-guidance-title"' in page
    assert "role='evidence'" in page
    assert "role='brand'" in page
    assert "macro interpretation_callout" in shared
    assert "macro boundary_zone_classes" in shared
    assert "lg:grid-cols-2" in shared
    assert "Cross-domain unified access guidance" in standard

    assert "operational_callout.render(" not in page
    assert "lg:grid-cols-2" not in page  # Shared grid owns responsive columns.
    assert "<script" not in page
    assert "form method=" not in page
