from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.contract

ROOT = Path(__file__).resolve().parents[3]


def test_runtime_repository_uses_canonical_pagination_contract() -> None:
    path = ROOT / 'app/integrations/runtime/repository.py'
    source = path.read_text(encoding='utf-8')
    tree = ast.parse(source, filename=str(path))
    imports = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }

    assert 'app.common.pagination' in imports
    assert 'build_pagination_window(' in source
    assert '.limit(window.per_page)' in source
    assert '.limit(per_page + 1)' not in source
