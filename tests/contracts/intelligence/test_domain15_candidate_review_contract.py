from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_candidate_is_persisted_non_executable_and_reviewed():
    source = (ROOT / 'app/knowledge/candidate_review.py').read_text()
    assert "'executable': False" in source
    assert "review_status = 'promoted'" in source
    assert 'reviewed_by_user_id' in source
    assert 'promoted_decision_id' in source


def test_promotion_uses_decision_workflow_not_resolver():
    source = (ROOT / 'app/knowledge/candidate_review.py').read_text()
    assert 'create_decision_snapshot(' in source
    assert 'persist_decision(' in source
    assert 'issue_execution_token' not in source
    assert 'dispatch_resolution' not in source
    assert 'enqueue_execution_delivery' not in source


def test_dedup_expiry_and_stale_revision_guards_exist():
    source = (ROOT / 'app/knowledge/candidate_review.py').read_text()
    model = (ROOT / 'app/models/intelligence.py').read_text()
    assert 'deduplication_key' in source and 'deduplication_key' in model
    assert 'expire_stale_candidates' in source
    assert "revision.publication_status != 'published'" in source
    assert 'compute_evidence_hash(record.evidence_json)' in source
