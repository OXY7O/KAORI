from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_domain_binding_guidance_uses_canonical_info_tip_without_persistent_callout() -> None:
    workspace = read('app/templates/integrations/partials/_domain_workspace.html')

    assert 'components/info_tip.html' in workspace
    assert 'info_tip.render(' in workspace
    assert "'integration-' ~ domain.key ~ '-binding-guidance'" in workspace
    assert "'Observability Routing'" in workspace
    assert "'Storage Authority Boundary'" in workspace
    assert 'data-kaori-storage-binding-boundary' not in workspace
    assert (
        'mb-4 flex flex-wrap items-start justify-between gap-3 rounded-lg '
        'border border-brand-outline bg-kaori-soft px-4 py-3'
    ) not in workspace


def test_domain_guidance_is_anchored_to_consumer_binding_filter_header() -> None:
    workspace = read('app/templates/integrations/partials/_domain_workspace.html')

    header = workspace.split('Consumer Binding Filters', 1)[1].split(
        'Search asset-to-source contracts',
        1,
    )[0]
    assert 'info_tip.render(' in header
    assert 'binding_guidance_title' in header
    assert "placement='right'" in header


def test_integrations_overview_remains_outside_domain_info_tip_refinement() -> None:
    overview = read('app/templates/integrations/overview.html')

    assert 'components/info_tip.html' not in overview
    assert 'info_tip.render(' not in overview
    assert 'Integration Portfolio Snapshot' in overview
    assert 'Connection and Authority Boundary' in overview
