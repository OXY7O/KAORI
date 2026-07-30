from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_canonical_styling_guide_and_component_contracts_exist() -> None:
    guide = _read('docs/design/KAORI_STYLING_GUIDE.md')
    design_readme = _read('docs/design/README.md')

    assert '# KAORI Styling Guide' in guide
    assert 'Non-Negotiable DRY Contract' in guide
    assert 'Font Hierarchy' in guide
    assert 'Hero Standard' in guide
    assert 'Pagination Standard' in guide
    assert 'Right-Side Context Boxes' in guide
    assert 'Label Standard' in guide
    assert 'View More Content' in guide
    assert 'Table Standard' in guide
    assert 'KAORI_STYLING_GUIDE.md' in design_readme
    assert 'components/RIGHT_CONTEXT_RAIL.md' in design_readme
    assert 'components/VIEW_MORE_CONTENT.md' in design_readme


def test_standard_labels_are_borderless_and_special_label_is_explicit() -> None:
    source = _read('app/templates/components/table_label.html')
    status = source.split('{% macro status_label', 1)[1].split('{%- endmacro %}', 1)[0]
    indicator = source.split('{% macro status_indicator_label', 1)[1].split('{%- endmacro %}', 1)[0]
    special = source.split('{% macro special_label', 1)[1].split('{%- endmacro %}', 1)[0]
    metadata = source.split('{% macro metadata_label', 1)[1].split('{%- endmacro %}', 1)[0]

    assert ' rounded-md ' in status
    assert ' border ' not in status
    assert ' rounded-full ' not in status
    assert ' rounded-md ' in indicator
    assert ' border ' not in indicator
    assert 'rounded-full' in indicator
    assert 'kaori-special-label' in special
    assert ' rounded-md border ' in special
    assert 'data-lucide="{{ icon }}"' in special
    assert ' border ' not in metadata


def test_right_context_rail_owns_the_standard_grid() -> None:
    source = _read('app/templates/components/context_rail.html')
    contract = _read('docs/design/components/RIGHT_CONTEXT_RAIL.md')

    assert 'xl:grid-cols-[minmax(0,1fr)_20rem]' in source
    assert 'space-y-4' in source
    assert 'components/context_rail.html' in contract
    assert 'Do not copy' in contract


def test_expandable_guidance_reuses_the_shared_view_more_shell() -> None:
    shared = _read('app/templates/components/view_more_content.html')
    information = _read('app/templates/components/information_guide_card.html')
    guidance = _read('app/templates/components/context_guidance_card.html')

    assert 'macro render' in shared
    assert 'View Details' in shared
    assert 'Collapse' in shared
    assert '{% import "components/view_more_content.html" as view_more_content %}' in information
    assert '{% call view_more_content.render(' in information
    assert '{% import "components/view_more_content.html" as view_more_content %}' in guidance
    assert '{% call view_more_content.render(' in guidance


def test_style_drift_verifier_matches_the_committed_baseline() -> None:
    module_path = ROOT / 'scripts' / 'verify_ui_style.py'
    spec = importlib.util.spec_from_file_location('verify_ui_style', module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    errors = module.validate(
        ROOT,
        ROOT / 'docs' / 'architecture' / 'ui-style-debt-baseline.json',
    )
    assert errors == []


def test_static_quality_gate_runs_the_style_drift_verifier() -> None:
    quality_gate = _read('scripts/quality_gate.sh')
    assert 'python scripts/verify_ui_reuse.py' in quality_gate
    assert 'python scripts/verify_ui_style.py' in quality_gate
