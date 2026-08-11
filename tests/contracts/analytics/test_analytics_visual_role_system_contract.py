from pathlib import Path
import re


ANALYTICS_ROOT = Path('app/templates/analytics')
SURFACE = ANALYTICS_ROOT / 'components/_analysis_surfaces.html'
DOMAINS = (
    'overview',
    'utilization',
    'capacity',
    'storage',
    'workload',
    'forecast',
    'top_consumers',
    'alerts',
)


def read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def _iter_calls(source: str, name: str):
    marker = f'{name}('
    cursor = 0
    while True:
        start = source.find(marker, cursor)
        if start < 0:
            return
        index = start + len(marker)
        depth = 1
        quote = None
        escaped = False
        while index < len(source) and depth:
            char = source[index]
            if quote:
                if escaped:
                    escaped = False
                elif char == '\\':
                    escaped = True
                elif char == quote:
                    quote = None
            else:
                if char in "'\"":
                    quote = char
                elif char == '(':
                    depth += 1
                elif char == ')':
                    depth -= 1
            index += 1
        yield source[start:index]
        cursor = index


def test_visual_roles_are_owned_by_one_shared_analytics_component() -> None:
    source = read(SURFACE)

    for macro in (
        "macro role_icon_classes(role='brand', tone='info', size='default')",
        "macro role_label_classes(role='brand', tone='info')",
        "macro resource_role(resource='')",
        "macro resource_icon_classes(resource='', size='default')",
        "macro interpretation_callout(label, headline, body, icon='info', role='brand'",
    ):
        assert macro in source

    assert 'border-kaori-border bg-kaori-soft text-kaori-primary' in source
    assert "table_label.tone_border_classes('info')" in source
    assert "table_label.tone_surface_classes('info')" in source
    assert "table_label.tone_icon_classes('info')" in source
    assert 'border-outline-subtle bg-surface-muted text-content-secondary' in source
    assert 'table_label.tone_surface_classes(resolved_tone)' in source


def test_every_analytics_page_uses_the_shared_token_scope() -> None:
    for domain in DOMAINS:
        source = read(ANALYTICS_ROOT / domain / 'index.html')
        assert 'kaori-analytics-page' in source, domain


def test_analytics_templates_do_not_duplicate_brand_icon_geometry() -> None:
    violations = []
    for template in ANALYTICS_ROOT.rglob('*.html'):
        if template in {SURFACE, ANALYTICS_ROOT / 'components/_record_detail_modal.html'}:
            continue
        source = read(template)
        if 'bg-kaori-soft text-kaori-primary' in source:
            violations.append(str(template))
    assert violations == []


def test_every_interpretation_call_declares_a_visual_role() -> None:
    violations = []
    for template in ANALYTICS_ROOT.rglob('*.html'):
        if template == SURFACE:
            continue
        source = read(template)
        for call_name in ('interpretation_callout', 'interpretation_content'):
            for call in _iter_calls(source, call_name):
                if 'role=' not in call:
                    violations.append(f'{template}:{call_name}')
    assert violations == []


def test_visual_roles_are_used_for_their_intended_meaning() -> None:
    all_templates = '\n'.join(
        read(path)
        for path in ANALYTICS_ROOT.rglob('*.html')
        if path != SURFACE
    )

    assert "role='insight'" in all_templates
    assert "role='brand'" in all_templates
    assert "role='status'" in all_templates
    assert 'resource_icon_classes(' in all_templates
    assert 'semantic_icon_classes(' in all_templates
    assert 'semantic=true' not in all_templates


def test_capacity_status_bars_use_semantic_colors_while_composition_stays_violet() -> None:
    overview = read(ANALYTICS_ROOT / 'capacity/partials/_overview.html')
    allocation = read(ANALYTICS_ROOT / 'capacity/partials/_allocation.html')
    risk = read(ANALYTICS_ROOT / 'capacity/partials/_risk.html')
    ranked = read(ANALYTICS_ROOT / 'components/_ranked_evidence_panel.html')

    assert 'progress_bar.semantic_bar(item.utilization_percent, item.tone' in overview
    assert "progress_bar.semantic_bar(allocation_item['percent'], allocation_item['tone']" in allocation
    assert 'progress_bar.semantic_bar(item.headroom, tone' in risk
    assert 'bg-kaori-primary' in ranked


def test_overview_uses_category_and_status_color_without_tinting_full_cards() -> None:
    health = read(ANALYTICS_ROOT / 'overview/partials/_health_summary.html')
    resource = read(ANALYTICS_ROOT / 'overview/partials/_resource_snapshot.html')
    alerts = read(ANALYTICS_ROOT / 'overview/partials/_alerts_snapshot.html')

    assert 'semantic_icon_classes(semantic_tone)' in health
    assert 'resource_icon_classes(item.label)' in resource
    assert 'semantic_icon_classes(metric.tone)' in alerts

    full_card_tint = re.compile(r'<article[^>]+bg-status-(?:normal|warning|critical|info|unknown)-soft')
    for source in (health, resource, alerts):
        assert full_card_tint.search(source) is None
