from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE_PATH = ROOT / "app" / "templates" / "components" / "live_lookup_notice.html"
BASELINE_PATH = ROOT / "docs" / "architecture" / "ui-style-debt-baseline.json"

SEMANTIC_BORDER = re.compile(
    r"\bborder-status-"
    r"(?:normal|warning|critical|info|unknown|disabled|pending|maintenance)-"
    r"border\b"
)


def test_live_lookup_notice_uses_shared_warning_border_authority() -> None:
    source = TEMPLATE_PATH.read_text(encoding="utf-8")

    assert "{% import 'components/table_label.html' as table_label %}" in source
    assert "table_label.tone_border_classes('warning')" in source
    assert SEMANTIC_BORDER.findall(source) == []

    assert "bg-status-warning-soft p-4 text-status-warning-text" in source
    assert 'role="alert"' in source
    assert 'aria-live="polite"' in source
    assert 'data-lucide="triangle-alert"' in source


def test_live_lookup_notice_semantic_border_debt_is_burned_down() -> None:
    payload = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    relative = TEMPLATE_PATH.relative_to(ROOT).as_posix()

    assert relative not in payload["files"]
