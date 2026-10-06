from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_secret_create_target_identity_is_two_by_two() -> None:
    source = read('app/templates/kubernetes/operations/secrets/create.html')
    assert 'Target &amp; Identity' in source
    assert 'grid gap-5 md:grid-cols-2' in source
    assert 'lg:grid-cols-2 xl:grid-cols-4' not in source


def test_protected_reveal_uses_shared_analytics_content_tab_style_with_fallback() -> None:
    page = read('app/templates/kubernetes/operations/secrets/reveal.html')
    tabs = read('app/templates/components/content_tabs.html')
    assert 'components/content_tabs.html' in page
    assert 'content_tabs.render_controlled_links' in page
    assert 'data-kaori-tab-variant="content-tabs-controlled"' in tabs
    assert 'data-kaori-tab-control="alpine-url-fallback"' in tabs
    assert 'data-kaori-tab-fallback="server-navigation"' in tabs
    assert '@click.prevent="setTab(' in tabs
    assert 'href="{{ tab_href }}"' in tabs


def test_protected_reveal_empty_cluster_copy_is_compact() -> None:
    page = read('app/templates/kubernetes/operations/secrets/reveal.html')
    assert 'No eligible cluster. Review readiness or policy.' in page
    assert 'No eligible cluster. Check readiness or enable a policy.' not in page


def test_secret_surfaces_remain_semantic_token_owned() -> None:
    source = '\n'.join(
        path.read_text(encoding='utf-8')
        for path in sorted((ROOT / 'app/templates/kubernetes/operations/secrets').glob('*.html'))
    )
    for forbidden in ('text-[', 'leading-[', 'tracking-[', 'font-extrabold', 'font-black'):
        assert forbidden not in source
    for raw_family in (
        'bg-red-',
        'text-red-',
        'border-red-',
        'bg-blue-',
        'text-blue-',
        'border-blue-',
        'bg-violet-',
        'text-violet-',
        'border-violet-',
        'bg-gray-',
        'text-gray-',
        'border-gray-',
    ):
        assert raw_family not in source


def test_protected_reveal_standard_docs_match_the_reviewed_tab_style() -> None:
    guide = read('docs/design/KAORI_STYLING_GUIDE.md')
    registry = read('docs/design/components/TAB_STYLES.md')
    content_tabs = read('docs/design/components/CONTENT_TABS.md')
    pattern = read('docs/design/patterns/KUBERNETES_CONFIGMAP_SECRET_OPERATIONS.md')
    assert 'Tab Style 4 — Content Tabs' in guide
    assert 'Protected Secret Reveal' in registry
    assert 'render_controlled_links()' in content_tabs
    assert 'Protected Reveal uses Tab Style 4:' in pattern


def test_tls_rotate_copy_and_fingerprint_space_are_balanced() -> None:
    page = read('app/templates/kubernetes/operations/secrets/tls_rotate.html')
    routes = read('app/kubernetes/operations/secrets/tls_routes.py')
    expected_hero_copy = 'Validate certificate pairing and coverage before Secret rotation.'
    assert expected_hero_copy in page
    assert expected_hero_copy in routes
    assert (
        'Validate parsing, key matching, host coverage, and the replacement before Update TLS Secret is enabled.'
        in page
    )
    assert 'lg:grid-cols-[minmax(0,0.85fr)_minmax(0,1.15fr)]' in page
    assert 'lg:grid-cols-[minmax(0,1.45fr)_minmax(18rem,0.55fr)]' not in page
