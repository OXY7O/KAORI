from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_workspace_summary_card_component_contract() -> None:
    component = read("app/templates/components/workspace_summary_card.html")

    assert "macro render(title, description, icon='info'" in component
    assert "border-brand-outline bg-kaori-soft" in component
    assert "bg-surface-card text-kaori-primary" in component
    assert "{{ title }}" in component
    assert "{{ description }}" in component
    assert "<a " not in component
    assert "<details" not in component


def test_alertmanager_configuration_uses_peer_violet_summary_cards() -> None:
    template = read("app/templates/alertmanager/partials/_detail_configuration.html")

    assert 'components/workspace_summary_card.html' in template
    assert template.count("workspace_summary_card.render(") == 3
    assert "'Connection Contract'" in template
    assert "'Change Impact'" in template
    assert "'Integration Flow'" in template
    assert 'rounded-xl border border-outline-subtle bg-surface-hover p-4' not in template


def test_configuration_flow_uses_primary_info_flow_standard() -> None:
    template = read("app/templates/alertmanager/partials/_detail_configuration.html")

    assert 'components/info_flow.html' in template
    assert "info_flow.render(" in template
    assert "context_guidance_card.render(" not in template
    assert "page_context_card.render(" not in template
    assert "'Configuration Workspace'" not in template
    assert "'Configuration Flow'" in template
    assert "'Save Changes'" in template
    assert "'Run Full Validation'" in template
    assert "'Refresh Runtime'" in template
    assert "'Review Resolution'" in template
    assert "Saving configuration does not establish readiness" in template
    assert "open_by_default=true" in template


def test_page_context_standard_is_removed() -> None:
    assert not (ROOT / "app/templates/components/page_context_card.html").exists()
    assert not (ROOT / "docs/design/components/PAGE_CONTEXT_CARD.md").exists()

    for path in (
        "docs/design/README.md",
        "docs/design/DESIGN_SYSTEM.md",
        "docs/design/KAORI_DESIGN_SYSTEM.md",
        "docs/design/components/CARD.md",
    ):
        assert "PAGE_CONTEXT_CARD" not in read(path)
        assert "Page Context Card" not in read(path)


def test_documentation_and_audit_match_corrected_contract() -> None:
    info_flow = read("docs/design/components/INFO_FLOW.md")
    context_guidance = read("docs/design/components/CONTEXT_GUIDANCE_CARD.md")
    audit = read("docs/design/audits/ALERTMANAGER_CONFIGURATION_WORKSPACE_AUDIT_2026_07.md")
    alertmanager_readme = read("app/alertmanager/README.md")

    assert "Primary ordered flows use Info Flow even when placed in a sidebar" in info_flow
    assert "A primary ordered flow must use Info Flow" in context_guidance
    assert "Removed Configuration Workspace" in audit
    assert "uses the shared Info Flow component" in alertmanager_readme
