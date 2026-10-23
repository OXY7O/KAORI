"""Access Denied uses one role-aware and actionable KAORI recovery panel (#2962)."""

from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_403_preserves_hero_role_context_and_existing_safe_navigation() -> None:
    page = read("app/templates/errors/403.html")
    Environment().parse(page)

    assert "Access Role Unavailable" in page
    assert "Access Denied" in page
    assert "current_user.role_record" in page
    assert "not assigned_role.is_active" in page
    assert "page_hero.shell_classes()" in page
    assert "page_hero.context_panel_classes()" in page
    assert "page_hero.context_actions_classes(columns=1)" in page
    assert "page_hero.context_metric(" in page
    assert "url_for('welcome.index')" in page
    assert "url_for('settings.account')" in page
    assert "Server-Side Enforcement" in page
    assert "Requested Access" in page


def test_recovery_panel_has_one_shared_surface_and_clear_visual_hierarchy() -> None:
    page = read("app/templates/errors/403.html")
    shared = read("app/templates/analytics/components/_analysis_surfaces.html")
    Environment().parse(page)

    assert '{% import "analytics/components/_analysis_surfaces.html" as analysis_surface %}' in page
    assert page.count("analysis_surface.guidance_card_classes()") == 1
    assert "data-kaori-access-resolution-guidance" in page
    assert 'aria-labelledby="access-resolution-title"' in page
    assert 'id="access-resolution-title"' in page
    assert "lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]" in page
    assert "lg:border-l lg:border-t-0" in page
    assert "bg-surface-hover" in page
    assert "bg-surface-card" in page
    assert "sm:text-2xl" in page
    assert "text-sm leading-6" in page
    assert "analysis_surface.role_icon_classes('brand', size='large')" in page
    assert "analysis_surface.role_icon_classes('insight', size='large')" in page
    assert "macro guidance_card_classes" in shared
    assert "macro role_icon_classes" in shared

    # The previous compact Analytics interpretation table is not an access workflow.
    assert "analysis_surface.interpretation_grid_classes()" not in page
    assert "analysis_surface.interpretation_callout(" not in page
    assert "analysis_surface.snapshot_header_classes()" not in page
    assert "operational_callout.render(" not in page


def test_denial_reason_is_state_aware_without_exposing_policy_internals() -> None:
    page = read("app/templates/errors/403.html")

    assert "'No Active Role' if role_unavailable else 'Permission Required'" in page
    assert "Your account has no active KAORI role." in page
    assert "The permission required for this page or action is not included" in page
    assert 'aria-label="Current KAORI role"' in page
    assert "{{ role_label }}" in page
    assert "permission_key" not in page
    assert "permission_name" not in page
    assert "has_permission(" not in page


def test_contact_and_steps_are_actionable_but_do_not_fabricate_a_support_channel() -> None:
    page = read("app/templates/errors/403.html")

    assert "Contact your access administrator" in page
    assert "KAORI Access Administrator or internal IT helpdesk" in page
    assert "Access → Users" in page
    assert 'aria-label="Access review steps"' in page
    assert "Share your KAORI username, page URL, and required action." in page
    assert "Never share your password." in page
    assert "View My Account" in page
    assert "this does not submit an access request." in page
    assert "action_button.classes('secondary')" in page
    assert 'href="{{ url_for(\'settings.account\') }}"' in page
    assert "Request Access</a>" not in page
    assert "mailto:" not in page
    assert "<script" not in page
    assert "form method=" not in page
