from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TARGET_PATH = ROOT / 'app' / 'templates' / 'components' / 'operational_workflow_catalog.html'
BASELINE_PATH = ROOT / 'docs' / 'architecture' / 'ui-style-debt-baseline.json'
COPIED_SHELL = 'overflow-hidden rounded-xl border border-outline-default bg-surface-card shadow-sm'
SHARED_SHELL = '{{ table_ui.block_classes() }}'


def test_operational_workflow_catalog_uses_shared_surface_shell_authority() -> None:
    source = TARGET_PATH.read_text(encoding='utf-8')

    assert '{% import "components/table_primitives.html" as table_ui %}' in source
    assert SHARED_SHELL in source
    assert COPIED_SHELL not in source

    assert "{% macro render(title, description, eyebrow='Operational Workflow Catalog', aria_label=None) -%}" in source
    assert 'aria-label="{{ aria_label or title }}"' in source
    assert '{{ eyebrow }}' in source
    assert '{{ title }}' in source
    assert '{{ description }}' in source
    assert '<div class="border-t border-outline-subtle">{{ caller() }}</div>' in source


def test_operational_workflow_catalog_copied_shell_debt_is_burned_down() -> None:
    payload = json.loads(BASELINE_PATH.read_text(encoding='utf-8'))
    relative = TARGET_PATH.relative_to(ROOT).as_posix()

    assert relative not in payload['files']
