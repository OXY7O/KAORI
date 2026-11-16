"""#4777: Workload Mapping modal reuses KAORI committed evidence chrome."""

from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[3]
WORKLOAD = ROOT / 'app/templates/kubernetes/analytics/workload/partials'
SHARED_MODAL = ROOT / 'app/templates/kubernetes/analytics/components/_record_detail_modal.html'


def read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def test_mapping_detail_uses_existing_readonly_evidence_modal_header_footer() -> None:
    source = read(WORKLOAD / '_workload_mapping_section.html')
    modal = read(SHARED_MODAL)
    Environment(autoescape=True).parse(source)
    Environment(autoescape=True).parse(modal)

    assert 'record_detail_modal.render(' in source
    assert "'workload-mapping-modal-' ~ loop.index" in source
    assert "size='workspace'" in source
    assert 'evidence_context=true' in source
    assert (
        "context_facts=[('Type', row.type), ('Namespace', row.namespace), ('Pods', row.detail.pods|length)]"
    ) in source
    assert "'Review committed request, limit, and selected-window usage evidence.'" in source
    assert 'Committed Snapshot' in modal
    assert 'Evidence Source · Read Only' in modal
    assert 'role="dialog"' in modal
    assert 'aria-modal="true"' in modal
    assert '@keydown.escape.window="detailOpen = false"' in modal
    assert 'detailOpen = false' in modal
    assert 'x-teleport=' in modal


def test_mapping_interpretation_occupies_its_own_full_width_guidance_surface() -> None:
    source = read(WORKLOAD / '_workload_mapping_section.html')
    Environment(autoescape=True).parse(source)

    assert 'Evidence Boundary and Request Fit Interpretation' in source
    assert 'md:grid-cols-3 md:divide-x md:divide-y-0' in source
    assert 'row.metrics_coverage.description' in source
    assert 'row.metrics_coverage.label' in source
    assert 'How To Read The Bars' in source
    assert 'Current vs Selected-Window Peak' in source
    assert 'Current Usage is the latest committed reading' in source
    assert 'upper-bound signal' in source
    for label in ('Below 75%', '75% To 90%', 'Above 90%'):
        assert label in source
    assert 'lg:grid-cols-[minmax(0,1.15fr)_minmax(0,0.85fr)]' not in source
    assert 'Current Request Utilization' in source
    assert 'Peak Request Utilization' in source
    assert "analysis_surface.interpretation_callout('Recommended Action'" in source
    assert 'row.risk.tone' in source


def test_pod_membership_is_compact_full_width_list_with_unavailable_state() -> None:
    source = read(WORKLOAD / '_workload_mapping_section.html')
    assert 'Pod Membership' in source
    assert '<ul class="flex max-h-44 flex-wrap gap-2 overflow-y-auto pr-1"' in source
    assert 'aria-label="Pods in {{ row.workload }}"' in source
    assert 'for pod in row.detail.pods' in source
    assert 'row.detail.pods|length' in source
    assert '[overflow-wrap:anywhere]' in source
    assert 'No Pod Evidence in the committed workload snapshot.' in source
    assert 'record_filter.form(' in source
    assert "evidence_list.shell('Workload Resource Mapping Records', embedded=true)" in source
