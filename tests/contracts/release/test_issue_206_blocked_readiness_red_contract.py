from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_shared_blocked_hero_renderer_exists() -> None:
    source = (ROOT / 'app' / 'templates' / 'components' / 'page_hero.html').read_text(encoding='utf-8')

    assert 'macro blocked_context_body(' in source
