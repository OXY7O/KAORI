from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TEMPLATES = ROOT / 'app/templates'


def read(relative: str) -> str:
    return (ROOT / relative).read_text()


def test_inventory_modal_uses_wide_overflow_safe_workspace() -> None:
    modal = read('app/templates/components/resource_detail_modal.html')
    script = read('app/static/js/detail_rows.js')

    assert 'max-w-[100rem]' in modal
    assert 'overflow-x-hidden overflow-y-auto' in modal
    assert '[overflow-wrap:anywhere]' in modal
    assert 'resource-detail-modal-title" class="mt-0.5 truncate' not in modal
    assert 'mt-0.5 truncate text-lg' not in script
    assert 'break-words text-lg' in script


def test_inventory_technical_metadata_uses_readable_wrapping_columns() -> None:
    component = read('app/templates/components/technical_metadata_collection.html')

    assert 'sm:grid-cols-[minmax(10rem,0.42fr)_minmax(0,1fr)]' in component
    assert 'grid min-w-0 gap-x-10' in component
    assert 'sm:grid-cols-[minmax(7rem,0.34fr) _minmax(0,1fr)]' not in component
    assert 'text-sm font-normal leading-5 text-content-secondary' in component
    assert 'whitespace-pre-wrap' in component
    assert '[overflow-wrap:anywhere]' in component
    assert 'max-h-' not in component
    assert 'overflow-y-auto' not in component
    assert 'break-all text-xs font-semibold' not in component


def test_all_inventory_modal_details_avoid_truncated_resource_evidence() -> None:
    detail_templates = list((TEMPLATES / 'inventory').glob('*/partials/*detail*.html'))
    detail_templates.extend(
        [
            TEMPLATES / 'components/related_resource_collection.html',
            TEMPLATES / 'components/technical_metadata_collection.html',
        ]
    )

    assert detail_templates
    for template in detail_templates:
        source = template.read_text()
        assert ' truncate ' not in source, template


def test_pod_and_workload_tolerations_use_compact_pair_spacing() -> None:
    for relative in (
        'app/templates/kubernetes/inventory/pods/partials/_pod_detail_content.html',
        'app/templates/kubernetes/inventory/workloads/partials/_workload_detail_content.html',
    ):
        source = read(relative)
        assert 'Tolerations remain factual scheduling evidence until evaluated against an explicit policy.' in source
        assert 'compact_pairs=true' in source
