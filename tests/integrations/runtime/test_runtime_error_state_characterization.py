from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_runtime_audit_keeps_provider_attention_states_distinct() -> None:
    service = read("app/integrations/service.py")

    for state in ("degraded", "unhealthy", "not_observed"):
        assert state in service
    assert "validation_required" in service
    assert "blocked" in service


def test_runtime_audit_has_executable_recovery_transition_evidence() -> None:
    recovery = read("app/integrations/runtime/recovery.py")

    assert "def is_runtime_recovery(" in recovery
    assert "previous not in _HEALTHY_STATES and current in _HEALTHY_STATES" in recovery
    assert "trigger_type='recovery'" in recovery
    assert "Recovery dispatch is best-effort." in recovery


def test_runtime_audit_keeps_report_storage_outage_degraded_not_successful() -> None:
    service = read("app/reports/generated/service.py")
    template = read("app/templates/reports/generated/index.html")

    assert "Report records remain available" in service
    assert "actions stay paused until connectivity returns." in service
    assert 'data-generated-storage-degraded="true"' in template
    assert "Artifact Storage Needs Review" in template


def test_runtime_audit_has_responsive_database_unavailable_evidence() -> None:
    browser_test = read("tests/ui/test_runtime_state_responsiveness.py")

    assert "'database_unavailable': 'PostgreSQL Unavailable'" in browser_test
    assert "assert response.status == 503" in browser_test
    assert "heading', name='Database Setup Required'" in browser_test
    assert "layout['scrollWidth'] <= layout['clientWidth'] + 1" in browser_test
