from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_shared_related_page_component_contract() -> None:
    source = read("app/templates/components/related_page_card.html")
    assert "macro render(" in source
    assert source.count("<a href=") == 1
    assert "rounded-2xl" in source
    assert "bg-kaori-primary" in source
    assert 'class="mt-6"' in source
    assert 'h-full' not in source
    assert 'mt-auto' not in source


def test_roles_keeps_single_page_permission_catalog_exception() -> None:
    source = read("app/templates/settings/roles/index.html")
    assert 'components/related_page_card.html' in source
    assert "related_page_card.render(" in source
    assert "Open Permission Catalog" in source
    assert "code-backed KAORI contracts" in source


def test_related_page_placement_standard_is_documented() -> None:
    component = read("docs/design/components/RELATED_PAGE_CARD.md")
    audit = read("docs/design/audits/RELATED_PAGE_CARD_PLACEMENT_AUDIT_2026_07.md")
    design_system = read("docs/design/KAORI_DESIGN_SYSTEM.md")
    assert "overview, landing, list, or registry" in component
    assert "Single-Page Exception" in component
    assert "mt-6 intrinsic action spacing" in audit
    assert "Do not place it on overview, landing, list, or registry pages" in design_system
