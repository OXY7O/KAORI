from pathlib import Path


def test_dispatch_requires_dry_run_before_token_consumption() -> None:
    source = Path('app/resolver/service.py').read_text()
    dry_run = source.index('dry_run = adapter.dry_run(context)')
    consume = source.index('journal = consume_execution_token(')
    execute = source.index('result = adapter.execute(context, dry_run)')

    assert dry_run < consume < execute
    assert "issued_journal.status = 'canceled'" in source
    assert "journal.status = 'failed'" in source


def test_registry_and_context_fail_closed() -> None:
    registry = Path('app/resolver/registry.py').read_text()
    contracts = Path('app/resolver/contracts.py').read_text()

    assert 'No resolver adapter is registered for action' in registry
    assert 'Resolver action is already registered' in registry
    assert 'build_idempotency_key' in contracts
    assert "'decision_id': decision_id" in contracts
    assert "'evidence_hash': evidence_hash" in contracts
    assert 'MappingProxyType' in contracts


def test_resolver_does_not_import_provider_mutation_services() -> None:
    source = Path('app/resolver/service.py').read_text()

    assert 'app.kubernetes_operations' not in source
    assert 'kubernetes.client' not in source
    assert 'app.prometheus' not in source
    assert 'app.alertmanager' not in source
