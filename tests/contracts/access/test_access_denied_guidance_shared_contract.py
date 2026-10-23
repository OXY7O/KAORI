"""KAORI 403 guidance uses the approved reusable operational callout (#2962)."""

from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_403_keeps_server_authorization_context_and_existing_navigation() -> None:
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


def test_access_guidance_uses_reusable_neutral_callouts_with_compact_copy() -> None:
    page = read("app/templates/errors/403.html")
    component = read("app/templates/components/operational_callout.html")
    standard = read("docs/design/components/OPERATIONAL_CALLOUT.md")

    assert '{% import "components/operational_callout.html" as operational_callout %}' in page
    assert page.count("operational_callout.render(") == 2
    assert page.count("variant='neutral'") == 2
    assert page.count("tone='info'") == 2
    assert page.count("extra_classes='h-full'") == 2
    assert "'Access Administrator Action'" in page
    assert "'Ask an administrator to review your role and permissions.'" in page
    assert "'Security Boundary'" in page
    assert "'Navigation is guidance; server-side permissions enforce access.'" in page
    assert "'user-cog'" in page
    assert "'shield-check'" in page
    assert "data-kaori-access-resolution-guidance" in page
    assert 'lg:grid-cols-2' in page
    assert "aria-label=\"Access resolution guidance\"" in page

    assert "macro render(" in component
    assert "border-outline-subtle" in component
    assert "bg-surface-elevated" in component
    assert "focus-visible:ring-outline-focus" in component
    assert "components/operational_callout.html" in standard

    # Do not let bespoke 403 cards or the earlier heavy tinted panel return.
    assert 'rounded-xl border border-kaori-primary/20 bg-kaori-soft p-5' not in page
    assert 'rounded-xl border border-outline-default bg-surface-card p-5 shadow-sm' not in page


def test_403_guidance_does_not_add_permissions_or_client_side_security_logic() -> None:
    page = read("app/templates/errors/403.html")

    # This is a presentation-only change; permissions remain enforced by routes.
    assert "has_permission(" not in page
    assert "<script" not in page
    assert "form method=" not in page
    assert "aria-label=\"Access resolution guidance\"" in page
