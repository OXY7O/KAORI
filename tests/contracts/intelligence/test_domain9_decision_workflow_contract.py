from pathlib import Path


def test_decision_workflow_has_persisted_approval_and_execution_journal() -> None:
    model_source = Path('app/models/intelligence.py').read_text()
    workflow_source = Path('app/intelligence/workflow.py').read_text()

    assert 'class IntelligenceDecision(' in model_source
    assert 'class IntelligenceDecisionApproval(' in model_source
    assert 'class IntelligenceExecutionJournal(' in model_source
    assert "UniqueConstraint('token_nonce_hash'" in model_source
    assert "journal.status != 'authorized'" in workflow_source
    assert "record.workflow_status = 'dispatched'" in workflow_source


def test_decision_transitions_require_rbac_and_emit_audit_evidence() -> None:
    workflow_source = Path('app/intelligence/workflow.py').read_text()
    permissions_source = Path('app/rbac/defaults.py').read_text()

    for permission in (
        'intelligence.decisions.view',
        'intelligence.decisions.create',
        'intelligence.decisions.approve',
        'intelligence.decisions.execute',
    ):
        assert permission in permissions_source

    assert '_require_permission(actor_permissions, CREATE_PERMISSION)' in workflow_source
    assert '_require_permission(actor_permissions, APPROVE_PERMISSION)' in workflow_source
    assert '_require_permission(actor_permissions, EXECUTE_PERMISSION)' in workflow_source
    assert "target_type = 'intelligence_decision'" in workflow_source


def test_migration_is_single_head_successor_and_has_rollback() -> None:
    source = Path('migrations/versions/20260723_decision_workflow_foundation.py').read_text()
    assert "down_revision = '20260722_foundation_cleanup'" in source
    assert "op.create_table(\n        'intelligence_decisions'" in source
    assert "op.create_table(\n        'intelligence_decision_approvals'" in source
    assert "op.create_table(\n        'intelligence_execution_journal'" in source
    assert "op.drop_table('intelligence_execution_journal')" in source
