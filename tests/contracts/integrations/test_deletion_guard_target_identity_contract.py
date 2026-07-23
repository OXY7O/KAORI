from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.contract


def test_deletion_guard_checks_canonical_resource_groups() -> None:
    source = Path('app/integrations/deletion.py').read_text(encoding='utf-8')

    assert "f'integration:{provider_type}:{provider_instance_id}'" in source
    assert "f'kubernetes-cluster:{cluster_id}'" in source
    assert "f'integration:kubernetes:{connection_id}'" in source
    assert 'JobExecution.status.in_(ACTIVE_JOB_STATUSES)' in source
