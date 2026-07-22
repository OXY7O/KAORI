from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_user_management_matching_count_uses_title_case() -> None:
    content = read("app/templates/users/partials/_content.html")

    assert "{{ pagination.total_items }} Matching Users" in content
    assert "{{ pagination.total_items }} matching users" not in content


def test_user_management_hero_description_matches_kaori_standard() -> None:
    hero = read("app/templates/users/partials/_hero.html")

    expected = (
        "Manage KAORI identities, authentication sources, lifecycle controls, "
        "and role assignments."
    )
    assert expected in hero
    assert "Manage identity records, lifecycle state" not in hero
    assert 'page_hero.description_classes()' in hero
    assert 'max-w-[44rem] text-sm font-normal leading-6 text-brand-foreground-muted' not in hero


def test_user_facing_copy_uses_emergency_access_term() -> None:
    paths = [
        "app/templates/users/partials/_summary_cards.html",
        "app/templates/users/partials/_table.html",
        "app/templates/users/form.html",
        "app/templates/users/providers/form.html",
    ]
    combined = "\n".join(read(path) for path in paths)

    assert "Emergency Access" in combined
    assert "Break-glass" not in combined
    assert "break-glass" not in combined
    assert ">Emergency Access</span>" in read("app/templates/users/partials/_table.html")
