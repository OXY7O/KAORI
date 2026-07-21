from pathlib import Path


def test_cutover_migration_guards_data_before_dropping_legacy_storage() -> None:
    source = Path('migrations/versions/20260721_integration_domain_cutover.py').read_text()
    assert '_assert_cutover_ready(bind)' in source
    assert '_backfill_remaining_legacy_bindings(bind)' in source
    assert "_encrypt_column(bind, 'kubernetes_connections', 'kubeconfig')" in source
    assert 'Canonical integration cutover requires INTEGRATION_CREDENTIAL_KEY' in source
    assert 'from app.security.credentials' not in source
    assert "op.drop_table('prometheus_bindings')" in source
    assert "op.drop_table('alertmanager_bindings')" in source
    assert "op.drop_table('prometheus_configs')" in source
    assert "op.drop_table('alertmanager_configs')" in source
    assert "batch.drop_column('kubeconfig')" in source
