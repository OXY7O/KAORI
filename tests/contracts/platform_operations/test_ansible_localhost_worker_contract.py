from __future__ import annotations

from flask import Flask
import pytest

from app.infrastructure_automation.source import (
    SOURCE_SHA,
    AutomationPilotDenied,
    normalize_facts,
    require_local_pilot_enabled,
    verify_localhost_source,
)


def _app(environment: str) -> Flask:
    app = Flask(__name__)
    app.config["APP_ENV"] = environment
    return app


def test_disabled_without_explicit_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KAORI_AUTOMATION_LOCALHOST_PILOT_ENABLED", raising=False)
    with _app("development").app_context(), pytest.raises(AutomationPilotDenied, match="disabled"):
        require_local_pilot_enabled()


def test_production_rejected_even_if_flag_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KAORI_AUTOMATION_LOCALHOST_PILOT_ENABLED", "true")
    with _app("production").app_context(), pytest.raises(AutomationPilotDenied, match="non-production"):
        require_local_pilot_enabled()


def test_unapproved_source_denied_before_checkout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KAORI_AUTOMATION_LOCALHOST_PILOT_ENABLED", "true")
    with _app("development").app_context(), pytest.raises(AutomationPilotDenied, match="approved pilot SHA"):
        verify_localhost_source("/does/not/exist", "0" * 40)


def test_result_redaction_drops_unapproved_sensitive_facts() -> None:
    result = normalize_facts(
        [{
            "event": "runner_on_ok",
            "event_data": {
                "task_action": "ansible.builtin.setup",
                "res": {
                    "ansible_facts": {
                        "ansible_distribution": "OracleLinux",
                        "ansible_kernel": "5.15.0",
                        "ansible_env": {"PASSWORD": "not-for-evidence"},
                        "ansible_password": "secret",
                    }
                },
            },
        }]
    )
    assert result == {"ansible_distribution": "OracleLinux", "ansible_kernel": "5.15.0"}


def test_runner_ok_without_facts_is_not_verified() -> None:
    with pytest.raises(AutomationPilotDenied, match="Required source-backed"):
        normalize_facts([{"event": "runner_on_ok", "event_data": {"task_action": "shell"}}])


def test_source_revision_is_immutable_sha() -> None:
    assert len(SOURCE_SHA) == 40
