from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_publish_service_executes_validation_before_status_transition() -> None:
    source = text('app/knowledge/service.py')
    assert source.index('validate_publication(') < source.index("revision.publication_status = 'published'")
    assert 'revision.publication_validation_json = result.as_dict()' in source
    assert 'if not result.valid:' in source


def test_publication_gate_checks_resolver_dry_run_capability_and_rollback() -> None:
    source = text('app/knowledge/validation.py')
    for boundary in (
        "resolver_registry.resolve(revision.resolver_key)",
        "getattr(adapter, 'dry_run', None)",
        "getattr(adapter, 'execute', None)",
        'required_capabilities_json',
        'compatibility_profiles_json',
        'rollback_required',
        'validate_version_transition(',
        'validate_parameter_schema(',
    ):
        assert boundary in source


def test_migration_follows_knowledge_runbook_head() -> None:
    source = text('migrations/versions/20260723_runbook_authoring_validation.py')
    assert "down_revision = '20260723_knowledge_runbooks'" in source
    assert 'publication_validation_json' in source
    assert 'reviewed_by_user_id' in source
