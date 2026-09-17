from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUNTIME_PATH = ROOT / 'app' / 'static' / 'js' / 'reports' / 'generate.js'


def test_reports_generate_runtime_avoids_direct_inner_html_assignment() -> None:
    runtime = RUNTIME_PATH.read_text(encoding='utf-8')

    assert '.innerHTML' not in runtime
    assert 'selectedSectionList.replaceChildren()' in runtime
    assert 'namespaceSelect.replaceChildren()' in runtime


def test_reports_generate_runtime_constructs_inventory_icon_with_dom_nodes() -> None:
    runtime = RUNTIME_PATH.read_text(encoding='utf-8')

    assert "const markerIcon = document.createElement('i')" in runtime
    assert "markerIcon.setAttribute('data-lucide', 'file-spreadsheet')" in runtime
    assert 'marker.appendChild(markerIcon)' in runtime
