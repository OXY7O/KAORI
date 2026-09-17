from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TARGET_PATH = ROOT / 'app' / 'templates' / 'integrations' / 'components' / '_workspace.html'
BASELINE_PATH = ROOT / 'docs' / 'architecture' / 'ui-style-debt-baseline.json'
VERIFIER_PATH = ROOT / 'scripts' / 'verify_ui_style.py'

SEMANTIC_BORDER_TOKENS = (
    'border-status-normal-border',
    'border-status-info-border',
    'border-status-warning-border',
    'border-status-critical-border',
    'border-status-unknown-border',
)


def test_integrations_workspace_owns_canonical_semantic_palette() -> None:
    source = TARGET_PATH.read_text(encoding='utf-8')

    assert 'macro palette_icon_classes' in source
    for token in SEMANTIC_BORDER_TOKENS:
        assert source.count(token) == 1


def test_integrations_workspace_shared_authority_is_not_style_debt() -> None:
    payload = json.loads(BASELINE_PATH.read_text(encoding='utf-8'))
    verifier = VERIFIER_PATH.read_text(encoding='utf-8')
    relative = TARGET_PATH.relative_to(ROOT).as_posix()

    assert relative not in payload['files']
    assert f"'{relative}'" in verifier
