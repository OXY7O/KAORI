from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_user_management_context_copy_uses_title_case() -> None:
    hero = read("app/templates/users/partials/_hero.html")
    summary = read("app/templates/users/partials/_summary_cards.html")

    assert "Managed KAORI Identities" in hero
    assert "Allowed to Authenticate" in hero
    assert "Managed Accounts" in summary
    assert "Managed KAORI identities" not in hero
    assert "Allowed to authenticate" not in hero
    assert "managed accounts" not in summary


def test_add_user_hero_matches_connection_registration_pattern() -> None:
    form = read("app/templates/users/form.html")

    assert "Registration Posture" in form
    assert "Local Identity Before Access" in form
    assert "page_hero.context_header" in form
    assert "page_hero.context_panel_metrics_classes" in form
    assert "page_hero.context_metric('key-round', 'Credential Owner', 'KAORI'" in form
    assert "page_hero.context_metric('shield-check', 'After Save', 'Role Assignment'" in form
    assert "text-sm font-normal leading-6 text-brand-foreground-muted" in form
    assert "Create one Local Database identity" in form
