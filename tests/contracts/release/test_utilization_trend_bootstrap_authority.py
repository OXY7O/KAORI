from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE_PATH = ROOT / 'app' / 'templates' / 'kubernetes' / 'analytics' / 'utilization' / 'partials' / '_trend.html'
RUNTIME_PATH = ROOT / 'app' / 'static' / 'js' / 'kubernetes' / 'analytics' / 'utilization.js'
BASELINE_PATH = ROOT / 'docs' / 'architecture' / 'ui-inline-debt-baseline.json'


def test_utilization_trend_uses_inert_json_bootstrap() -> None:
    template = TEMPLATE_PATH.read_text(encoding='utf-8')

    assert '<template' in template
    assert '</template>' in template
    assert 'data-utilization-trend-data' in template
    assert 'data-kaori-json-payload' in template
    assert '<script type="application/json" data-utilization-trend-data>' not in template
    assert "'trend_hours': trend_hours" in template
    assert "'cpu': trends.cpu|default([])" in template
    assert "'memory': trends.memory|default([])" in template
    assert "'pods': trends.pods|default([])" in template


def test_utilization_runtime_reads_template_content_with_element_fallback() -> None:
    runtime = RUNTIME_PATH.read_text(encoding='utf-8')

    assert 'source.content?.textContent ?? source.textContent' in runtime
    assert "JSON.parse(payload || '{}')" in runtime


def test_utilization_trend_is_removed_from_inline_debt_ledger() -> None:
    payload = json.loads(BASELINE_PATH.read_text(encoding='utf-8'))
    relative = TEMPLATE_PATH.relative_to(ROOT).as_posix()

    assert relative not in payload['files']
