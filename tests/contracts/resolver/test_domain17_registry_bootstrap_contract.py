from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_application_initializes_registry_before_celery():
    source = (ROOT / 'app/__init__.py').read_text()
    assert source.index('init_resolver_registry(app)') < source.index('init_celery(app)')


def test_bootstrap_requires_explicit_namespace_allowlist_and_fingerprint():
    source = (ROOT / 'app/integrations/resolver_bootstrap.py').read_text()
    assert 'explicit namespace allowlist' in source
    assert 'registry_fingerprint' in source
    assert 'Unknown enabled resolver actions' in source
    assert 'RESOLVER_TOKEN_SIGNING_KEY with at least 32 characters' in source


def test_policy_migration_is_linear_and_restrictive():
    source = (ROOT / 'migrations/versions/20260723_resolver_registry.py').read_text()
    assert "down_revision = '20260723_candidate_review'" in source
    assert 'uq_resolver_policy_cluster_action' in source
    assert "lifecycle_status IN ('active', 'disabled')" in source
