from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


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




def test_governance_overview_is_capability_first_and_permission_gates_tls_evidence() -> None:
    routes = read('app/kubernetes/governance/routes.py')
    overview = read('app/templates/kubernetes/governance/overview/index.html')
    standard = read('docs/design/patterns/KUBERNETES_TLS_CERTIFICATE_GOVERNANCE.md')

    assert "@permission_required('governance.view')\ndef overview" in routes
    assert "can_view_tls = current_user.has_permission('tls_certificates.view')" in routes
    assert 'get_tls_certificate_page({})' in routes
    assert 'if can_view_tls and has_registered_clusters() is not False' in routes
    assert 'can_view_tls=can_view_tls' in routes
    assert 'tls_payload=tls_payload' in routes

    for token in (
        'Governance Capabilities',
        'Committed Governance Posture',
        'TLS Governance Snapshot',
        'TLS Governance Posture',
        'Governance Model',
        'components/snapshot_context_bar.html',
        'Additional governance capabilities appear here only after they are implemented and authorized',
    ):
        assert token in overview

    assert '{% if can_view_tls and tls_payload %}' in overview
    assert 'View Permission Required' in overview
    assert 'TLS View Restricted' in overview
    assert 'Governance Overview landing contract' in standard
    assert 'never queries Kubernetes at request time' in standard


def test_governance_dead_job_presentation_helper_is_retired() -> None:
    source = read('app/kubernetes/governance/tls_certificates/job_presentation.py')
    assert 'def get_active_tls_sync_job(' not in source


def test_governance_final_release_evidence_is_wired_to_quality_gate() -> None:
    quality_gate = read('scripts/quality_gate.sh')
    coverage = read('scripts/verify_feature_test_coverage.py')
    assert 'python scripts/verify_governance_final_lock.py' in quality_gate
    for path in (
        'tests/unit/kubernetes/governance/test_tls_governance_policy.py',
        'tests/kubernetes/governance/test_tls_governance_route_characterization.py',
        'tests/security/kubernetes/governance/test_tls_governance_security.py',
        'tests/rendering/kubernetes/governance/test_tls_governance_rendering.py',
        'tests/integration/kubernetes/governance/test_tls_certificate_read_model.py',
        'tests/e2e/kubernetes/governance/test_tls_governance_smoke.py',
    ):
        assert path in coverage
