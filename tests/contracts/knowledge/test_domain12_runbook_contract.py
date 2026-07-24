from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_published_revision_and_decision_binding_contract() -> None:
    model = (ROOT / 'app/models/knowledge.py').read_text()
    decision = (ROOT / 'app/intelligence/decision.py').read_text()
    workflow = (ROOT / 'app/intelligence/workflow.py').read_text()
    assert "publication_status IN ('draft', 'published', 'withdrawn')" in model
    assert 'content_hash' in model
    for field in ('runbook_key', 'runbook_revision_id', 'runbook_version', 'runbook_content_hash'):
        assert field in decision
        assert field in workflow
    assert "revision.publication_status != 'published'" in workflow
    assert 'revision.content_hash != snapshot.runbook_content_hash' in workflow


def test_runbook_service_is_fail_closed() -> None:
    service = (ROOT / 'app/knowledge/service.py').read_text()
    assert 'Only draft runbook revisions can be published.' in service
    assert "publication_status == 'published'" in service
    assert 'assert_required_evidence' in service
    assert 'Missing required permission' in service


def test_domain12_migration_follows_domain11() -> None:
    migration = (ROOT / 'migrations/versions/20260723_knowledge_runbook_foundation.py').read_text()
    assert "down_revision = '20260723_resolver_orchestration'" in migration
    assert "op.create_table(\n        'knowledge_runbooks'" in migration
    assert "op.create_table(\n        'knowledge_runbook_revisions'" in migration
    assert 'fk_intelligence_decision_runbook_revision' in migration
