from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_general_hero_uses_compact_context_without_duplicate_actions() -> None:
    hero = read("app/templates/settings/general/partials/_hero.html")
    assert "Current Presentation" in hero
    assert "Account Preference" in hero
    assert "Canonical operational timestamps remain UTC" in hero
    assert "Release Identity" in hero
    assert "Compatibility Policy" in hero
    assert "context_header" in hero
    assert "context_panel_metrics_classes" in hero
    assert "primary_action_classes" not in hero


def test_time_zone_workspace_has_clear_configuration_sequence() -> None:
    template = read("app/templates/settings/general/partials/_time_locale.html")
    for token in (
        "Selection Mode",
        "Browser Detection",
        "Manual Time Zone",
        "Effective Time Zone",
        "Save Time Zone",
        "Personal Preference",
    ):
        assert token in template
    assert "general-current-time" in template
    assert "detect-browser-timezone" in template
    assert "pointer-events-none" in template


def test_regional_format_uses_three_equal_controls_and_one_preview() -> None:
    template = read("app/templates/settings/general/partials/_regional_format.html")
    assert "Regional Locale" in template
    assert "Date Format" in template
    assert "Time Format" in template
    assert "Current Presentation Preview" in template
    assert "Save Regional Format" in template
    assert template.count("rounded-xl border border-outline-default bg-surface-subtle p-4") >= 3


def test_personal_preference_context_explains_scope_and_boundary() -> None:
    template = read("app/templates/settings/general/partials/_impact_information.html")
    assert "Presentation Scope" in template
    assert "Data & Execution Boundary" in template
    assert "Canonical Storage" in template
    assert "Execution Schedules" in template
    assert "External Systems" in template
    assert "Presentation only." in template


def test_system_information_is_explicitly_read_only_and_traceable() -> None:
    main = read("app/templates/settings/general/partials/_system_information.html")
    context = read("app/templates/settings/general/partials/_system_information_context.html")
    assert "Release Identity" in main
    assert "Read-Only Metadata" in main
    assert "Build Reference" in main
    assert "Build Date" in main
    assert "Capability Catalog" in main
    assert "Release Governance" in context
    assert "Information Boundary" in context
    assert "Not Exposed" in context


def test_compatibility_workspace_keeps_version_and_readiness_decisions_separate() -> None:
    main = read("app/templates/settings/general/partials/_compatibility_versions.html")
    context = read("app/templates/settings/general/partials/_compatibility_versions_context.html")
    assert "Integration Compatibility" in main
    assert "Validation Required" in main
    assert "Supported Version Matrix" in main
    assert "Capability Validation Basis" in main
    assert "Reading the Matrix" in context
    assert "Minimum Compatible" in context
    assert "Recommended Baseline" in context
    assert "Live Readiness" in context
