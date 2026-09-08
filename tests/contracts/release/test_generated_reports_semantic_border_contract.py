from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE_PATH = ROOT / "app" / "templates" / "reports" / "generated" / "index.html"
BASELINE_PATH = ROOT / "docs" / "architecture" / "ui-style-debt-baseline.json"

WARNING_BORDER = re.compile(r"\bborder-status-warning-border\b")


def test_generated_reports_storage_notice_uses_shared_warning_border_authority() -> None:
    source = TEMPLATE_PATH.read_text(encoding="utf-8")

    assert '{% import "components/table_label.html" as table_label %}' in source
    assert "table_label.tone_border_classes('warning')" in source
    assert WARNING_BORDER.findall(source) == []
    assert "{% if payload.storage_notice %}" in source
    assert 'data-generated-storage-degraded="true"' in source
    assert "bg-status-warning-soft" in source
    assert "text-status-warning-text" in source
    assert 'data-lucide="wifi-off"' in source
    assert "Artifact Storage Needs Review" in source
    assert "Open Storage" in source


def test_generated_reports_semantic_border_debt_is_burned_down() -> None:
    payload = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    relative = TEMPLATE_PATH.relative_to(ROOT).as_posix()

    assert relative not in payload["files"]
