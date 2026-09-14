from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MATRIX_PATH = ROOT / 'docs' / 'architecture' / 'functional-capability-audit-matrix.json'

INTEGRATIONS_KUBERNETES_RUNTIME_SECONDARY_EVIDENCE = {
    'async_job': 'tests/integrations/runtime/test_recovery.py',
    'failure_recovery': 'tests/integrations/runtime/test_recovery.py',
}


def _assert_paths_exist(paths: list[str], *, context: str) -> None:
    assert paths, f'{context}: evidence paths must not be empty'
    missing = [path for path in paths if not (ROOT / path).exists()]
    assert not missing, f'{context}: missing evidence paths: {missing}'


def test_integrations_kubernetes_runtime_secondary_behaviors_bind_narrow_executable_evidence() -> None:
    payload = json.loads(MATRIX_PATH.read_text(encoding='utf-8'))
    behaviors = payload['surfaces']['integrations']['capabilities']['kubernetes_provider']['behaviors']

    for behavior_key, evidence_path in INTEGRATIONS_KUBERNETES_RUNTIME_SECONDARY_EVIDENCE.items():
        behavior = behaviors[behavior_key]
        assert behavior['state'] == 'covered', f'integrations.kubernetes_provider.{behavior_key} must be covered'
        assert behavior['evidence'] == [evidence_path]
        _assert_paths_exist(
            behavior['evidence'],
            context=f'integrations.kubernetes_provider.{behavior_key}',
        )
