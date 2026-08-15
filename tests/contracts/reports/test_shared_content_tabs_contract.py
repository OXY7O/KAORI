from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text()


def test_shared_content_tabs_preserve_analytics_geometry_and_offer_server_owned_links() -> None:
    shared = read('app/templates/components/content_tabs.html')
    analytics_workspace = read('app/templates/analytics/kubernetes/components/_analysis_workspace.html')
    analytics_overview = read('app/templates/analytics/kubernetes/overview/index.html')
    storage = read('app/templates/reports/storage/index.html')

    # Geometry is the Analytics compact-tab treatment: soft embedded strip,
    # rounded bordered items, KAORI violet active state, and compact spacing.
    assert 'border-b border-outline-subtle bg-surface-hover px-5 py-2 sm:px-6' in shared
    assert "'min-w-max flex-nowrap' if nowrap else 'flex-wrap'" in shared
    assert 'rounded-lg border px-3.5 text-sm font-semibold' in shared
    assert 'border-kaori-primary bg-kaori-soft text-kaori-primary-dark dark:text-kaori-accent' in shared
    assert 'render_buttons' in shared
    assert 'render_links' in shared
    assert 'data-kaori-tab-variant="content-tabs-server"' in shared
    assert "shell_classes(embedded, nowrap)" in shared
    assert "'min-w-max flex-nowrap' if nowrap else 'flex-wrap'" in shared
    assert '{% if hx_sync %}hx-sync="{{ hx_sync }}"{% endif %}' in shared
    assert '{# djlint:off #}' in shared
    assert '{# djlint:on #}' in shared
    assert 'data-{{ data_namespace }}-tab-button="{{ tab_id }}"' in shared
    assert 'data-{{ data_namespace }}-tab-link="{{ tab_id }}"' in shared

    # Analytics now consumes the shared component directly; the former
    # compatibility wrapper is retired instead of preserved as duplicate ownership.
    assert 'components/content_tabs.html' in analytics_workspace
    assert 'content_tabs.render_buttons' in analytics_workspace
    assert "data_namespace='analytics'" in analytics_workspace
    assert 'components/content_tabs.html' in analytics_overview
    assert not (ROOT / 'app/templates/analytics/components/_content_tabs.html').exists()

    # Storage consumes the same global component with server-owned URL state.
    assert 'components/content_tabs.html' in storage
    assert 'content_tabs.render_links' in storage
    assert "data_namespace='storage'" in storage
    assert 'components/framed_workspace_tabs.html' not in storage
    assert 'framed_tabs.render_navigation' not in storage
