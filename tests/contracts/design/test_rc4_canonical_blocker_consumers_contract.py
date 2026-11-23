"""RC.4 UAT correction: shared provider blocking and evidence-first workspaces (#5136)."""

from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_source_control_missing_installation_is_terminally_blocked() -> None:
    for name in ('overview', 'repositories', 'analytics'):
        html = read(f'app/templates/source_control/{name}.html')
        Environment().parse(html)
        assert 'components/provider_prerequisite/_setup_blocker.html' in html
        assert 'components/states/_blocked_state.html' in html
        assert 'Source Control Installation Required' in html
        assert 'Open Source Control Integrations' in html
        assert 'components/states/_empty_state.html' not in html

    overview = read('app/templates/source_control/overview.html')
    analytics = read('app/templates/source_control/analytics.html')
    repositories = read('app/templates/source_control/repositories.html')
    assert '{% if scope.installation_count == 0 %}' in overview
    assert '{% elif scope.committed_count == 0 %}' in overview
    assert '{% if not authorized_installations %}' in analytics
    assert '{% if not scope.installations %}' in repositories
    assert '{% if selected and inventory.total is not none %}' in repositories
    assert '{% elif selected %}' in repositories


def test_source_control_preserves_committed_scope_and_three_independent_sources() -> None:
    analytics = read('app/templates/source_control/analytics.html')
    routes = read('app/source_control/routes.py')
    assert 'analytics_readiness.source_card(' in analytics
    for source in ('Domain Integration', 'Metrics Source', 'Alert Source'):
        assert source in analytics
    assert 'Not Evaluated' in analytics
    assert 'repository_coverage.grant_count_matches_observation' in analytics
    assert 'read_repository_coverage_for_current_session' in routes
    assert "_require_product_uat_access()" in routes
    assert "if raw_installation_id:" in routes
    assert "abort(404)" in routes
    assert 'HarborClient' not in routes
    assert 'GitHubClient' not in routes


def test_security_blocks_unqualified_scans_using_existing_components() -> None:
    overview = read('app/templates/security_posture/overview.html')
    findings = read('app/templates/security_posture/findings.html')
    for html in (overview, findings):
        Environment().parse(html)
        assert "posture.scanned_artifacts > 0" in html
        assert 'components/provider_prerequisite/_setup_blocker.html' in html
        assert 'components/states/_blocked_state.html' in html
        assert 'Registry Scanner Evidence Required' in html
    assert '{% if not security_evidence_ready %}' in overview
    assert '{% if not findings_ready %}' in findings
    assert 'data-security-findings-registry' in findings
    assert 'can_manage_integrations=current_user.has_permission' in read(
        'app/security_posture/routes.py'
    )


def test_registry_and_vault_reuse_shared_geometry_and_one_line_copy() -> None:
    registry = read('app/templates/artifact_registry/components/_setup_blocker.html')
    secrets = read('app/templates/secrets_pki/overview.html')
    assert 'Registry Provider Required' in registry
    assert 'components/provider_prerequisite/_setup_blocker.html' in registry
    assert 'components/states/_blocked_state.html' in secrets
    line = next(
        item for item in secrets.splitlines()
        if "No eligible Vault source; uncollected KV v2 inventory is not zero Secrets." in item
    )
    assert len(line.strip()) < 115
    assert 'whitespace-nowrap' not in secrets
