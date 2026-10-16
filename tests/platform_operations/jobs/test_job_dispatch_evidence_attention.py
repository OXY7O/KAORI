from pathlib import Path
from types import SimpleNamespace

from app.platform_operations.jobs.configuration import _policy_status

ROOT = Path(__file__).resolve().parents[3]


def test_incomplete_audit_evidence_is_not_rendered_as_enabled_healthy() -> None:
    status = _policy_status(SimpleNamespace(enabled=True, last_dispatch_status='evidence_failed'))
    assert status == {
        'label': 'Dispatch Evidence Incomplete',
        'tone': 'warning',
        'icon': 'shield-alert',
    }


def test_source_owned_selected_workspace_and_overview_count_evidence_failure() -> None:
    source = (ROOT / 'app/platform_operations/jobs/configuration.py').read_text(encoding='utf-8')
    assert "'evidence_failed'" in source
    assert "'Dispatch Evidence Incomplete'" in source
    assert "if policy.last_dispatch_status in {'failed', 'evidence_failed'}" in source
    documentation = (ROOT / 'app/platform_operations/jobs/README.md').read_text(encoding='utf-8')
    assert 'bounded five-minute retry' in documentation
    assert 'evidence_failed' in documentation
