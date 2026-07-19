from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DESIGN_SYSTEM = ROOT / "docs" / "design" / "KAORI_DESIGN_SYSTEM.md"
HERO_STANDARD = ROOT / "docs" / "design" / "components" / "HERO.md"


def test_global_design_system_does_not_define_page_specific_references():
    content = DESIGN_SYSTEM.read_text(encoding="utf-8")
    forbidden_headings = (
        "## Login page reference",
        "## Welcome workspace reference",
        "## Kubernetes operations dashboard reference",
        "## Kubernetes topology reference",
        "## Kubernetes node inventory reference",
        "## Kubernetes namespace inventory reference",
        "## Kubernetes workload inventory reference",
    )
    for heading in forbidden_headings:
        assert heading not in content


def test_hero_contract_is_owned_by_component_document():
    global_content = DESIGN_SYSTEM.read_text(encoding="utf-8")
    hero_content = HERO_STANDARD.read_text(encoding="utf-8")

    assert "docs/design/components/HERO.md" in global_content
    assert "Compact outer minimum height: **248 px**" in hero_content
    assert "Desktop outer target/minimum height from `lg`: **280 px**" in hero_content
    assert "Only five hero types are permitted" in hero_content


def test_final_semantic_mapping_is_unambiguous():
    content = DESIGN_SYSTEM.read_text(encoding="utf-8")
    assert "Maintenance, Paused, Silenced | Warning" in content
    assert "Pending, Syncing, Processing | Info" in content
    assert "Maintenance / Paused / Silenced | Violet" not in content
    assert "Pending / Syncing / Processing | Cyan" not in content
