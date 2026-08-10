from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_hero_component_standard_is_enforced() -> None:
    result = subprocess.run(
        [sys.executable, 'scripts/verify_hero_component_standard.py'],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert 'KAORI Hero component standard passed' in result.stdout


def test_hero_documentation_has_one_global_contract_and_one_domain_extension() -> None:
    components = ROOT / 'docs' / 'design' / 'components'
    global_standard = (components / 'HERO.md').read_text(encoding='utf-8')
    analytics_extension = (components / 'ANALYTICS_HERO.md').read_text(encoding='utf-8')

    assert 'KAORI Hero Component Standard v1.3' in global_standard
    assert '16 px, regular, 28 px line height' in global_standard
    assert 'exactly two compact metrics' in global_standard
    assert 'kaori-hero-shell' in global_standard
    assert 'components/DARK_MODE.md' in global_standard
    assert 'Kubernetes Analytics Hero Extension' in analytics_extension
    assert not (components / 'ANALYTICS_HERO_STANDARD.md').exists()
    assert not (components / 'ANALYTICS_HERO_INVENTORY_REFERENCE.md').exists()


def test_removed_hero_macros_are_absent_from_implementation() -> None:
    source = (ROOT / 'app' / 'templates' / 'components' / 'page_hero.html').read_text(encoding='utf-8')
    for macro in (
        'context_posture_header',
        'context_posture_note',
        'context_bottom_notice',
        'action_group_classes',
        'secondary_action_classes',
        'destructive_action_classes',
        'supporting_strip',
    ):
        assert f'macro {macro}' not in source
