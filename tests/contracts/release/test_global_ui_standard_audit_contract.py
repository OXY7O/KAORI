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

EXPECTED_RESIDUAL_DEBT = {
    'style_drift_candidates': {
        'baseline': 'docs/architecture/ui-style-debt-baseline.json',
        'verifier': 'scripts/verify_ui_style.py',
    },
    'inline_template_debt': {
        'baseline': 'docs/architecture/ui-inline-debt-baseline.json',
        'verifier': 'scripts/verify_ui_reuse.py',
    },
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

    residual_debt = payload['residual_debt']
    assert set(residual_debt) == set(EXPECTED_RESIDUAL_DEBT)
    for key, expected in EXPECTED_RESIDUAL_DEBT.items():
        entry = residual_debt[key]
        assert entry['baseline'] == expected['baseline']
        assert entry['verifier'] == expected['verifier']
        _assert_paths_exist([entry['baseline'], entry['verifier']], context=f'residual debt {key}')
        assert entry['disposition'] == 'bounded_existing_debt'
        assert entry['tracking_issue'] == 223
        assert entry['no_silent_acceptance'] is True
        assert entry['policy'] == 'must_not_increase; decreases require baseline update in the same change'

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


def test_table_label_is_the_canonical_semantic_border_authority() -> None:
    verifier = runpy.run_path(str(ROOT / 'scripts' / 'verify_ui_style.py'))
    table_label_path = 'app/templates/components/table_label.html'
    approved = verifier['_APPROVED_SEMANTIC_BORDER_COMPONENTS']
    assert table_label_path in approved, (
        'table_label.tone_border_classes() is the shared semantic-border authority and must not be '
        'reported as page-local UI debt.'
    )

    table_label_source = (ROOT / table_label_path).read_text(encoding='utf-8')
    assert '{% macro tone_border_classes(tone)' in table_label_source
    for token in (
        'border-status-normal-border',
        'border-status-warning-border',
        'border-status-critical-border',
        'border-status-unknown-border',
        'border-status-info-border',
    ):
        assert token in table_label_source

    baseline = json.loads((ROOT / 'docs' / 'architecture' / 'ui-style-debt-baseline.json').read_text(encoding='utf-8'))
    assert 'semantic_border_utilities' not in baseline['files'].get(table_label_path, {})

    page_local_metrics = verifier['_metrics'](
        'app/templates/example_page.html',
        '<div class="border-status-warning-border"></div>',
    )
    assert page_local_metrics['semantic_border_utilities'] == 1, (
        'canonical ownership must not weaken semantic-border drift detection for page-local templates'
    )
