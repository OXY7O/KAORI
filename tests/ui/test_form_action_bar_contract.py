from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = ROOT / "app" / "templates"
DOCS = ROOT / "docs" / "design"


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_shared_form_action_bar_contract() -> None:
    component = read("app/templates/components/form_action_bar.html")

    assert "macro render(helper" in component
    assert "max-w-lg text-xs leading-5 text-content-muted" in component
    assert "sm:items-center sm:justify-between" in component
    assert "sm:justify-end" in component
    assert "{{ caller() }}" in component


def test_integration_forms_use_shared_action_bar() -> None:
    paths = [
        "app/templates/cluster/partials/_form.html",
        "app/templates/prometheus/instance_form.html",
        "app/templates/prometheus/config.html",
        "app/templates/alertmanager/instance_form.html",
        "app/templates/alertmanager/partials/_detail_configuration.html",
        "app/templates/alertmanager/config.html",
    ]

    for path in paths:
        template = read(path)
        assert 'components/form_action_bar.html' in template, path
        assert "form_action_bar.render(" in template, path


def test_static_action_helpers_remain_concise() -> None:
    helpers = [
        "Save to start Kubernetes inventory onboarding.",
        "Save changes to update cluster configuration.",
        "Register now; validate from the connection detail.",
        "Save changes, then run Full Validation.",
        "Register after Test Connection succeeds.",
        "Test changes before saving this configuration.",
    ]

    for helper in helpers:
        assert len(helper) <= 72, helper


def test_removed_long_footer_copy_does_not_return() -> None:
    sources = "\n".join(
        read(path)
        for path in [
            "app/templates/cluster/partials/_form.html",
            "app/templates/prometheus/instance_form.html",
            "app/templates/alertmanager/instance_form.html",
            "app/templates/alertmanager/partials/_detail_configuration.html",
        ]
    )

    prohibited = [
        "Changes affect connectivity, inventory collection, and observability mapping for this cluster.",
        "Saving resets readiness to Validation Required. Test Connection and Full Validation are performed from the connection detail page.",
        "Complete the form and run Test Connection. Register Instance becomes available only after the submitted values pass reachability verification.",
        "Run Full Validation before relying on the connection again.",
    ]

    for phrase in prohibited:
        assert phrase not in sources


def test_form_action_bar_documentation_is_registered() -> None:
    component_doc = read("docs/design/components/FORM_ACTION_BAR.md")
    audit_doc = read("docs/design/audits/FORM_ACTION_BAR_INTEGRATIONS_AUDIT_2026_07.md")
    readme = read("docs/design/README.md")
    design_system = read("docs/design/DESIGN_SYSTEM.md")
    global_design_system = read("docs/design/KAORI_DESIGN_SYSTEM.md")

    assert "72 characters" in component_doc
    assert "Register after Test Connection succeeds." in audit_doc
    assert "components/FORM_ACTION_BAR.md" in readme
    assert "components/FORM_ACTION_BAR.md" in design_system
    assert "components/FORM_ACTION_BAR.md" in global_design_system
