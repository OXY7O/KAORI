from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERO = ROOT / "app/templates/users/partials/_hero.html"


def _source() -> str:
    return HERO.read_text(encoding="utf-8")


def test_user_management_hero_uses_standard_context_metrics() -> None:
    source = _source()

    assert "page_hero.context_panel_metrics_classes()" in source
    assert "page_hero.context_metric('users-round', 'Accounts', summary.total" in source
    assert "page_hero.context_metric('circle-check', 'Active', summary.active" in source


def test_user_management_hero_keeps_two_white_context_actions_only() -> None:
    source = _source()

    assert source.count("page_hero.context_action_classes()") == 2
    assert "page_hero.primary_action_classes()" not in source
    assert "page_hero.secondary_action_classes()" not in source
    assert "Add User" in source
    assert "Provision LDAP" in source


def test_user_management_hero_removes_verbose_context_copy() -> None:
    source = _source()

    assert "Provision a managed identity" not in source
    assert "Create local accounts, provision directory identities" not in source
    assert "Administrative action" not in source
