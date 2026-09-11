from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TARGET_PATH = (
    ROOT
    / "app"
    / "templates"
    / "access"
    / "identity_providers"
    / "partials"
    / "_directory_provisioning_strip.html"
)
BASELINE_PATH = ROOT / "docs" / "architecture" / "ui-style-debt-baseline.json"
COPIED_SHELL = "overflow-hidden rounded-xl border border-outline-default bg-surface-card shadow-sm"
SHARED_SHELL = "{{ surface_ui.block_classes() }}"


def test_directory_provisioning_strip_uses_shared_surface_shell_authority() -> None:
    source = TARGET_PATH.read_text(encoding="utf-8")

    assert '{% import "components/table_primitives.html" as surface_ui %}' in source
    assert f'<section class="{SHARED_SHELL}">' in source
    assert COPIED_SHELL not in source

    assert "Directory Provisioning" in source
    assert "Directory Workflow" in source
    assert "identity_providers.provision" in source
    assert "identity_providers.directory_provisioning" in source
    assert "Open Directory Provisioning" in source
    assert "Read Only" in source
    assert "sm:grid-cols-3" in source
    assert "summary.directory_identity_links" in source


def test_directory_provisioning_strip_copied_shell_debt_is_burned_down() -> None:
    payload = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    relative = TARGET_PATH.relative_to(ROOT).as_posix()

    assert relative not in payload["files"]
