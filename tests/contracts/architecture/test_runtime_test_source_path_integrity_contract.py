from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
VERIFIER = ROOT / 'scripts' / 'verify_test_source_paths.py'
QUALITY_GATE = ROOT / 'scripts' / 'quality_gate.sh'


def test_runtime_test_source_paths_are_part_of_the_static_quality_gate() -> None:
    assert VERIFIER.exists()
    assert 'python scripts/verify_test_source_paths.py' in QUALITY_GATE.read_text(encoding='utf-8')


def test_runtime_test_source_path_verifier_accepts_the_current_tree() -> None:
    spec = importlib.util.spec_from_file_location('verify_test_source_paths_contract', VERIFIER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module.main() == 0
