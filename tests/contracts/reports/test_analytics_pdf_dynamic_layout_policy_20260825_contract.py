from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / 'app/reports/export/html_pdf/publication_layout.py'


def _load_layout_module():
    spec = importlib.util.spec_from_file_location('kaori_publication_layout', MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_layout_contract_publishes_dynamic_content_policy() -> None:
    standard = read('app/reports/export/html_pdf/analytics_publication_standard.py')
    for token in (
        "'dynamic_page_policy': 'content-budgeted'",
        "'section_continuation_policy': 'same-section-only'",
        "'table_overflow_policy': 'chunk-with-repeated-header'",
        "'reference_layout_policy': 'two-column-or-stack'",
        "'typography_scaling_policy': 'never-for-density'",
        "'dynamic_pair_policy': 'density-selects-50-50-or-stack'",
    ):
        assert token in standard


def test_pair_layout_switches_to_stack_for_dense_peer_content() -> None:
    layout = _load_layout_module()
    assert layout.choose_pair_mode(left_chars=180, right_chars=190, left_rows=2, right_rows=2) == 'split'
    assert layout.choose_pair_mode(left_chars=720, right_chars=180, left_rows=8, right_rows=2) == 'stack'
    assert layout.choose_pair_mode(left_chars=350, right_chars=410, left_rows=8, right_rows=8) == 'stack'


def test_reference_layout_switches_to_single_column_for_long_or_many_identities() -> None:
    layout = _load_layout_module()
    short = [{'identity': 'pod-a'}, {'identity': 'pod-b'}, {'identity': 'pod-c'}]
    long = [{'identity': 'prometheus-prometheus-kube-prometheus-prometheus-0'}]
    many = [{'identity': f'pod-{index}'} for index in range(8)]

    assert layout.choose_reference_columns(short) == 2
    assert layout.choose_reference_columns(long) == 1
    assert layout.choose_reference_columns(many) == 1


def test_row_pagination_preserves_order_and_marks_continuation() -> None:
    layout = _load_layout_module()
    rows = list(range(13))
    chunks = layout.paginate_rows(rows, first_page_capacity=5, continuation_capacity=4)

    assert [chunk.items for chunk in chunks] == [list(range(5)), list(range(5, 9)), list(range(9, 13))]
    assert [chunk.continuation for chunk in chunks] == [False, True, True]


def test_page_budget_never_consumes_footer_safety_zone() -> None:
    layout = _load_layout_module()
    assert layout.block_fits(remaining_mm=60, estimated_block_mm=40)
    assert not layout.block_fits(remaining_mm=55, estimated_block_mm=40)


def test_shared_css_exposes_adaptive_pair_and_continuation_contract() -> None:
    css = ''.join(read('app/static/reports/pdf/analytics_publication.css').split())
    assert '.publication-pair.is-stacked' in css
    assert 'grid-template-columns:minmax(0,1fr)!important' in css
    assert '.publication-continuation' in css
    assert '.publication-continuation-page' in css
    continuation_block = css.split('.publication-continuation{', 1)[1].split('}', 1)[0]
    assert 'break-before:page' not in continuation_block
    continuation_page_block = css.split('.publication-continuation-page{', 1)[1].split('}', 1)[0]
    assert 'break-before:page' in continuation_page_block
    assert '.publication-visual' in css
    assert 'overflow:hidden' in css


def test_shared_component_exposes_dynamic_publication_primitives() -> None:
    component = read('app/templates/reports/pdf/components/analytics_publication.html')
    assert 'macro adaptive_pair' in component
    assert 'publication-pair' in component
    assert 'macro continuation_heading' in component
    assert 'publication-continuation' in component


def test_every_two_column_template_uses_publication_pair_contract() -> None:
    offenders: list[str] = []
    for path in sorted((ROOT / 'app/templates/reports/pdf').glob('*.html')):
        source = path.read_text(encoding='utf-8')
        for class_value in __import__('re').findall(r'class="([^"]*\btwo-column\b[^"]*)"', source):
            if 'publication-pair' not in class_value.split():
                offenders.append(f'{path.name}: {class_value}')
    assert not offenders, 'Raw two-column layout bypasses the global pair contract:\n' + '\n'.join(offenders)


def test_report_specific_css_does_not_own_peer_column_ratios() -> None:
    offenders: list[str] = []
    block_pattern = __import__('re').compile(r'([^{}]+)\{([^{}]*)\}', __import__('re').S)
    for path in sorted((ROOT / 'app/static/reports/pdf').glob('*.css')):
        if path.name == 'analytics_publication.css':
            continue
        source = path.read_text(encoding='utf-8')
        for selector, declarations in block_pattern.findall(source):
            if '-split' not in selector:
                continue
            if 'grid-template-columns' in declarations:
                offenders.append(f'{path.name}: {" ".join(selector.split())}')
    assert not offenders, 'Peer column ratios must be owned by shared publication CSS:\n' + '\n'.join(offenders)


def test_publication_verifier_and_docs_enforce_dynamic_layout_policy() -> None:
    verifier = read('scripts/verify_analytics_pdf_publication.py')
    docs = read('docs/reports/kaori-analytics-pdf-publication-standard-v3.md')

    for token in (
        'dynamic_page_policy',
        'section_continuation_policy',
        'table_overflow_policy',
        'reference_layout_policy',
        'typography_scaling_policy',
        'dynamic_pair_policy',
        'publication-pair',
        'Peer column ratios must be owned by shared publication CSS',
    ):
        assert token in verifier

    assert 'Dynamic content and pagination' in docs
    assert 'Typography never shrinks to make dynamic content fit' in docs
    assert '50/50 or stack' in docs
    assert 'continuation page' in docs
    assert '18mm footer safety zone' in docs


def test_shared_reference_typography_has_distinct_hierarchy() -> None:
    css = ''.join(read('app/static/reports/pdf/analytics_publication.css').split())
    assert '--analytics-type-reference-title:7.1pt' in css
    assert '--analytics-type-reference-meta:6.15pt' in css
    assert '--analytics-type-reference-code:6.6pt' in css
    assert '.identity-title{font-size:var(--analytics-type-reference-title)!important' in css
    assert '.identity-meta{font-size:var(--analytics-type-reference-meta)!important' in css


def test_major_visuals_use_global_locked_box_utilities() -> None:
    css = ''.join(read('app/static/reports/pdf/analytics_publication.css').split())
    assert '.publication-visual.is-pair{' in css
    assert 'height:var(--analytics-visual-pair-height)!important' in css
    assert '.publication-visual.is-distribution{' in css
    assert 'height:var(--analytics-visual-distribution-height)!important' in css
    assert '.publication-visual.is-wide{' in css
    assert 'height:var(--analytics-visual-wide-height)!important' in css
    assert '.publication-visual>svg{' in css
    assert 'height:100%!important' in css

    expected = {
        'resource_utilization.html': ('publication-visual is-pair', 'publication-visual is-distribution', 'publication-visual is-wide'),
        'capacity_analysis.html': ('publication-visual is-pair', 'publication-visual is-wide'),
        'storage_analysis.html': ('publication-visual is-pair', 'publication-visual is-wide'),
        'forecast_analysis.html': ('publication-visual is-pair', 'publication-visual is-wide'),
    }
    for filename, tokens in expected.items():
        source = read(f'app/templates/reports/pdf/{filename}')
        for token in tokens:
            assert token in source, f'{filename} missing {token}'


def test_report_css_does_not_own_locked_visual_heights() -> None:
    visual_tokens = (
        '.chart-frame',
        '.trend-chart-frame',
        '.forecast-chart-frame',
        '.storage-trend-frame',
        '.portfolio-chart',
        '.resource-chart',
        '.memory-concentration-card',
        '.cpu-concentration-card',
        '.node-card',
        '.persistent-volume-card',
    )
    import re
    offenders: list[str] = []
    block_pattern = re.compile(r'([^{}]+)\{([^{}]*)\}', re.S)
    for path in sorted((ROOT / 'app/static/reports/pdf').glob('*.css')):
        if path.name == 'analytics_publication.css':
            continue
        source = path.read_text(encoding='utf-8')
        for selector, declarations in block_pattern.findall(source):
            if not any(token in selector for token in visual_tokens):
                continue
            if re.search(r'(?<!-)\bheight\s*:|\bmin-height\s*:|\bmax-height\s*:', declarations):
                offenders.append(f'{path.name}: {" ".join(selector.split())}')
    assert not offenders, 'Locked visual heights must be owned by shared publication CSS:\n' + '\n'.join(offenders)


def test_renderer_exposes_dynamic_layout_helpers_to_templates() -> None:
    engine = read('app/reports/export/html_pdf/engine.py')
    assert 'choose_pair_mode' in engine
    assert 'choose_reference_columns' in engine
    assert 'paginate_rows' in engine
    assert 'publication_pair_mode=choose_pair_mode' in engine
    assert 'publication_reference_columns=choose_reference_columns' in engine
    assert 'publication_paginate_rows=paginate_rows' in engine


def test_identity_register_uses_dynamic_reference_column_policy() -> None:
    component = read('app/templates/reports/pdf/components/analytics_publication.html')
    assert 'publication_reference_columns(items)' in component
    assert "columns == 1" in component
