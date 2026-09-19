from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TARGET_PATH = ROOT / 'app' / 'templates' / 'components' / 'action_button.html'
BASELINE_PATH = ROOT / 'docs' / 'architecture' / 'ui-style-debt-baseline.json'
VERIFIER_PATH = ROOT / 'scripts' / 'verify_ui_style.py'
DISABLED_BORDER = 'disabled:border-status-disabled-border'


def test_action_button_owns_canonical_disabled_border_semantics() -> None:
    source = TARGET_PATH.read_text(encoding='utf-8')

    assert source.count(DISABLED_BORDER) == 2
    assert "variant == 'primary'" in source
    assert 'border border-transparent bg-kaori-primary' in source
    assert 'border border-outline-default bg-surface-card' in source
    assert 'focus-visible:ring-outline-focus' in source
    assert 'disabled:bg-status-disabled-soft' in source
    assert 'disabled:text-status-disabled-text' in source


def test_action_button_shared_authority_is_not_style_debt() -> None:
    payload = json.loads(BASELINE_PATH.read_text(encoding='utf-8'))
    verifier = VERIFIER_PATH.read_text(encoding='utf-8')
    relative = TARGET_PATH.relative_to(ROOT).as_posix()

    assert relative not in payload['files']
    assert f"'{relative}'" in verifier
