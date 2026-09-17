from __future__ import annotations

import json
from pathlib import Path

from scripts import verify_ui_style

ROOT = Path(__file__).resolve().parents[3]
SIDEBAR_PATH = ROOT / 'app' / 'templates' / 'components' / 'navigation' / 'sidebar.html'
BASELINE_PATH = ROOT / 'docs' / 'architecture' / 'ui-style-debt-baseline.json'
RELATIVE = SIDEBAR_PATH.relative_to(ROOT).as_posix()


def test_sidebar_locked_typography_is_explicit_style_authority() -> None:
    assert RELATIVE in verify_ui_style._APPROVED_FONT_EXTRABOLD_COMPONENTS
    assert RELATIVE in verify_ui_style._APPROVED_CUSTOM_HERO_COMPONENTS


def test_sidebar_locked_typography_is_not_global_style_debt() -> None:
    source = SIDEBAR_PATH.read_text(encoding='utf-8')
    metrics = verify_ui_style._metrics(RELATIVE, source)

    assert metrics['font_extrabold_utilities'] == 0
    assert metrics['custom_hero_titles'] == 0
    assert 'text-sm font-extrabold leading-5' in source
    assert source.count('text-xs font-extrabold uppercase tracking-widest') >= 1


def test_sidebar_is_removed_from_style_debt_ledger() -> None:
    payload = json.loads(BASELINE_PATH.read_text(encoding='utf-8'))

    assert RELATIVE not in payload['files']
