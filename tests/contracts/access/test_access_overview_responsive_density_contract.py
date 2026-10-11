from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_access_overview_hero_metadata_has_distinct_context_from_numeric_summary() -> None:
    template = (ROOT / 'app/templates/access/overview/index.html').read_text(encoding='utf-8')
    assert "page_hero.meta_label('layers', 'Domain-Owned Summaries')" in template
    assert "page_hero.meta_label('shield-check', 'Permission Scoped')" in template
    assert "page_hero.meta_label('history', 'Committed Evidence')" in template
    assert "access_overview.workspace_count ~ ' Workspaces'" not in template
    assert "access_overview.attention_workspace_count ~ ' Review'" not in template
    assert 'page_hero.context_metric(metric.icon, metric.label, metric.value, metric.description)' in template


def test_access_overview_metric_labels_are_readable_without_hover_only_titles() -> None:
    template = (ROOT / 'app/templates/access/overview/index.html').read_text(encoding='utf-8')
    assert 'grid-cols-1 divide-y' in template
    assert 'sm:grid-cols-3 sm:divide-x sm:divide-y-0' in template
    assert '<span class="min-w-0 break-words">{{ label }}</span>' in template
    assert '<span class="truncate" title="{{ label }}">{{ label }}</span>' not in template
    assert 'md:min-h-[20rem]' in template
    assert 'flex min-w-0 flex-col px-3 py-3 sm:py-4' in template
