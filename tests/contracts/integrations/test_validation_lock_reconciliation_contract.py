from __future__ import annotations

from pathlib import Path


def test_validation_claim_reconciles_stale_locks_before_atomic_claim() -> None:
    source = Path('app/integrations/validation/state.py').read_text()

    assert 'def _release_stale_validation_lock' in source
    assert 'ACTIVE_JOB_STATUSES' in source
    assert 'for candidate_key in (lock_key, *conflict_keys):' in source
    assert '_release_stale_validation_lock(client, candidate_key)' in source
    assert 'client.eval(_COMPARE_DELETE_SCRIPT' in source
