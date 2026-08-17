from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_governance_routes_do_not_short_circuit_authorization_with_blueprint_before_request() -> None:
    source = read('app/kubernetes/governance/routes.py')
    assert '@governance_bp.before_request' not in source
    assert 'block_clusterless_governance_actions' not in source


def test_tls_routes_own_authorized_clusterless_handling() -> None:
    source = read('app/kubernetes/governance/tls_certificates/routes.py')
    assert 'def _clusterless_read_response()' in source
    assert 'def _clusterless_detail_response()' in source
    assert 'def _clusterless_sync_response()' in source
    assert source.index("@permission_required('tls_certificates.view')\ndef tls_certificates_index") < source.index(
        'clusterless_response = _clusterless_read_response()'
    )


def test_governance_dead_job_presentation_helper_is_retired() -> None:
    source = read('app/kubernetes/governance/tls_certificates/job_presentation.py')
    assert 'def get_active_tls_sync_job(' not in source


def test_governance_final_release_evidence_is_wired_to_quality_gate() -> None:
    quality_gate = read('scripts/quality_gate.sh')
    coverage = read('scripts/verify_feature_test_coverage.py')
    assert 'python scripts/verify_governance_final_lock.py' in quality_gate
    for path in (
        'tests/unit/governance/test_tls_governance_policy.py',
        'tests/governance/test_tls_governance_route_characterization.py',
        'tests/security/governance/test_tls_governance_security.py',
        'tests/rendering/governance/test_tls_governance_rendering.py',
        'tests/integration/governance/test_tls_certificate_read_model.py',
        'tests/e2e/governance/test_tls_governance_smoke.py',
    ):
        assert path in coverage
