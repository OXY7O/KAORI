from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_namespace_detail_uses_inline_expanded_detail_grid():
    detail = _read("app/templates/inventory/namespaces/partials/_namespace_detail_content.html")
    shared_detail = _read("app/templates/components/details/_detail_content.html")

    assert 'data-kaori-detail-variant="inline-expanded"' in detail
    assert "grid items-stretch gap-4 p-5 md:grid-cols-2 2xl:grid-cols-3" in detail
    assert 'class="flex h-full flex-col rounded-xl' in shared_detail
    assert "xl:grid-cols-4" not in detail
    assert "min-h-96" not in detail
    assert "min-h-[28rem]" not in detail
    for title in ("Namespace Identity", "Object Composition", "Access & Security"):
        assert f"detail.detail_card('{title}'" in detail


def test_namespace_detail_uses_shared_empty_evidence_and_operational_context():
    detail = _read("app/templates/inventory/namespaces/partials/_namespace_detail_content.html")
    assert "detail.empty_evidence(" in detail
    assert "Committed Snapshot Boundary" in detail
    assert "namespace.operational_context.title" in detail
    assert "No Implicit Compliance" not in detail
    assert "does not automatically indicate a compliance failure" in detail
