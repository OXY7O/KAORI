from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_engineering_standard_is_release_enforced() -> None:
    result = subprocess.run(
        [sys.executable, 'scripts/verify_engineering_standard.py'],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert 'KAORI Engineering Standard v1 passed' in result.stdout


def test_engineering_standard_registers_all_user_facing_review_families() -> None:
    standard = (ROOT / 'docs' / 'standards' / 'KAORI_ENGINEERING_STANDARD_V1.md').read_text(encoding='utf-8')

    for token in (
        'KAORI Bright Violet',
        'Action Icon Box',
        'Context Icon Box',
        'Status Badge Box',
        'default Rows = 5',
        'Rows options = 5 / 10 / 25 / 50',
        'Right-side content rail',
        'Tab Style 1',
        'Tab Style 2',
        'Tab Style 3',
        'View Details / inline expand',
        'Modal',
        'Drawer',
        'self-dismissing toasts',
        'Notification Center',
        'Quick Actions, Notification Deck, Account menu',
        'Per-page final recheck checklist',
    ):
        assert token in standard
