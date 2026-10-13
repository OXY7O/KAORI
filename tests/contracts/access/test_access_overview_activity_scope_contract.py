from __future__ import annotations

import ast
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[3]


def _supporting_text(attention_count: int) -> str:
    source = ast.parse((ROOT / 'app/access/overview/presentation.py').read_text(encoding='utf-8'))
    function = next(
        node for node in source.body if isinstance(node, ast.FunctionDef) and node.name == '_activity_supporting_text'
    )
    namespace: dict[str, Any] = {'Any': Any}
    exec(compile(ast.Module(body=[function], type_ignores=[]), '<access-evidence>', 'exec'), namespace)
    helper = cast(Callable[[dict[str, int]], str], namespace['_activity_supporting_text'])
    return helper({'attention_24h': attention_count})


def test_zero_notification_attention_never_claims_universal_evidence_absence() -> None:
    wording = _supporting_text(0)
    assert 'Notification-backed Activity Register' in wording
    assert 'last 24 hours' in wording
    assert 'other administrative evidence sources remain separate' in wording
    assert 'No warning/error administrative evidence was recorded' not in wording


def test_positive_notification_attention_names_its_source_and_time_window() -> None:
    wording = _supporting_text(3)
    assert '3 warning/error event(s)' in wording
    assert 'Notification-backed Activity Register' in wording
    assert 'last 24 hours' in wording


def test_overview_does_not_redefine_or_union_activity_sources() -> None:
    presentation = (ROOT / 'app/access/overview/presentation.py').read_text(encoding='utf-8')
    assert 'get_activity_audit_summary()' in presentation
    assert 'System-wide administrative and authentication evidence.' not in presentation
    assert 'other sources remain separate.' in presentation
