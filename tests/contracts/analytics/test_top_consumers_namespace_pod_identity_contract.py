from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = ROOT / "app/templates/analytics/top_consumers/partials/_consumer_detail_results.html"


def test_consumer_detail_namespace_column_contains_namespace_and_pod_identity():
    content = TEMPLATE.read_text(encoding="utf-8")

    assert 'data-lucide="boxes"' in content
    assert "{{ row.namespace }}" in content
    assert "{{ row.pod|default('—', true) }}" in content
    assert 'class="mt-1 flex min-w-0 items-start gap-3 lg:mt-0"' in content
    assert 'class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-kaori-soft text-kaori-primary"' in content


def test_namespace_pod_identity_uses_one_icon_for_both_lines():
    content = TEMPLATE.read_text(encoding="utf-8")
    namespace_block = content.split('lg:col-span-3">', 1)[1].split('</div>\n                                <div class="min-w-0 lg:col-span-4">', 1)[0]

    assert namespace_block.count('data-lucide=') == 1
    assert '<p class="break-words text-sm font-semibold text-content-primary">{{ row.namespace }}</p>' in namespace_block
    assert '<p class="mt-0.5 break-all text-xs leading-5 text-content-muted">{{ row.pod|default(\'—\', true) }}</p>' in namespace_block
