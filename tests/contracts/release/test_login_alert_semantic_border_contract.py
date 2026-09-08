from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE_PATH = (
    ROOT
    / "app"
    / "templates"
    / "access"
    / "authentication"
    / "partials"
    / "_login_alerts.html"
)
BASELINE_PATH = ROOT / "docs" / "architecture" / "ui-style-debt-baseline.json"
SEMANTIC_BORDER = re.compile(
    r"\bborder-status-"
    r"(?:normal|warning|critical|info|unknown|disabled|pending|maintenance)-"
    r"border\b"
)


def test_login_alerts_use_shared_semantic_border_authority() -> None:
    source = TEMPLATE_PATH.read_text(encoding="utf-8")

    assert '{% import "components/operational_callout.html" as operational_callout %}' in source
    assert "operational_callout.semantic_border_classes('normal')" in source
    assert "operational_callout.semantic_border_classes('critical')" in source
    assert SEMANTIC_BORDER.findall(source) == []

    assert "get_flashed_messages(with_categories=true)" in source
    assert 'category == "success"' in source
    assert 'role="status"' in source
    assert 'role="alert"' in source
    assert 'data-lucide="circle-check"' in source
    assert 'data-lucide="triangle-alert"' in source
    assert "bg-status-normal-soft" in source
    assert "text-status-normal-text" in source
    assert "bg-status-critical-soft" in source
    assert "text-status-critical-text" in source


def test_login_alert_semantic_border_debt_is_burned_down() -> None:
    payload = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    relative = TEMPLATE_PATH.relative_to(ROOT).as_posix()

    assert relative not in payload["files"]
