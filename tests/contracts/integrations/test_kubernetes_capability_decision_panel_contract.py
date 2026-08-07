from pathlib import Path

TEMPLATE = Path("app/templates/integrations/kubernetes/partials/_capability_workspace.html")


def _source() -> str:
    return TEMPLATE.read_text(encoding="utf-8")


def test_validation_decision_panel_keeps_desktop_side_rail_layout():
    source = _source()

    assert "data-kaori-capability-side-rail-layout" in source
    assert "lg:grid-cols-[minmax(0,1fr)_22rem]" in source
    assert "xl:grid-cols-[minmax(0,1fr)_24rem]" in source
    assert "2xl:grid-cols-[minmax(0,1fr)_25rem]" in source
    assert 'class="self-start lg:sticky lg:top-4"' in source


def test_validation_decision_panel_uses_compact_connected_layout():
    source = _source()

    assert "data-kaori-capability-decision-panel-v2" in source
    assert "data-kaori-capability-posture-list" in source
    assert "data-kaori-validation-workflow-steps" in source
    assert "data-kaori-capability-posture-grid" not in source
    assert "grid grid-cols-2 gap-2" not in source
    assert "xl:max-h-[calc(100dvh-6rem)]" not in source
    assert "xl:overflow-y-auto" not in source


def test_validation_decision_panel_keeps_readiness_progress_and_semantics():
    source = _source()

    assert 'aria-label="Capability readiness"' in source
    assert "bg-kaori-primary" in source
    assert "Operational Gate" in source
    assert "Next Operational Action" in source
    assert "Interpret → Remediate → Revalidate → Synchronize" in source


def test_validation_decision_panel_preserves_full_workflow_copy_without_truncation():
    source = _source()

    assert 'Interpret → Remediate → Revalidate → Synchronize' in source
    assert 'truncate text-xs text-content-secondary">Interpret → Remediate' not in source
    assert '[overflow-wrap:anywhere]' in source
    assert 'xl:px-5' in source
