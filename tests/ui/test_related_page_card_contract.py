from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = ROOT / "app" / "templates"


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_shared_related_page_component_contract() -> None:
    source = read("app/templates/components/related_page_card.html")
    assert "macro render(" in source
    assert "Related Workspace" in source
    assert "Exactly one" not in source  # prose belongs in documentation, not runtime UI
    assert source.count("<a href=") == 1
    assert "rounded-2xl" in source
    assert "bg-kaori-primary" in source


def test_roles_uses_related_page_component_for_permission_catalog() -> None:
    source = read("app/templates/settings/roles/index.html")
    assert 'components/related_page_card.html' in source
    assert "related_page_card.render(" in source
    assert "Open Permission Catalog" in source
    assert "code-backed KAORI contracts" in source
    assert '<section class="rounded-2xl border border-brand-outline bg-kaori-primary' not in source


def test_integration_pages_use_canonical_related_workspaces() -> None:
    expectations = {
        "app/templates/integrations/kubernetes.html": (
            "Kubernetes Inventory",
            "url_for('inventory.overview')",
            "Open Kubernetes Inventory",
        ),
        "app/templates/integrations/prometheus.html": (
            "Kubernetes Analytics",
            "url_for('analytics.overview')",
            "Open Kubernetes Analytics",
        ),
        "app/templates/integrations/alertmanager.html": (
            "Alert Intelligence",
            "url_for('intelligence.alert_intelligence')",
            "Open Alert Intelligence",
        ),
    }
    for relative, values in expectations.items():
        source = read(relative)
        assert 'components/related_page_card.html' in source
        assert "related_page_card.render(" in source
        assert "xl:grid-cols-[minmax(0,1fr)_20rem]" in source
        for value in values:
            assert value in source


def test_related_page_standard_is_documented() -> None:
    component = read("docs/design/components/RELATED_PAGE_CARD.md")
    audit = read("docs/design/audits/RELATED_PAGE_CARD_AUDIT_2026_07.md")
    index = read("docs/design/README.md")
    design_system = read("docs/design/KAORI_DESIGN_SYSTEM.md")
    assert "Exactly one action" in component
    assert "Permission Catalog" in component
    assert "Integrations Overview was not given" in audit
    assert "components/RELATED_PAGE_CARD.md" in index
    assert "Related workspace contract" in design_system
