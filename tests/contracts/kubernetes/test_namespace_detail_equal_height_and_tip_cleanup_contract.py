from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding='utf-8')


def test_namespace_detail_uses_full_workspace_modal_grid():
    detail = _read('app/templates/inventory/kubernetes/namespaces/partials/_namespace_detail_content.html')
    shared_detail = _read('app/templates/components/details/_detail_content.html')

    assert 'data-kaori-detail-variant="full-workspace-modal"' in detail
    assert 'data-kaori-detail-density="adaptive-stacks"' in detail
    assert 'xl:grid-cols-[minmax(0,0.82fr)_minmax(0,1.18fr)]' in detail
    assert 'items-stretch' not in detail
    assert detail.count('stretch=false') >= 4
    assert 'stretch=true' in shared_detail
    assert "{{ 'h-full' if stretch else '' }}" in shared_detail
    assert 'xl:grid-cols-4' not in detail
    assert 'min-h-96' not in detail
    assert 'min-h-[28rem]' not in detail
    for title in ('Namespace Identity', 'Object Composition', 'Access & Security'):
        assert f"detail.detail_card('{title}'" in detail


def test_namespace_detail_uses_shared_empty_evidence_and_operational_context():
    detail = _read('app/templates/inventory/kubernetes/namespaces/partials/_namespace_detail_content.html')
    assert 'detail.empty_evidence(' in detail
    assert 'Committed Snapshot Boundary' in detail
    assert 'namespace.operational_context.title' in detail
    assert 'No Implicit Compliance' not in detail
    assert 'does not automatically indicate a compliance failure' in detail
