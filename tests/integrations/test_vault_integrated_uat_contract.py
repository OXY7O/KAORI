"""Contract that DevContainer Vault acceptance references real KAORI sources.

This test does NOT prove live provider, PostgreSQL or human acceptance.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNBOOK = ROOT / 'app/secrets_pki/VAULT_DEVCONTAINER_UAT.md'
ROUTES = ROOT / 'app/secrets_pki/routes.py'
ALERT_ROUTES = ROOT / 'app/intelligence/alert_intelligence/routes.py'
JOBS = ROOT / 'app/definitions/catalogs/platform_operations/jobs/registered_jobs.yaml'


def test_all_safe_vault_operational_endpoints_are_registered():
    urls = ROUTES.read_text(encoding='utf-8')
    guide = RUNBOOK.read_text(encoding='utf-8')
    for slug in (
        '', 'inventory', 'registry', 'lifecycle', 'certificates', 'pki',
        'expiration', 'leases', 'consumers', 'governance',
        'analytics/certificates',
    ):
        pattern = f"@secrets_pki_bp.get('/{slug}')"
        assert pattern in urls
        assert "/secrets-pki/" + slug in guide
        assert "@permission_required('secrets_pki.view')" in urls.split(pattern, 1)[1][:115]


def test_alertcase_path_is_exact_not_invented():
    guide = RUNBOOK.read_text(encoding='utf-8')
    code = ALERT_ROUTES.read_text(encoding='utf-8')
    assert "url_prefix='/intelligence/alert-intelligence'" in code
    assert "@alert_intelligence_bp.get('/vault-cases')" in code
    assert "/intelligence/alert-intelligence/vault-cases" in guide
    assert "KAORI_VAULT_PROVIDER_CASE_ADMISSION_ENABLED" in guide
    assert "must be absent/false" in guide


def test_manual_vault_jobs_in_guide_exist_in_canonical_catalog():
    guide = RUNBOOK.read_text(encoding='utf-8')
    source = JOBS.read_text(encoding='utf-8')
    for key in (
        'secrets_pki.inventory.sync',
        'secrets_pki.pki.sync',
        'secrets_pki.pki.stored_certs.sync',
        'secrets_pki.vault_alerts.observe',
    ):
        assert f'- key: {key}' in source
        assert key in guide


def test_uat_checklist_paths_refer_to_real_focused_suites():
    guide = RUNBOOK.read_text(encoding='utf-8')
    suites = (
        'tests/integrations/test_vault_provider.py',
        'tests/integrations/test_vault_pki_committed_inventory.py',
        'tests/integrations/test_vault_stored_certificates_committed.py',
        'tests/integrations/test_vault_pki_readiness_freshness.py',
        'tests/integrations/test_scoped_secrets_pki_registry_web.py',
        'tests/integrations/test_secrets_pki_pki_evidence_workspaces.py',
        'tests/integrations/test_secrets_pki_operational_evidence_workspaces.py',
        'tests/intelligence/test_vault_provider_case_admission.py',
        'tests/intelligence/test_vault_provider_case_workspace.py',
    )
    for path in suites:
        assert (ROOT / path).is_file(), path
        assert path in guide
    assert (ROOT / 'scripts/quality_gate.sh').is_file()
    assert (ROOT / 'pyrightconfig.json').is_file()


def test_uat_documents_do_not_assert_unexecuted_pass():
    guide = RUNBOOK.read_text(encoding='utf-8')
    matrix = (ROOT / 'app/secrets_pki/VAULT_INTEGRATED_UAT.md').read_text(
        encoding='utf-8',
    )
    for phrase in (
        'Not Tested', 'Not Materialized', 'human acceptance',
        'No Secret value', 'qualified zero', 'HOLD',
    ):
        assert phrase.casefold() in guide.casefold()
    assert 'canonical #724 policy evaluator still absent' not in matrix
    assert 'canonical persisted #724 scope evaluator not implemented' not in matrix


def test_existing_kaori_quality_gates_are_reused_not_replaced():
    guide = RUNBOOK.read_text(encoding='utf-8')
    for command in (
        'python -m ruff check',
        'python -m pytest -q',
        'python -m pyright --project pyrightconfig.json',
        'bash scripts/quality_gate.sh --static',
    ):
        assert command in guide
