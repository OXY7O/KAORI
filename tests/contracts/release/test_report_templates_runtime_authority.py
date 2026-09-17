from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE_PATH = ROOT / 'app' / 'templates' / 'reports' / 'report_templates' / 'index.html'
RUNTIME_PATH = ROOT / 'app' / 'static' / 'js' / 'reports' / 'report_templates.js'
BASELINE_PATH = ROOT / 'docs' / 'architecture' / 'ui-inline-debt-baseline.json'


def test_report_templates_use_inert_json_and_static_runtime_authority() -> None:
    template = TEMPLATE_PATH.read_text(encoding='utf-8')

    assert 'id="report-templates-config-data"' in template
    assert 'data-kaori-json-payload' in template
    assert 'payload.default_sections_by_report_type | tojson' in template
    assert 'payload.allowed_formats_by_report_type | tojson' in template
    assert "filename='js/reports/report_templates.js'" in template
    assert 'const defaults =' not in template
    assert 'const allowedFormats =' not in template
    assert '(() => {' not in template


def test_report_templates_static_runtime_preserves_form_and_htmx_contract() -> None:
    assert RUNTIME_PATH.exists()

    runtime = RUNTIME_PATH.read_text(encoding='utf-8')

    assert "document.getElementById('report-templates-config-data')" in runtime
    assert 'configNode.content?.textContent ?? configNode.textContent' in runtime
    assert 'JSON.parse' in runtime
    assert "document.querySelector('[data-template-form]')" in runtime
    assert "form.dataset.initialized === 'true'" in runtime
    assert "form.dataset.initialized = 'true'" in runtime
    assert "'[data-template-report-type]'" in runtime
    assert "'[data-template-output-format]'" in runtime
    assert "'[data-template-reset-sections]'" in runtime
    assert "'[data-template-section-error]'" in runtime
    assert "'DOMContentLoaded'" in runtime
    assert "'htmx:afterSwap'" in runtime
    assert "event.detail?.target?.id === 'templates-registry'" in runtime


def test_report_templates_index_is_removed_from_inline_debt_ledger() -> None:
    payload = json.loads(BASELINE_PATH.read_text(encoding='utf-8'))
    relative = TEMPLATE_PATH.relative_to(ROOT).as_posix()

    assert relative not in payload['files']
