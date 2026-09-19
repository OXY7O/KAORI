from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
GENERATED_REPORT_DETAIL = ROOT / 'app' / 'templates' / 'reports' / 'generated' / 'detail.html'
BASELINE_PATH = ROOT / 'docs' / 'architecture' / 'ui-style-debt-baseline.json'
SEMANTIC_BORDER = re.compile(
    r'\bborder-status-'
    r'(?:normal|warning|critical|info|unknown|disabled|pending|maintenance)-'
    r'border\b'
)


def test_generated_report_detail_uses_shared_artifact_state_border_authority() -> None:
    source = GENERATED_REPORT_DETAIL.read_text(encoding='utf-8')

    assert '{% import "components/operational_callout.html" as operational_callout %}' in source
    assert source.count("operational_callout.semantic_border_classes('warning')") == 3
    assert source.count("operational_callout.semantic_border_classes('critical')") == 1
    assert SEMANTIC_BORDER.findall(source) == []

    for marker in (
        'data-generated-detail-storage-notice="true"',
        'data-generated-detail-missing-artifact="true"',
        'data-generated-detail-archived-artifact-missing="true"',
        'data-generated-detail-generation-note="true"',
    ):
        assert marker in source

    assert 'payload.report.can_download_artifact' in source
    assert 'payload.report.can_restore_report' in source
    assert 'can_manage_storage' in source
    assert 'dialog[open]' in source
    assert 'payload.job_execution' in source


def test_generated_report_detail_semantic_border_debt_is_burned_down() -> None:
    payload = json.loads(BASELINE_PATH.read_text(encoding='utf-8'))
    relative = GENERATED_REPORT_DETAIL.relative_to(ROOT).as_posix()

    assert relative not in payload['files']
