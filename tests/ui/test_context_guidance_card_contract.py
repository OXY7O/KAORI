from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_shared_context_guidance_card_contract() -> None:
    component = read("app/templates/components/context_guidance_card.html")

    assert "macro render(title, description, items, icon='info', open_by_default=false" in component
    assert "<details" in component
    assert "<summary" in component
    assert "Details" in component
    assert "Collapse" in component
    assert "'%02d'|format(loop.index)" in component
    assert "grid-cols-[24px_minmax(0,1fr)]" in component
    assert "focus-visible:ring-outline-focus" in component
    assert "{{ item[0] }}" in component
    assert "{{ item[1] }}" in component
    assert "if ordered" not in component


def test_alertmanager_after_registration_uses_shared_component() -> None:
    template = read("app/templates/alertmanager/instance_form.html")

    assert 'components/context_guidance_card.html' in template
    assert "context_guidance_card.render(" in template
    assert "'After Registration'" in template
    assert "'Connection Type Guide'" in template
    assert "information_guide_card.render(" in template
    assert "'Connection Identity & Contract'" in template
    assert "'Connection Lifecycle'" in template
    assert "ordered=true" not in template
    assert "After Registration</h2>" not in template


def test_integration_guidance_migrations_use_shared_component() -> None:
    expected = {
        "app/templates/integrations/kubernetes/detail.html": "'Operational Flow'",
        "app/templates/prometheus/instance_form.html": "'Prometheus Integration Flow'",
        "app/templates/prometheus/instance_detail.html": "'Operational Flow'",
        "app/templates/prometheus/config.html": "'Configuration Flow'",
        "app/templates/alertmanager/partials/_detail_validation_content.html": "'When External Criteria Already Pass'",
    }

    for path, title in expected.items():
        template = read(path)
        assert 'components/context_guidance_card.html' in template, path
        assert "context_guidance_card.render(" in template, path
        assert title in template, path


def test_semantic_and_navigation_boxes_remain_separate() -> None:
    kubernetes = read("app/templates/integrations/kubernetes/detail.html")
    prometheus = read("app/templates/prometheus/instance_detail.html")
    alertmanager = read("app/templates/alertmanager/instance_form.html")

    assert "Authority Boundary" in kubernetes
    assert "Change Impact" in prometheus
    assert "related_page_card.render(" in alertmanager
    assert "info_flow.render(" in alertmanager


def test_context_guidance_card_documentation_is_registered() -> None:
    standard = read("docs/design/components/CONTEXT_GUIDANCE_CARD.md")
    audit = read("docs/design/audits/CONTEXT_GUIDANCE_CARD_INTEGRATIONS_AUDIT_2026_07.md")
    readme = read("docs/design/README.md")
    design_system = read("docs/design/DESIGN_SYSTEM.md")
    global_design_system = read("docs/design/KAORI_DESIGN_SYSTEM.md")

    assert "After Registration" in standard
    assert "two to five" in standard.lower()
    assert "ordered" in standard.lower()
    assert "Context Guidance Card" in audit
    assert "components/CONTEXT_GUIDANCE_CARD.md" in readme
    assert "components/CONTEXT_GUIDANCE_CARD.md" in design_system
    assert "components/CONTEXT_GUIDANCE_CARD.md" in global_design_system
