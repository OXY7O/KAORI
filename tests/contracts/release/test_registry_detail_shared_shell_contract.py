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
    / '_registry_detail_content.html'
)
BASELINE_PATH = ROOT / 'docs' / 'architecture' / 'ui-style-debt-baseline.json'
COPIED_SHELL = 'overflow-hidden rounded-xl border border-outline-default bg-surface-card shadow-sm'
SHARED_SHELL = '{{ surface_ui.block_classes() }}'


def test_registry_detail_uses_shared_surface_shell_authority() -> None:
    source = TARGET_PATH.read_text(encoding='utf-8')

    assert '{% import "components/table_primitives.html" as surface_ui %}' in source
    assert f'class="{SHARED_SHELL}"' in source
    assert COPIED_SHELL not in source

    assert 'class="bg-surface-hover px-4 py-4"' in source
    assert 'readiness_tone' in source
    assert "url_for('metrics.instance_detail'" in source
    assert "url_for('alertmanager.instance_detail'" in source
    assert "current_user.has_permission('clusters.manage')" in source
    assert 'data-delete-url' in source
    assert "detail.detail_card('Connection identity'" in source
    assert "'Operational coverage'" in source
    assert "'Source bindings'" in source
    assert 'class="grid gap-4 p-5 md:grid-cols-2 xl:grid-cols-4"' in source


def test_registry_detail_surface_and_action_style_debt_is_fully_retired() -> None:
    source = TARGET_PATH.read_text(encoding='utf-8')
    payload = json.loads(BASELINE_PATH.read_text(encoding='utf-8'))
    relative = TARGET_PATH.relative_to(ROOT).as_posix()

    assert "table_label.tone_border_classes('normal')" in source
    assert "table_label.tone_border_classes('critical')" in source
    assert 'border-status-normal-border' not in source
    assert 'border-status-critical-border' not in source
    assert relative not in payload['files']
