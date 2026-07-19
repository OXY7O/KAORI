from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_ROOTS = (
    ROOT / "app/templates/integrations",
    ROOT / "app/templates/prometheus",
    ROOT / "app/templates/alertmanager",
)


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_alertmanager_registration_flow_and_primary_labels_are_title_case() -> None:
    form = _read("app/templates/alertmanager/instance_form.html")
    registry = _read("app/templates/integrations/alertmanager/partials/_inventory_card.html")

    assert "Alertmanager Registration Flow" in form
    assert "Alertmanager Scope & Workflow" not in form
    assert ">Instance Name<" in form
    assert ">Connection Type<" in form
    assert ">Search Instance<" in registry


def test_known_sentence_case_semantic_labels_do_not_return() -> None:
    forbidden = (
        ">Instance name<",
        ">Connection type<",
        ">Search instance<",
        ">Configuration flow<",
        ">Operational flow<",
        ">Runtime version<",
        ">Last validated<",
        ">Last observed<",
        ">Scope type<",
        ">Source role<",
        ">Request timeout<",
        ">Recommended action<",
        ">Technical evidence<",
    )

    content = "\n".join(
        path.read_text(encoding="utf-8")
        for root in TEMPLATE_ROOTS
        for path in root.rglob("*.html")
    )
    for label in forbidden:
        assert label not in content


def test_integration_title_case_audit_is_documented() -> None:
    audit = _read("docs/design/audits/INTEGRATIONS_TITLE_CASE_AUDIT_2026_07.md")
    typography = _read("docs/design/components/TYPOGRAPHY.md")

    assert "Alertmanager Registration Flow" in audit
    assert "Integrations Semantic Label Contract" in typography
    assert "Search Instance" in typography
