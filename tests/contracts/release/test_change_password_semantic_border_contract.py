from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CALLOUT_PATH = ROOT / "app" / "templates" / "components" / "operational_callout.html"
TARGET_PATH = ROOT / "app" / "templates" / "settings" / "account" / "partials" / "_change_password.html"
BASELINE_PATH = ROOT / "docs" / "architecture" / "ui-style-debt-baseline.json"
SEMANTIC_BORDER = re.compile(
    r"\bborder-status-"
    r"(?:normal|warning|critical|info|unknown|disabled|pending|maintenance)-"
    r"border(?:/[0-9]+)?\b"
)


def test_change_password_uses_static_subtle_semantic_border_authority() -> None:
    callout_source = CALLOUT_PATH.read_text(encoding="utf-8")
    target_source = TARGET_PATH.read_text(encoding="utf-8")

    assert "macro semantic_border_classes(tone='info', variant='default')" in callout_source
    for tone in ("normal", "warning", "critical", "unknown", "info"):
        assert f"border-status-{tone}-border/60" in callout_source

    assert "operational_callout.semantic_border_classes('warning', 'subtle')" in target_source
    assert SEMANTIC_BORDER.findall(target_source) == []

    assert 'data-password-sharing-warning="true"' in target_source
    assert 'role="note"' in target_source
    assert "bg-status-warning-soft/55" in target_source
    assert "text-status-warning-text" in target_source
    assert 'data-lucide="message-circle-warning"' in target_source
    assert "Keep your password private." in target_source
    assert "Never share it with anyone, including administrators or support staff." in target_source


def test_change_password_semantic_border_debt_is_burned_down() -> None:
    payload = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    relative = TARGET_PATH.relative_to(ROOT).as_posix()

    assert relative not in payload["files"]
