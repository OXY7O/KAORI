from __future__ import annotations

import re
import runpy
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]

KUBERNETES_ANALYTICS_HEROES = (
    'overview/partials/_hero.html',
    'utilization/partials/_hero.html',
    'capacity/partials/_hero.html',
    'storage/partials/_hero.html',
    'workload/partials/_hero.html',
    'top_consumers/partials/_hero.html',
    'alerts/partials/_hero.html',
    'forecast/partials/_hero.html',
)


def test_hero_component_standard_is_enforced() -> None:
    result = subprocess.run(
        [sys.executable, 'scripts/verify_hero_component_standard.py'],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert 'KAORI Hero component standard passed' in result.stdout


def test_secrets_pki_hero_descriptions_use_static_qualified_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    verifier = runpy.run_path(str(ROOT / 'scripts/verify_hero_component_standard.py'))
    resolver = verifier['_secrets_pki_workspace_descriptions']
    descriptions = resolver()
    assert set(descriptions) == {
        'app/secrets_pki/evidence_workspaces.py:certificates',
        'app/secrets_pki/evidence_workspaces.py:pki',
        'app/secrets_pki/evidence_workspaces.py:expiration',
        'app/secrets_pki/operational_evidence_workspaces.py:leases',
        'app/secrets_pki/operational_evidence_workspaces.py:consumers',
        'app/secrets_pki/operational_evidence_workspaces.py:governance',
    }
    for owner, description in descriptions.items():
        verifier['_validate_description_budget'](description, owner=owner)

    original_read = resolver.__globals__['_read']
    source = ROOT / 'app/secrets_pki/evidence_workspaces.py'

    def non_static_description(path: Path) -> str:
        content = original_read(path)
        if path == source:
            return content.replace(
                "'Review public certificates and independent consumer evidence.'",
                'dynamic_provider_description',
            )
        return content

    monkeypatch.setitem(resolver.__globals__, '_read', non_static_description)
    with pytest.raises(AssertionError, match='static literals'):
        resolver()


def test_notification_channels_hero_uses_three_bounded_metadata_roles() -> None:
    source = (ROOT / 'app/templates/integrations/delivery/notification_channels/index.html').read_text(encoding='utf-8')
    verifier = runpy.run_path(str(ROOT / 'scripts/verify_hero_component_standard.py'))
    verifier['_verify_bounded_hero_metadata'](source, owner='Notification Channels')

    for label in ('Delivery Capability', 'Provider Registry', 'Delivery Evidence'):
        assert label in source

    channels = (
        ROOT / 'app/templates/integrations/delivery/notification_channels/partials/_channels_workspace.html'
    ).read_text(encoding='utf-8')
    assert '{% for provider in payload.providers %}' in channels
    assert '{{ provider.label }}' in channels
    assert '{{ provider.description }}' in channels
    assert 'table_label.status_label(provider.status, provider.tone' in channels
    assert 'Open {{ provider.label }} setup guide' in channels


def test_notification_channels_hero_rejects_dynamic_and_extra_metadata() -> None:
    verifier = runpy.run_path(str(ROOT / 'scripts/verify_hero_component_standard.py'))
    check = verifier['_verify_bounded_hero_metadata']
    row = '<div class="{{ page_hero.metadata_row_classes() }}">__ITEMS__</div>'
    with pytest.raises(AssertionError, match='unbounded/conditional'):
        check(
            row.replace(
                '__ITEMS__',
                '{% for provider in payload.providers %}'
                '{{ page_hero.meta_label(provider.icon, provider.label) }}'
                '{% endfor %}',
            ),
            owner='regression',
        )
    with pytest.raises(AssertionError, match='expected 3 stable'):
        check(
            row.replace('__ITEMS__', "{{ page_hero.meta_label('a','one') }}" * 4),
            owner='regression',
        )


def test_unmanaged_hero_detector_scopes_brand_surface_to_shell_container() -> None:
    namespace = runpy.run_path(str(ROOT / 'scripts' / 'verify_hero_component_standard.py'))
    detector = namespace['_has_unmanaged_hero_shell']

    normal_page = '<main><h1>Account</h1><a class="bg-kaori-primary">Save</a></main>'
    unmanaged_hero = '<section class="bg-kaori-primary rounded-2xl"><h1>Local Hero</h1></section>'

    assert detector(normal_page) is False
    assert detector(unmanaged_hero) is True


def test_hero_documentation_has_one_global_contract_and_one_domain_extension() -> None:
    components = ROOT / 'docs' / 'design' / 'components'
    global_standard = (components / 'HERO.md').read_text(encoding='utf-8')
    analytics_extension = (components / 'ANALYTICS_HERO.md').read_text(encoding='utf-8')

    assert 'KAORI Hero Component Standard v1.9' in global_standard
    assert 'Hero Profile' in global_standard
    assert 'Hero State' in global_standard
    assert 'Eyebrow = where / domain context' in global_standard
    assert 'KUBERNETES TENANT → Overview' in global_standard
    assert 'OBJECT STORAGE INVENTORY → Overview' in global_standard
    assert 'OBJECT STORAGE INVENTORY → Object Storage Overview' in global_standard
    assert 'Legacy surfaces that still duplicate eyebrow/title wording' in global_standard
    assert 'same Profile + same State' in global_standard
    assert 'exactly three metadata' in global_standard
    assert 'normal, blocked, and degraded' in global_standard
    assert '7–15 words' in global_standard
    assert '8–12 words' in global_standard
    assert 'maximum 68 characters' in global_standard
    assert 'one visual line at canonical non-phone widths' in global_standard
    assert 'action-oriented' in global_standard
    assert 'phone-native compact composition' in global_standard
    assert '14 px / 24 px on phone' in global_standard
    assert '16 px / 28 px from `sm`' in global_standard
    assert 'Action Icon Box' in global_standard
    assert 'Context Icon Box' in global_standard
    assert 'Status Badge Box' in global_standard
    assert 'exactly two compact metrics' in global_standard
    assert 'kaori-hero-shell' in global_standard
    assert 'components/DARK_MODE.md' in global_standard
    assert 'Kubernetes Analytics Hero Extension' in analytics_extension
    assert 'Blocked Analytics metadata remains exactly three items' in analytics_extension
    assert 'page_hero.analytics_metadata(...)' in analytics_extension
    assert not (components / 'ANALYTICS_HERO_STANDARD.md').exists()
    assert not (components / 'ANALYTICS_HERO_INVENTORY_REFERENCE.md').exists()


def test_operational_dashboard_uses_one_canonical_hero_profile() -> None:
    component = (ROOT / 'app' / 'templates' / 'components' / 'page_hero.html').read_text(encoding='utf-8')
    kubernetes = (ROOT / 'app' / 'templates' / 'kubernetes' / 'dashboard' / 'partials' / '_hero.html').read_text(
        encoding='utf-8'
    )
    object_storage = (
        ROOT / 'app' / 'templates' / 'storage' / 'object_storage' / 'dashboard' / 'partials' / '_hero.html'
    ).read_text(encoding='utf-8')

    assert 'macro operational_dashboard(' in component
    assert 'macro persistent_metadata(' in component
    assert 'data-kaori-hero-metadata-policy="persistent"' in component
    assert 'page_hero.operational_dashboard(' in kubernetes
    assert 'page_hero.operational_dashboard(' in object_storage
    assert 'kaori-hero-description' in component
    assert 'whitespace-nowrap' not in component
    for source in (kubernetes, object_storage):
        assert 'page_hero.shell_classes()' not in source
        assert 'page_hero.layout_classes()' not in source
        assert 'page_hero.context_panel_classes()' not in source


def test_kubernetes_dashboard_uses_canonical_cluster_integration_action() -> None:
    source = (ROOT / 'app' / 'templates' / 'kubernetes' / 'dashboard' / 'partials' / '_hero.html').read_text(
        encoding='utf-8'
    )

    assert "'Open Cluster Integrations'" in source
    assert "url_for('integrations.kubernetes')" in source
    assert "'Add Cluster'" not in source
    assert "'Kubernetes Integrations'" not in source


def test_blocked_hero_context_has_one_shared_renderer() -> None:
    component = (ROOT / 'app' / 'templates' / 'components' / 'page_hero.html').read_text(encoding='utf-8')
    shared_context = (
        ROOT / 'app' / 'templates' / 'components' / 'provider_prerequisite' / '_hero_context.html'
    ).read_text(encoding='utf-8')
    kubernetes = (ROOT / 'app' / 'templates' / 'components' / 'cluster' / '_hero_blocked_context.html').read_text(
        encoding='utf-8'
    )
    object_storage = (
        ROOT
        / 'app'
        / 'templates'
        / 'storage'
        / 'object_storage'
        / 'inventory'
        / 'components'
        / '_hero_blocked_context.html'
    ).read_text(encoding='utf-8')

    assert 'macro blocked_context_body(' in component
    assert 'page_hero.blocked_context_body(' in shared_context
    for wrapper in (kubernetes, object_storage):
        assert 'components/provider_prerequisite/_hero_context.html' in wrapper
        assert 'page_hero.blocked_context_body(' not in wrapper


def test_kubernetes_analytics_heroes_use_three_stable_metadata_slots_in_all_states() -> None:
    component = (ROOT / 'app' / 'templates' / 'components' / 'page_hero.html').read_text(encoding='utf-8')
    assert 'macro analytics_metadata(' in component
    assert 'data-kaori-analytics-metadata' in component
    assert 'persistent_metadata(analytics_items)' in component

    base = ROOT / 'app' / 'templates' / 'kubernetes' / 'analytics'
    for relative in KUBERNETES_ANALYTICS_HEROES:
        source = (base / relative).read_text(encoding='utf-8')
        assert 'page_hero.analytics_metadata(' in source, relative
        assert 'page_hero.metadata_row_classes()' not in source, relative


def test_object_storage_analytics_uses_three_stable_metadata_slots_in_all_states() -> None:
    source = (
        ROOT / 'app' / 'templates' / 'storage' / 'object_storage' / 'analytics' / 'partials' / '_hero.html'
    ).read_text(encoding='utf-8')

    assert 'page_hero.analytics_metadata(' in source
    assert 'page_hero.metadata_row_classes()' not in source
    assert re.search(r"evidence_label\s*=\s*['\"]Committed Snapshot Boundary['\"]", source)
    assert '{% if inventory_observed_at %}' not in source


def test_object_storage_inventory_setup_copy_is_concise() -> None:
    source = (
        ROOT
        / 'app'
        / 'templates'
        / 'storage'
        / 'object_storage'
        / 'inventory'
        / 'components'
        / '_onboarding_banner.html'
    ).read_text(encoding='utf-8')

    assert 'Register a Storage integration before KAORI collects object-storage snapshots.' in source
    assert 'before KAORI can collect and present committed object-storage systems' not in source


def test_kubernetes_analytics_cluster_remediation_uses_integration_action() -> None:
    source = (ROOT / 'app' / 'common' / 'dependencies.py').read_text(encoding='utf-8')
    start = source.index('def cluster_required_blocker()')
    end = source.index('\n\ndef metrics_source_setup_blocker', start)
    blocker = source[start:end]

    assert "'action_label': 'Open Cluster Integrations'" in blocker
    assert "'action_url': url_for('integrations.kubernetes')" in blocker
    assert "'permission': 'clusters.manage'" in blocker
    assert "'action_label': 'Add Cluster'" not in blocker
    assert "'action_label': 'Open Cluster Integration'" not in blocker
    assert "url_for('cluster.add_cluster')" not in blocker


def test_removed_hero_macros_are_absent_from_implementation() -> None:
    source = (ROOT / 'app' / 'templates' / 'components' / 'page_hero.html').read_text(encoding='utf-8')
    for macro in (
        'context_posture_header',
        'context_posture_note',
        'context_bottom_notice',
        'action_group_classes',
        'secondary_action_classes',
        'destructive_action_classes',
        'supporting_strip',
    ):
        assert f'macro {macro}' not in source


def test_hero_right_header_accessories_have_three_canonical_variants() -> None:
    source = (ROOT / 'app' / 'templates' / 'components' / 'page_hero.html').read_text(encoding='utf-8')

    assert 'macro context_action_icon_box(icon, href, aria_label, title=None)' in source
    assert 'macro context_icon_box(icon)' in source
    assert "macro context_header_status(eyebrow_label, title, status_label, status_tone='info')" in source
    assert 'aria-label="{{ aria_label }}"' in source
    assert 'context_status_badge(status_label, status_tone)' in source


def test_hero_context_panel_footer_variants_share_one_precise_row_rhythm() -> None:
    source = (ROOT / 'app' / 'templates' / 'components' / 'page_hero.html').read_text(encoding='utf-8')

    assert 'flex h-full flex-col gap-2.5' in source
    assert 'sm:min-h-[13rem] sm:gap-3 sm:p-4' in source
    assert 'grid grid-cols-1 gap-2' in source
    assert 'sm:grid-cols-2 sm:auto-rows-fr' in source
    assert 'sm:[&>*:nth-child(n+2)]:block' in source
    assert 'kaori-hero-tile mt-auto flex min-h-10 items-center gap-2' in source
    assert "mt-auto grid min-h-10 gap-2 {{ 'grid-cols-2' if columns == 2 else 'grid-cols-1' }}" in source
    assert 'mt-3 grid grid-cols-2 gap-2' not in source
    assert 'mt-auto grid gap-2 pt-3' not in source


def test_intelligence_overview_uses_non_redundant_hero_identity() -> None:
    source = (ROOT / 'app' / 'templates' / 'intelligence' / 'overview.html').read_text(encoding='utf-8')

    assert "page_hero.intro('brain-circuit', 'Intelligence', 'scan-search')" in source
    assert '<h1 class="{{ page_hero.title_classes() }}">Overview</h1>' in source
    assert 'Infrastructure Intelligence' not in source
    assert '>Intelligence Overview</h1>' not in source


def test_kubernetes_blocker_families_are_locked_to_general_and_analytics() -> None:
    standard = (ROOT / 'docs' / 'design' / 'components' / 'HERO.md').read_text(encoding='utf-8')
    tenant = (ROOT / 'app' / 'templates' / 'kubernetes' / 'tenant' / 'base.html').read_text(encoding='utf-8')
    analytics = (ROOT / 'app' / 'templates' / 'kubernetes' / 'analytics' / 'overview' / 'index.html').read_text(
        encoding='utf-8'
    )
    app_layout = (ROOT / 'app' / 'templates' / 'layouts' / 'app.html').read_text(encoding='utf-8')

    assert 'Kubernetes has exactly two prerequisite blocker families' in standard
    assert 'components/cluster/_hero_blocked_context.html' in tenant
    assert 'components/cluster/_onboarding_banner.html' in tenant
    assert 'components/states/_blocked_state.html' not in tenant
    assert '{% block page_capability_navigation %}' in app_layout
    assert '{% block page_capability_navigation %}' not in analytics
    assert '{% if dependency_blocker %}' in analytics


def test_active_hero_families_use_navigation_owned_non_redundant_identity() -> None:
    expected = {
        'app/templates/kubernetes/inventory/overview/partials/_hero.html': ('Kubernetes Inventory', 'Overview'),
        'app/templates/kubernetes/inventory/nodes/partials/_hero.html': ('Kubernetes Inventory', 'Nodes'),
        'app/templates/kubernetes/governance/overview/index.html': ('Kubernetes Governance', 'Overview'),
        'app/templates/kubernetes/governance/tls_certificates/partials/_hero.html': (
            'Kubernetes Governance',
            'TLS Certificates',
        ),
        'app/templates/kubernetes/analytics/capacity/partials/_hero.html': ('Kubernetes Analytics', 'Capacity'),
        'app/templates/storage/object_storage/inventory/overview/partials/_hero.html': (
            'Object Storage Inventory',
            'Overview',
        ),
        'app/templates/access/overview/index.html': ('Access', 'Overview'),
        'app/templates/platform_operations/overview/index.html': ('Operations Center', 'Overview'),
    }

    for relative, (eyebrow, title) in expected.items():
        source = (ROOT / relative).read_text(encoding='utf-8')
        assert eyebrow in source, relative
        assert f'>{title}</h1>' in source, relative


def test_reports_and_integrations_hero_identity_follow_sidebar_vocabulary() -> None:
    report_expectations = {
        'overview/index.html': ('Reports', 'Overview'),
        'generate/index.html': ('Reports', 'Generate'),
        'generated/index.html': ('Reports', 'Generated'),
        'report_templates/index.html': ('Reports', 'Templates'),
        'storage/index.html': ('Reports', 'Storage'),
        'schedules/index.html': ('Reports', 'Schedules'),
    }
    base = ROOT / 'app' / 'templates' / 'reports'
    for relative, (eyebrow, title) in report_expectations.items():
        source = (base / relative).read_text(encoding='utf-8')
        assert f"'{eyebrow}'" in source, relative
        assert f'>{title}</h1>' in source, relative

    integration_overview = (ROOT / 'app/templates/integrations/overview.html').read_text(encoding='utf-8')
    integration_domain = (ROOT / 'app/templates/integrations/domain.html').read_text(encoding='utf-8')
    assert '{% set badge = "Integrations" %}' in integration_overview
    assert '{% set title = "Overview" %}' in integration_overview
    assert 'page_hero.intro(domain.icon, "Integrations", domain.icon)' in integration_domain
    assert '>{{ domain.label }}</h1>' in integration_domain

    general = (ROOT / 'app/templates/settings/general/partials/_hero.html').read_text(encoding='utf-8')
    account = (ROOT / 'app/templates/settings/account/partials/_hero.html').read_text(encoding='utf-8')
    assert "page_hero.intro('settings-2', 'Settings'," in general
    assert '>General</h1>' in general
    assert "page_hero.intro('settings-2', 'Settings'," in account
    assert '>Account</h1>' in account

    object_storage_pages = (ROOT / 'app/storage/object_storage/analytics/pages.py').read_text(encoding='utf-8')
    assert object_storage_pages.count("'Object Storage Analytics',") == 6
    for title in ('Overview', 'Capacity & Usage', 'Performance', 'Forecast', 'Top Consumers', 'Alerts & Anomalies'):
        assert f"        '{title}'," in object_storage_pages


def test_secrets_pki_lifecycle_compact_hero_and_integrated_navigation_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    verifier = runpy.run_path(str(ROOT / 'scripts/verify_hero_component_standard.py'))
    check = verifier['_verify_secrets_pki_lifecycle_compact_hero']
    check()

    read = check.__globals__['_read']
    lifecycle_path = ROOT / 'app/templates/secrets_pki/lifecycle.html'
    navigation_path = ROOT / 'app/templates/secrets_pki/_lifecycle_navigation.html'

    def legacy_single_quotes(path: Path) -> str:
        source = read(path)
        if path == lifecycle_path:
            assert 'lifecycle_navigation.render("lifecycle")' in source
            return source.replace('lifecycle_navigation.render("lifecycle")', "lifecycle_navigation.render('lifecycle')")
        return source

    monkeypatch.setitem(check.__globals__, '_read', legacy_single_quotes)
    check()

    def wrong_navigation_key(path: Path) -> str:
        source = read(path)
        if path == lifecycle_path:
            return source.replace('lifecycle_navigation.render("lifecycle")', 'lifecycle_navigation.render("leases")')
        return source

    monkeypatch.setitem(check.__globals__, '_read', wrong_navigation_key)
    with pytest.raises(AssertionError, match='must render shared peer navigation'):
        check()

    def misplaced_navigation(path: Path) -> str:
        source = read(path)
        if path == lifecycle_path:
            return source.replace('{{ lifecycle_navigation.render("lifecycle") }}', '').replace(
                '<section class="{{ page_hero.shell_classes() }}">',
                '<section class="{{ page_hero.shell_classes() }}">{{ lifecycle_navigation.render("lifecycle") }}',
                1,
            )
        return source

    monkeypatch.setitem(check.__globals__, '_read', misplaced_navigation)
    with pytest.raises(AssertionError, match='peer navigation must appear above Hero'):
        check()

    def broken_copy(path: Path) -> str:
        source = read(path)
        if path == lifecycle_path:
            return source.replace(
                'Missing evidence is not zero; TLS delivery is unverified.',
                'Missing evidence is not zero. Validity and matching fingerprints do not '
                'prove rotation, delivery, trust or endpoint TLS serving.',
            )
        return source

    monkeypatch.setitem(check.__globals__, '_read', broken_copy)
    with pytest.raises(AssertionError, match='one-line candidate'):
        check()

    def raw_navigation(path: Path) -> str:
        source = read(path)
        if path == navigation_path:
            return source.replace('workspace_tabs.render_navigation(', 'raw_navigation(')
        return source

    monkeypatch.setitem(check.__globals__, '_read', raw_navigation)
    with pytest.raises(AssertionError, match='Integrated Workspace Tabs'):
        check()


def test_secrets_pki_overview_blocked_dashboard_uses_shared_state_and_bounded_copy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    verifier = runpy.run_path(str(ROOT / 'scripts/verify_hero_component_standard.py'))
    check = verifier['_verify_secrets_pki_overview_blocked_dashboard']
    check()

    original_read = check.__globals__['_read']
    overview = ROOT / 'app/templates/secrets_pki/overview.html'

    def verbose_hero(path: Path) -> str:
        source = original_read(path)
        if path == overview:
            return source.replace(
                "blocked_info='Qualify Vault and collect KV v2 inventory.'",
                "blocked_info='Register a Vault source, approve KV v2 metadata mounts, "
                "and run the registered inventory job.'",
            )
        return source

    monkeypatch.setitem(check.__globals__, '_read', verbose_hero)
    with pytest.raises(AssertionError, match='one-line copy budget'):
        check()

    def wrong_blocker(path: Path) -> str:
        source = original_read(path)
        if path == overview:
            return source.replace(
                '{% include "components/states/_blocked_state.html" %}',
                '{% include "components/states/_empty_state.html" %}',
            )
        return source

    monkeypatch.setitem(check.__globals__, '_read', wrong_blocker)
    with pytest.raises(AssertionError, match='canonical _blocked_state'):
        check()
