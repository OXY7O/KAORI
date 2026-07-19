from pathlib import Path


def _root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_reconciliation_command_is_registered() -> None:
    commands = (_root() / 'app/commands/__init__.py').read_text(encoding='utf-8')
    assert 'reconcile_integration_legacy' in commands
    assert 'app.cli.add_command(reconcile_integration_legacy)' in commands


def test_reconciliation_is_guarded_and_dry_run_by_default() -> None:
    source = (_root() / 'app/commands/integrations.py').read_text(encoding='utf-8')
    assert "'reconcile-integration-legacy'" in source
    assert "@click.option('--apply'" in source
    assert "build_reconciliation_report(apply=False)" in source
    assert "build_reconciliation_report(apply=True)" in source


def test_reconciliation_covers_orphans_legacy_rows_and_kubeconfig() -> None:
    source = (_root() / 'app/integrations/legacy_reconcile.py').read_text(encoding='utf-8')
    assert 'delete_empty_orphan' in source
    assert 'delete_merged_orphan' in source
    assert 'delete_verified_legacy_bindings' in source
    assert 'delete_verified_legacy_configs' in source
    assert 'clear_verified_legacy_kubeconfig' in source


def test_reconciliation_recovers_targets_from_runtime_and_bindings() -> None:
    source = (_root() / 'app/integrations/legacy_reconcile.py').read_text(encoding='utf-8')
    assert 'runtime_observation.instance_id=' in source
    assert 'matching binding asset=' in source
    assert 'create_canonical_binding_from_legacy' in source
    assert 'canonical_bindings_created' in source
