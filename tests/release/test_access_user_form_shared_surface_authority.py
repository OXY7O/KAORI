from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGET_PATH = ROOT / "app" / "templates" / "access" / "users" / "form.html"
BASELINE_PATH = ROOT / "docs" / "architecture" / "ui-style-debt-baseline.json"
COPIED_SHELL = "overflow-hidden rounded-xl border border-outline-default bg-surface-card shadow-sm"
SHARED_SHELL = "surface_ui.block_classes()"


def test_user_form_uses_shared_surface_shell_authority() -> None:
    source = TARGET_PATH.read_text(encoding="utf-8")

    assert '{% import "components/table_primitives.html" as surface_ui %}' in source
    assert source.count(SHARED_SHELL) == 5
    assert COPIED_SHELL not in source

    # Preserve the create/edit identity and credential-management contract while
    # moving only outer presentation-shell ownership to the shared primitive.
    assert "User Configuration" in source
    assert "Identity Profile" in source
    assert "Identity Source & Credential Ownership" in source
    assert "Credential Management" in source
    assert "Access Role" in source
    assert "Lifecycle" in source
    assert "Back to Users" in source
    assert "form.hidden_tag()" in source


def test_user_form_copied_shell_debt_is_burned_down_only() -> None:
    payload = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    relative = TARGET_PATH.relative_to(ROOT).as_posix()

    assert payload["files"][relative] == {"semantic_border_utilities": 7}
