from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TARGET_PATH = (
    ROOT
    / 'app'
    / 'templates'
    / 'integrations'
    / 'orchestration'
    / 'container_orchestrator'
    / 'providers'
    / 'kubernetes'
    / 'partials'
    / '_runtime_workspace.html'
)
BASELINE_PATH = ROOT / 'docs' / 'architecture' / 'ui-style-debt-baseline.json'
COPIED_SHELL = 'overflow-hidden rounded-xl border border-outline-default bg-surface-card shadow-sm'
SHARED_SHELL = '{{ surface_ui.block_classes() }}'


def test_runtime_workspace_uses_shared_surface_shell_authority() -> None:
    source = TARGET_PATH.read_text(encoding='utf-8')

    assert '{% import "components/table_primitives.html" as surface_ui %}' in source
    assert f'class="{SHARED_SHELL} font-sans"' in source
    assert COPIED_SHELL not in source

    assert '<article id="kubernetes-runtime-workspace"' in source
    assert 'data-kaori-runtime-workspace-v8' in source
    assert "url_for('integrations.kubernetes_runtime_refresh'" in source
    assert 'hx-target="#kubernetes-runtime-workspace"' in source
    assert 'hx-swap="outerHTML"' in source
    assert 'data-kaori-runtime-main-layout' in source
    assert 'data-kaori-runtime-decision-summary' in source
    assert 'data-kaori-runtime-evidence-workspace' in source


def test_runtime_workspace_copied_shell_debt_is_burned_down() -> None:
    payload = json.loads(BASELINE_PATH.read_text(encoding='utf-8'))
    relative = TARGET_PATH.relative_to(ROOT).as_posix()

    assert relative not in payload['files']
