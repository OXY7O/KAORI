from __future__ import annotations

import json
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MATRIX_PATH = ROOT / 'docs' / 'architecture' / 'ui-standard-audit-matrix.json'

REQUIRED_CATEGORIES = {
    'hero',
    'layout_spacing',
    'cards_surfaces',
    'tables_status_labels',
    'forms',
    'modal_drawer',
    'typography',
    'loading_empty_error',
    'light_dark',
    'shared_component_ownership',
}

EXPECTED_DELEGATIONS = {
    'responsive_device_compatibility': 224,
    'functional_capability': 225,
    'navigation_interaction': 226,
    'accessibility_ux': 227,
    'runtime_error_behavior': 228,
}


def _assert_paths_exist(paths: list[str], *, context: str) -> None:
    assert paths, f'{context}: evidence paths must not be empty'
    missing = [path for path in paths if not (ROOT / path).exists()]
    assert not missing, f'{context}: missing evidence paths: {missing}'


def test_global_ui_standard_audit_matrix_is_fail_closed() -> None:
    assert MATRIX_PATH.exists(), (
        'Global UI audit matrix is missing; #223 requires every release surface and canonical UI category '
        'to have explicit evidence or disposition.'
    )

    payload = json.loads(MATRIX_PATH.read_text(encoding='utf-8'))
    assert payload['version'] == 1
    assert payload['source_registry'] == 'scripts/release_surface_registry.py'
    assert payload['delegated_workstreams'] == EXPECTED_DELEGATIONS
    assert set(payload['categories']) == REQUIRED_CATEGORIES

    for category, authority in payload['categories'].items():
        _assert_paths_exist(authority['standards'], context=f'category {category} standards')
        _assert_paths_exist(authority['evidence'], context=f'category {category} evidence')

    registry = runpy.run_path(str(ROOT / 'scripts' / 'release_surface_registry.py'))
    surfaces = {surface.key: surface for surface in registry['SURFACES']}
    matrix = payload['surfaces']
    assert set(matrix) == set(surfaces), (
        f'audit surface coverage must exactly match release authority; '
        f'missing={sorted(set(surfaces) - set(matrix))}, extra={sorted(set(matrix) - set(surfaces))}'
    )

    for key, surface in surfaces.items():
        entry = matrix[key]
        if key == 'health':
            assert entry['classification'] == 'system_non_ui'
            assert entry['reason'].strip()
            assert entry['delegated_concerns'] == {}
            continue

        assert entry['classification'] == 'ui', f'{key}: release-visible surface must be explicitly audited'
        assert entry['audit_state'] == 'inventory_ready', f'{key}: first #223 increment must remain an audit inventory'
        assert entry['delegated_concerns'] == EXPECTED_DELEGATIONS

        surface_evidence = entry['surface_evidence']
        _assert_paths_exist(surface_evidence['verifiers'], context=f'{key} verifiers')
        _assert_paths_exist(surface_evidence['contracts'], context=f'{key} contracts')
        assert set(surface.verifiers).issubset(surface_evidence['verifiers']), (
            f'{key}: matrix dropped release verifier authority {sorted(set(surface.verifiers) - set(surface_evidence["verifiers"]))}'
        )
        assert set(surface.contract_paths).issubset(surface_evidence['contracts']), (
            f'{key}: matrix dropped release contract authority '
            f'{sorted(set(surface.contract_paths) - set(surface_evidence["contracts"]))}'
        )
