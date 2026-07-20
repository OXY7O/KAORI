from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_shared_information_guide_card_contract() -> None:
    component = read("app/templates/components/information_guide_card.html")

    assert "macro render(title, description, items" in component
    assert "<details" in component
    assert "<summary" in component
    assert "Details" in component
    assert "Collapse" in component
    assert "divide-y divide-outline-subtle" in component
    assert 'data-lucide="{{ item[0] }}"' in component
    assert "{{ item[1] }}" in component
    assert "{{ item[2] }}" in component
    assert "'%02d'|format(loop.index)" not in component
    assert "grid-cols-[24px_minmax(0,1fr)]" not in component


def test_alertmanager_connection_guides_use_information_guide_card() -> None:
    form = read("app/templates/alertmanager/instance_form.html")
    configuration = read("app/templates/alertmanager/partials/_detail_configuration.html")

    for template in (form, configuration):
        assert 'components/information_guide_card.html' in template
        assert "information_guide_card.render(" in template
        assert "'Connection Type Guide'" in template
        assert "'building-2', 'Externally Managed'" in template
        assert "'box', 'Standalone'" in template
        assert "'network', 'Shared Service'" in template
        assert "'target', 'Managed for a Specific Scope'" in template

    assert "information_guide_card.render(\n                        'Connection Identity & Contract'" in form
    assert "'fingerprint', 'Connection Identity'" in form
    assert "'file-check-2', 'Connection Contract'" in form
    assert "'badge-check', 'Capability Contract'" in form
    assert "'link-2', 'Scope Bindings'" in form


def test_ordered_guidance_remains_separate() -> None:
    component = read("app/templates/components/context_guidance_card.html")
    form = read("app/templates/alertmanager/instance_form.html")

    assert "macro render(title, description, items, icon='info', open_by_default=false" in component
    assert "'%02d'|format(loop.index)" in component
    assert "if ordered" not in component
    assert "ordered=false" not in component
    assert "'After Registration'" in form
    assert "'Connection Lifecycle'" in form
    assert "context_guidance_card.render(" in form


def test_information_guide_card_documentation_is_registered() -> None:
    standard = read("docs/design/components/INFORMATION_GUIDE_CARD.md")
    audit = read("docs/design/audits/INFORMATION_GUIDE_CARD_INTEGRATIONS_AUDIT_2026_07.md")
    readme = read("docs/design/README.md")
    design_system = read("docs/design/DESIGN_SYSTEM.md")
    global_design_system = read("docs/design/KAORI_DESIGN_SYSTEM.md")

    assert "non-sequential" in standard.lower()
    assert "Every item must use an icon" in standard
    assert "Connection Type Guide" in audit
    assert "components/INFORMATION_GUIDE_CARD.md" in readme
    assert "components/INFORMATION_GUIDE_CARD.md" in design_system
    assert "components/INFORMATION_GUIDE_CARD.md" in global_design_system
