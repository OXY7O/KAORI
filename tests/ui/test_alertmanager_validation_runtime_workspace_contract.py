from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_validation_and_runtime_use_shared_peer_summary_cards() -> None:
    validation = read("app/templates/alertmanager/partials/_detail_validation.html")
    runtime = read("app/templates/alertmanager/partials/_detail_runtime.html")

    for source in (validation, runtime):
        assert 'components/workspace_summary_card.html' in source
        assert source.count('workspace_summary_card.render(') == 3
        assert 'rounded-xl border border-outline-subtle bg-surface-hover p-4' not in source

    for fragment in (
        "'What Validation Does'",
        "'Why It Matters'",
        "'Operator Flow'",
    ):
        assert fragment in validation

    for fragment in (
        "'Readiness Versus Health'",
        "'How Monitoring Works'",
        "'Resolver Correlation'",
    ):
        assert fragment in runtime


def test_health_interpretation_shared_component_contract() -> None:
    component = read("app/templates/components/health_interpretation.html")

    for fragment in (
        'macro render(',
        'Health Interpretation',
        'Current Health Score',
        'Readiness Boundary',
        'Contributing Evidence',
        '0–59',
        '60–84',
        '85–100',
        "status_tone == 'critical'",
        "status_tone == 'warning'",
        "status_tone == 'normal'",
        'table_label.status_label',
    ):
        assert fragment in component

    assert '<svg' not in component
    assert 'stroke-dashoffset' not in component
    assert '<details' not in component
    assert '<button' not in component
    assert '<a ' not in component


def test_alertmanager_runtime_uses_shared_health_interpretation() -> None:
    runtime_panel = read("app/templates/alertmanager/partials/_runtime_panel.html")

    assert 'components/health_interpretation.html' in runtime_panel
    assert 'health_interpretation.render(' in runtime_panel
    assert 'runtime_state.health_score' in runtime_panel
    assert 'runtime_state.health_summary' in runtime_panel
    assert 'runtime_state.factors' in runtime_panel
    assert 'readiness_label=runtime_state.readiness_label' in runtime_panel

    for legacy in (
        '<svg',
        'stroke-dashoffset',
        'score_ring_class',
        'relative h-24 w-24',
    ):
        assert legacy not in runtime_panel


def test_validation_runtime_documentation_contract() -> None:
    workspace_summary = read("docs/design/components/WORKSPACE_SUMMARY_CARD.md")
    health = read("docs/design/components/HEALTH_INTERPRETATION.md")
    audit = read("docs/design/audits/ALERTMANAGER_VALIDATION_RUNTIME_WORKSPACE_AUDIT_2026_07.md")
    design_system = read("docs/design/KAORI_DESIGN_SYSTEM.md")
    alertmanager_readme = read("app/alertmanager/README.md")

    assert 'Validation: What Validation Does, Why It Matters, Operator Flow' in workspace_summary
    assert 'Runtime: Readiness Versus Health, How Monitoring Works, Resolver Correlation' in workspace_summary
    assert 'Unknown or not-observed posture must not be presented as Critical' in health
    assert 'oversized radial or donut score chart' in health
    assert 'Mixed peer-summary styling' in audit
    assert '## Health Interpretation' in design_system
    assert 'does not use a decorative radial chart' in alertmanager_readme
