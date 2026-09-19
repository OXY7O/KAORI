from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE_PATH = ROOT / 'app' / 'templates' / 'kubernetes' / 'inventory' / 'topology' / 'index.html'
RUNTIME_PATH = ROOT / 'app' / 'static' / 'js' / 'kubernetes' / 'inventory' / 'topology.js'
BASELINE_PATH = ROOT / 'docs' / 'architecture' / 'ui-inline-debt-baseline.json'


def test_topology_configuration_uses_inert_json_bootstrap() -> None:
    template = TEMPLATE_PATH.read_text(encoding='utf-8')

    assert '<template' in template
    assert '</template>' in template
    assert 'id="topology-config-data"' in template
    assert 'data-kaori-json-payload' in template
    assert 'window.KAORI_TOPOLOGY' not in template
    for key in ('data_url', 'renderer_url', 'initial_graph', 'namespace_map', 'filters'):
        assert f"'{key}'" in template


def test_topology_runtime_parses_dom_configuration_fail_closed() -> None:
    runtime = RUNTIME_PATH.read_text(encoding='utf-8')

    assert "document.getElementById('topology-config-data')" in runtime
    assert 'configNode.content?.textContent ?? configNode.textContent' in runtime
    assert 'JSON.parse' in runtime
    assert 'const config = window.KAORI_TOPOLOGY' not in runtime
    assert 'window.KAORI_TOPOLOGY =' not in runtime
    assert 'window.KAORI_TOPOLOGY_LIBRARY_VERSION' in runtime
    assert 'KAORI topology configuration is unavailable.' in runtime
    assert 'KAORI topology configuration is invalid.' in runtime


def test_topology_index_is_removed_from_inline_debt_ledger() -> None:
    payload = json.loads(BASELINE_PATH.read_text(encoding='utf-8'))
    relative = TEMPLATE_PATH.relative_to(ROOT).as_posix()

    assert relative not in payload['files']
