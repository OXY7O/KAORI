from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding='utf-8')


def test_pod_inventory_posture_copy_uses_canonical_sentence_case() -> None:
    source = read('app/templates/inventory/pods/partials/_summary_cards.html')

    assert 'Pod Runtime Posture' in source
    assert 'Lifecycle exceptions, completion evidence, restart activity, and image diversity' in source
    assert 'Pods In The Current Result' not in source
    assert 'Running Coverage' not in source


def test_pod_inventory_footer_uses_resource_aware_count_and_rows_label() -> None:
    source = read('app/templates/inventory/pods/partials/_table_content.html')

    assert "'Pod' if pagination.total_items == 1 else 'Pods'" in source
    assert 'for="pods-per-page"' in source
    assert '>Rows</label>' in source
    assert 'hx-target="#pods-inventory-scope"' in source
    assert 'value="inventory_scope"' in source


def test_pod_detail_uses_canonical_section_names_and_operational_context() -> None:
    source = read('app/templates/inventory/pods/partials/_pod_detail_content.html')

    assert 'Placement & Network' in source
    assert 'Pod Specification' in source
    assert 'Container Runtime' in read('app/templates/components/container_runtime_collection.html')
    assert 'Volumes & Resource References' in source
    assert 'Technical Metadata' not in source
    assert 'Committed Snapshot Boundary' in source
    assert 'pod.operational_context.title' in source
