from pathlib import Path


LANDING = Path('app/templates/integrations/alertmanager.html')
INSTANCE_FORM = Path('app/templates/alertmanager/instance_form.html')
RUNTIME_PANEL = Path('app/templates/alertmanager/partials/_runtime_panel.html')
LEGACY_CONFIG = Path('app/templates/alertmanager/config.html')


def test_alertmanager_landing_hero_matches_kaori_violet_geometry() -> None:
    source = LANDING.read_text(encoding='utf-8')

    required_fragments = (
        'rounded-2xl border border-brand-outline bg-kaori-primary p-5',
        'grid gap-5 xl:grid-cols-12 xl:items-stretch',
        'flex min-w-0 flex-col justify-center xl:col-span-7',
        "page_hero.intro('siren', 'Operational Integration', 'server-cog')",
        'font-medium leading-6 text-brand-foreground-muted sm:text-base',
        'page_hero.meta_label',
        'aside class="xl:col-span-5"',
        'flex h-full min-h-[13rem] flex-col rounded-xl',
        'Integration posture',
        'Connection readiness and usage coverage',
        'Register Instance',
    )
    missing = [fragment for fragment in required_fragments if fragment not in source]
    assert not missing, f'Alertmanager landing hero contract is incomplete: {missing}'

    forbidden_fragments = (
        'page_hero.shell_classes()',
        'page_hero.layout_classes()',
        'page_hero.supporting_strip',
        'lg:grid-cols-[minmax(0,1fr)_20rem]',
        'bg-gradient-to-r',
        'from-blue-',
        'to-cyan-',
    )
    found = [fragment for fragment in forbidden_fragments if fragment in source]
    assert not found, f'Alertmanager landing still contains legacy hero patterns: {found}'


def test_alertmanager_instance_hero_uses_the_same_geometry() -> None:
    source = INSTANCE_FORM.read_text(encoding='utf-8')

    required_fragments = (
        'rounded-2xl border border-brand-outline bg-kaori-primary p-5',
        'grid gap-5 xl:grid-cols-12 xl:items-stretch',
        'flex min-w-0 flex-col justify-center xl:col-span-7',
        "page_hero.intro('siren', 'Alertmanager Integration Source', 'server-cog')",
        'aside class="xl:col-span-5"',
        'flex h-full min-h-[13rem] flex-col rounded-xl',
        'Source posture',
        'Configuration and usage boundary',
        'Back to Registry',
        'components/table_label.html',
    )
    missing = [fragment for fragment in required_fragments if fragment not in source]
    assert not missing, f'Alertmanager instance hero contract is incomplete: {missing}'

    assert 'page_hero.shell_classes()' not in source
    assert 'page_hero.layout_classes()' not in source
    assert 'rounded-full' not in source


def test_alertmanager_runtime_panel_uses_semantic_kaori_statuses_and_htmx_indicator() -> None:
    source = RUNTIME_PANEL.read_text(encoding='utf-8')

    required_fragments = (
        'components/table_label.html',
        'table_label.status_label',
        'id="alertmanager-runtime-loading"',
        'hx-indicator="#alertmanager-runtime-loading"',
        'sm:grid-cols-2 xl:grid-cols-3',
        'latest persisted runtime observation',
        'Latest observed source condition',
        'Validated integration capability contract',
        'Diagnostic Pipeline',
    )
    missing = [fragment for fragment in required_fragments if fragment not in source]
    assert not missing, f'Alertmanager runtime panel contract is incomplete: {missing}'



def test_alertmanager_copy_is_global_and_has_no_future_product_positioning() -> None:
    landing = LANDING.read_text(encoding='utf-8')
    instance = INSTANCE_FORM.read_text(encoding='utf-8')
    inventory = Path(
        'app/templates/integrations/alertmanager/partials/_inventory_card.html'
    ).read_text(encoding='utf-8')
    combined = '\n'.join((landing, instance, inventory))

    required_fragments = (
        'infrastructure assets, services, domains, and workflows',
        'multiple operational contexts through governed bindings',
        'systems, services, and workflows that use them',
        'infrastructure assets, services, operational domains, and workflows',
        'workflows, or global contexts through canonical bindings',
    )
    missing = [fragment for fragment in required_fragments if fragment not in combined]
    assert not missing, f'Alertmanager global integration wording is incomplete: {missing}'

    forbidden_fragments = (
        'Kubernetes or future infrastructure',
        'Server, HCI, or Storage',
        'as those asset registries are introduced',
        'future infrastructure scope',
        'Ready for downstream reads',
        'provider-owned',
    )
    found = [fragment for fragment in forbidden_fragments if fragment in combined]
    assert not found, f'Alertmanager still contains product/future positioning: {found}'


def test_obsolete_cluster_configuration_template_is_removed() -> None:
    assert not LEGACY_CONFIG.exists(), (
        'The unreferenced blue-gradient Alertmanager cluster configuration template '
        'must not remain alongside the canonical instance workflow.'
    )
