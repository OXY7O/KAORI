from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HERO_COMPONENT = ROOT / "app/templates/components/page_hero.html"
DESIGN_SYSTEM = ROOT / "docs/design/KAORI_DESIGN_SYSTEM.md"


def test_shared_hero_owns_final_geometry_and_typography_contract():
    source = HERO_COMPONENT.read_text(encoding="utf-8")

    assert "min-h-[15.5rem]" in source
    assert "lg:min-h-[17.5rem]" in source
    assert "xl:grid-cols-12" in source
    assert "xl:col-span-7" in source
    assert "xl:col-span-5" in source
    assert "macro title_classes" in source
    assert "text-[30px]" in source
    assert "lg:text-[32px]" in source
    assert "macro description_classes" in source
    assert "text-[15px]" in source
    assert "leading-6" in source


def test_shared_hero_owns_action_treatments():
    source = HERO_COMPONENT.read_text(encoding="utf-8")

    assert "macro primary_action_classes" in source
    assert "bg-white" in source
    assert "text-kaori-primary" in source
    assert "hover:bg-kaori-soft" in source
    assert "macro secondary_action_classes" in source
    assert "macro destructive_action_classes" in source
    assert "bg-critical-soft" in source


def test_design_system_freezes_hero_types_and_behavior():
    source = DESIGN_SYSTEM.read_text(encoding="utf-8")

    for required in (
        "Standard Hero",
        "Dashboard Hero",
        "Workspace Hero",
        "Wizard Hero",
        "Detail Hero",
        "Empty Hero",
        "Busy Hero",
        "Hero stability",
        "Hero content rule",
        "248 px",
        "280 px",
        "two or three metadata labels",
        "white surface",
    ):
        assert required in source

    assert "supersedes the earlier experimental 164–188 px proposal" in source
