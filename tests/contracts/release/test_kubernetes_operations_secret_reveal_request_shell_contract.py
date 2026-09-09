from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TARGET_PATH = (
    ROOT
    / 'app'
    / 'templates'
    / 'kubernetes'
    / 'operations'
    / 'secrets'
    / '_reveal_request_form.html'
)
BASELINE_PATH = ROOT / 'docs' / 'architecture' / 'ui-style-debt-baseline.json'
COPIED_SHELL = (
    'overflow-hidden rounded-xl border border-outline-default '
    'bg-surface-card shadow-sm'
)
SHARED_SHELL = 'class="{{ table_ui.block_classes() }}"'


def test_secret_reveal_request_uses_shared_shell_authority() -> None:
    source = TARGET_PATH.read_text(encoding='utf-8')

    assert '{% import "components/table_primitives.html" as table_ui %}' in source
    assert SHARED_SHELL in source
    assert COPIED_SHELL not in source

    assert 'id="reveal-request-form"' in source
    assert "request_secret_reveal" in source
    assert 'name="csrf_token"' in source
    assert 'name="cluster_id"' in source
    assert 'name="namespace"' in source
    assert 'name="secret_name"' in source
    assert 'name="key_name"' in source
    assert 'name="ticket_reference"' in source
    assert 'name="reason"' in source
    assert 'data-operation-submit' in source
    assert 'Submitting request...' in source
    assert 'No Secret value is rendered or persisted by KAORI.' in source
    assert 'This live Secret currently has no revealable key names.' in source
    assert 'Select a Secret Target' in source


def test_secret_reveal_request_copied_shell_debt_is_burned_down() -> None:
    payload = json.loads(BASELINE_PATH.read_text(encoding='utf-8'))
    relative = TARGET_PATH.relative_to(ROOT).as_posix()

    assert relative not in payload['files']
