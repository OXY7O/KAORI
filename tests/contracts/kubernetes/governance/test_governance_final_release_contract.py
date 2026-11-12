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


def test_governance_overview_reuses_authorized_tls_snapshot_and_operations_compact_catalog() -> None:
    routes = read('app/kubernetes/governance/routes.py')
    overview = read('app/templates/kubernetes/governance/overview/index.html')
    service = read('app/kubernetes/governance/tls_certificates/service.py')
    snapshot_partial = read('app/templates/kubernetes/governance/tls_certificates/partials/_snapshot_context.html')
    shared_card = read('app/templates/components/workspace_link_card.html')
    standard = read('docs/design/patterns/KUBERNETES_TLS_CERTIFICATE_GOVERNANCE.md')

    assert "@permission_required('governance.view')\ndef overview" in routes
    assert "can_view_tls = current_user.has_permission('tls_certificates.view')" in routes
    assert 'if can_view_tls and has_registered_clusters() is True:' in routes
    assert 'tls_snapshot = get_tls_collection_snapshot()' in routes
    assert 'get_tls_certificate_page' not in routes
    permission_position = routes.index("can_view_tls = current_user.has_permission(")
    readiness_position = routes.index('if can_view_tls and has_registered_clusters() is True:')
    snapshot_position = routes.index('tls_snapshot = get_tls_collection_snapshot()')
    assert permission_position < readiness_position < snapshot_position

    assert 'def get_tls_collection_snapshot() -> dict[str, Any]:' in service
    assert 'check_tls_governance_schema_readiness()' in service
    assert 'return _collection_snapshot(' in service
    assert "selected_cluster_id=''," in service
    assert "summary={'total': total}" in service
    assert 'TLSCertificateInventory.id' in service
    assert 'get_tls_certificate_page({})' not in routes
    assert 'TLS Collection Snapshot' in snapshot_partial
    assert 'snapshot_context.render(' in snapshot_partial

    for token in (
        'Kubernetes Governance',
        'Review Kubernetes governance controls, evidence, and ownership.',
        'Governance Scope',
        'Governance Capabilities',
        'Implemented governance controls are added as independent capability cards without changing the Overview structure.',
        'sm:grid-cols-2',
        "'title': 'TLS Certificates'",
        "'action': 'Open TLS Certificates' if can_view_tls else 'View Permission Required'",
        'workspace_card.render(',
        'compact=true',
        'Governance Model',
        'Governance Operating Model',
        'Provider Authority',
        'Policy & Guardrails',
        'Committed Evidence',
        'Controlled Handoffs',
        'KAORI applies governance policy and authorization guardrails without cloning the provider control plane.',
        'Open Cluster Integrations',
        'View Permission Required',
        'header_badge=capability_badge',
        "info_tip.render('governance-operating-model-guide'",
        "variant='guide'",
        'header_badge=model_guide',
        'overflow-hidden rounded-xl border border-outline-subtle',
    ):
        assert token in overview

    assert '{% if can_view_tls and tls_snapshot is not none %}' in overview
    assert "{% with payload={'snapshot': tls_snapshot} %}" in overview
    assert 'kubernetes/governance/tls_certificates/partials/_snapshot_context.html' in overview
    assert overview.index('partials/_snapshot_context.html') < overview.index("section_intro.render('Governance Scope'")
    assert overview.index("section_intro.render('Governance Scope'") < overview.index(
        "section_intro.render('Governance Model'"
    )
    assert '{% if cluster_onboarding.is_blocked %}' in overview
    assert 'components/cluster/_onboarding_banner.html' in overview
    assert 'components/snapshot_context_bar.html' not in overview
    assert 'Governance Control Context' not in overview
    assert 'New governance capabilities join this catalog only after implementation' not in overview
    assert '[grid-template-columns:repeat(auto-fit' not in overview
    assert "action_href=url_for('governance.tls_certificates')" not in overview
    assert 'get_tls_certificate_page' not in overview
    assert 'tls_payload' not in overview
    assert 'workspace.status_tone|default(none)' in shared_card
    assert "workspace.action_label|default('Open Workspace')" in shared_card

    assert 'Governance Overview landing contract' in standard
    assert 'domain-first' in standard
    assert 'get_tls_collection_snapshot()' in standard
    assert 'TLS Collection Snapshot' in standard
    assert '**Open Cluster Integrations**' in standard
    assert 'scalable equal-height catalog' in standard
    assert 'parent section owns no TLS-specific action' in standard
    assert 'two-column grid' in standard


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
