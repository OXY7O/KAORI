from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_shared_configuration_decision_supports_dense_optional_evidence() -> None:
    shared = read('app/templates/integrations/components/_configuration_decision.html')

    assert 'operational_effects=none' in shared
    assert 'validation_boundary=none' in shared
    assert 'Controlled Flow' in shared
    assert 'Operational Effects' in shared
    assert 'Validation Boundary' in shared
    assert 'mt-3 grid gap-2 sm:grid-cols-2' in shared
    assert 'flex h-full min-h-full flex-col self-stretch' in shared


def test_prometheus_configuration_populates_operational_effects() -> None:
    prometheus = read('app/templates/prometheus/partials/_detail_configuration.html')

    for token in (
        "('Save Changes', 'Resets technical readiness.')",
        "('Test Connection', 'Proves transport reachability only.')",
        "('Full Validation', 'Rebuilds capability evidence.')",
        "('Consumer Use', 'Requires eligible scope bindings.')",
    ):
        assert token in prometheus


def test_prometheus_configuration_populates_validation_boundary() -> None:
    prometheus = read('app/templates/prometheus/partials/_detail_configuration.html')

    for token in (
        "('Transport Check', 'Test Connection')",
        "('Capability Contract', 'Full Validation')",
        "('Consumer Eligibility', 'Scope Binding')",
        "('Operational Use', 'Source Resolution')",
    ):
        assert token in prometheus


def test_prometheus_configuration_keeps_symmetric_geometry_and_compact_boundary_copy() -> None:
    prometheus = read('app/templates/prometheus/partials/_detail_configuration.html')

    assert 'grid items-stretch gap-4' in prometheus
    assert (
        'Prometheus executes metric queries. KAORI governs source selection, validation evidence, bindings, and consumer eligibility.'
        in prometheus
    )
    assert 'Prometheus remains authoritative for metric collection and query execution.' not in prometheus
