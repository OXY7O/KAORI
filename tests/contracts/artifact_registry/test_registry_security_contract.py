from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_security_evidence_is_digest_oriented_and_incremental() -> None:
    models = read('app/models/registry.py')
    collector = read('app/integrations/registry/providers/harbor/security.py')
    sync = read('app/artifact_registry/security/sync.py')

    assert 'class RegistryScanSnapshot' in models
    assert 'class RegistryVulnerability' in models
    assert "UniqueConstraint('repository_id', 'digest'" in models
    assert 'get_vulnerability_report' in collector
    assert '_scan_identity_changed' in collector
    assert 'reuse_existing_scan' in collector
    assert 'RegistryVulnerability(' in sync


def test_security_read_model_is_committed_and_server_paginated() -> None:
    presentation = read('app/artifact_registry/security/presentation.py')

    assert 'RegistryArtifact.query' in presentation
    assert 'RegistryVulnerability.query' in presentation
    assert 'paginate_query(' in presentation
    assert "JobExecution.job_type == 'artifact_registry_security'" in presentation
    assert 'HarborClient' not in presentation


def test_security_workspace_uses_canonical_kaori_components() -> None:
    template = read('app/templates/artifact_registry/partials/_security_workspace.html')

    for shared_component in (
        'components/snapshot_context_bar.html',
        'components/operational_metric_card.html',
        'components/operational_section_card.html',
        'components/table.html',
        'components/table_registry.html',
        'components/table_label.html',
        'components/states/_empty_state.html',
    ):
        assert shared_component in template
    assert 'Security Evidence Snapshot' in template
    assert 'Provider Capability Matrix' in template
    assert '[5, 10, 25, 50]' in template
    assert 'Presence is not trust-policy evaluation.' in template
    assert 'Search CVE, package, repo, or digest…' in template
    assert 'Current critical findings from the latest committed scan evidence.' not in template
    assert 'Current high-severity findings from the latest committed scan evidence.' not in template


def test_security_has_two_level_three_views_above_the_hero() -> None:
    catalog = read('app/common/workspace_navigation_catalog.py')
    navigation = read('app/common/workspace_navigation.py')
    routes = read('app/artifact_registry/routes.py')

    assert "'artifact_registry_security': (" in catalog
    assert "'Vulnerabilities'" in catalog
    assert "'Supply Chain'" in catalog
    assert "return 'artifact_registry_security'" in navigation
    assert "'artifact_registry_security': 'Security'" in navigation
    assert "@artifact_registry_bp.get('/security')" in routes
    assert "@artifact_registry_bp.get('/security/supply-chain')" in routes
    assert "return _security_response('vulnerabilities')" in routes


def test_registry_security_capabilities_are_provider_declared() -> None:
    providers = read('app/artifact_registry/security/providers.py')
    harbor = read('app/integrations/registry/providers/harbor/security.py')

    assert 'capabilities: frozenset[str]' in providers
    assert "capabilities=frozenset({'vulnerability', 'signature', 'sbom'})" in harbor


def test_registry_scan_evidence_semantics_are_shared_by_dashboard_and_intelligence() -> None:
    contracts = read('app/artifact_registry/security/contracts.py')
    presentation = read('app/artifact_registry/security/presentation.py')
    evaluator = read('app/intelligence/registry_recommendations.py')

    assert "SUCCESSFUL_REGISTRY_SCAN_STATUSES = frozenset({'success', 'finished', 'completed'})" in contracts
    assert 'SUCCESSFUL_REGISTRY_SCAN_STATUSES' in presentation
    assert 'func.lower(RegistryArtifact.scan_status).in_(SUCCESSFUL_REGISTRY_SCAN_STATUSES)' in presentation
    assert 'registry_scan_evidence_ready(artifact.scan_status)' in evaluator
    assert "if not registry_scan_evidence_ready(artifact.scan_status):" in evaluator
