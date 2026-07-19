import ast
from pathlib import Path


LANDING = Path('app/templates/integrations/alertmanager.html')
INSTANCE_FORM = Path('app/templates/alertmanager/instance_form.html')
RUNTIME_PANEL = Path('app/templates/alertmanager/partials/_runtime_panel.html')
RUNTIME_RESPONSE = Path('app/templates/alertmanager/partials/_runtime_refresh_response.html')
FEEDBACK_OOB = Path('app/templates/alertmanager/partials/_operation_feedback_oob.html')
ROUTES = Path('app/alertmanager/routes.py')
LEGACY_CONFIG = Path('app/templates/alertmanager/config.html')


def test_alertmanager_landing_hero_matches_kaori_violet_geometry() -> None:
    source = LANDING.read_text(encoding='utf-8')

    required_fragments = (
        'page_hero.shell_classes()',
        'page_hero.layout_classes()',
        'page_hero.content_classes()',
        "page_hero.intro('siren', 'Operational Integration', 'server-cog')",
        'font-medium leading-6 text-brand-foreground-muted sm:text-base',
        'Register, validate, and govern reusable Alertmanager connections and their operational scope bindings.',
        'page_hero.meta_label',
        'page_hero.aside_classes()',
        'flex h-full min-h-[12rem] flex-col rounded-xl',
        'Integration posture',
        'Connection readiness and scope coverage',
        'Register Instance',
    )
    missing = [fragment for fragment in required_fragments if fragment not in source]
    assert not missing, f'Alertmanager landing hero contract is incomplete: {missing}'

    forbidden_fragments = (
        'page_hero.supporting_strip',
        'lg:grid-cols-[minmax(0,1fr)_20rem]',
        'Connect Alertmanager as a reusable operational source across infrastructure assets, services, domains, and workflows.',
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
        'Integration workflow',
        'Connection lifecycle &amp; scope',
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
        'Register, validate, and govern reusable Alertmanager connections',
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


def test_register_alertmanager_instance_matches_informative_form_contract() -> None:
    source = INSTANCE_FORM.read_text(encoding='utf-8')

    required_fragments = (
        'id="alertmanager-instance-form"',
        'xl:col-span-8',
        'xl:col-span-4 xl:sticky xl:top-5',
        'Alertmanager Scope &amp; Workflow',
        'Provider Identity &amp; Contract',
        'After Registration',
        'Reusable connection identity',
        'Reachability test',
        'Validation and scope assignment',
        'Allow KAORI to use this connection',
        'maintenance or troubleshooting without deleting the instance',
        "url_for('alertmanager.test_new_instance_connection')",
        'hx-include="#alertmanager-instance-form"',
        'hx-target="#alertmanager-connection-test-result"',
        'Test Connection',
        'Register Instance',
        'focus:border-outline-focus focus:ring-2 focus:ring-outline-focus/20',
    )
    missing = [fragment for fragment in required_fragments if fragment not in source]
    assert not missing, f'Register Alertmanager form contract is incomplete: {missing}'

    forbidden_fragments = (
        'Integration Boundary',
        'Source Boundary',
        'font-mono',
        'focus:border-kaori-primary focus:ring-2 focus:ring-outline-focus',
        'Runtime source enabled',
        'Disabled sources are excluded from asset-scope resolution',
    )
    found = [fragment for fragment in forbidden_fragments if fragment in source]
    assert not found, f'Register Alertmanager form still contains legacy UI patterns: {found}'


def test_alertmanager_connection_test_result_is_semantic_and_separate_from_validation() -> None:
    source = Path(
        'app/templates/alertmanager/partials/_connection_test_result.html'
    ).read_text(encoding='utf-8')

    required_fragments = (
        'Reachable',
        'Not reachable',
        'Response time',
        'Cluster status',
        'Register the instance, then run Full Validation',
        'API capabilities, compatibility profile, runtime readiness, and scope eligibility',
        "alertmanager/partials/_operation_feedback_oob.html",
    )
    missing = [fragment for fragment in required_fragments if fragment not in source]
    assert not missing, f'Connection test result contract is incomplete: {missing}'
    assert 'rounded-full' not in source
    assert 'font-mono' not in source


def test_alertmanager_htmx_actions_render_persistent_notification_toasts() -> None:
    runtime_response = RUNTIME_RESPONSE.read_text(encoding='utf-8')
    feedback_oob = FEEDBACK_OOB.read_text(encoding='utf-8')

    assert 'runtime_feedback' in runtime_response
    assert "alertmanager/partials/_operation_feedback_oob.html" in runtime_response
    assert 'toast_oob=true' in feedback_oob
    assert "components/navigation/_quick_sync_result.html" in feedback_oob
    assert 'notification_saved=operation_feedback.notification_saved' in feedback_oob


def test_every_alertmanager_mutation_route_records_operational_activity() -> None:
    tree = ast.parse(ROUTES.read_text(encoding='utf-8'))
    functions = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    action_functions = (
        'new_instance',
        'test_new_instance_connection',
        'instance_detail',
        'refresh_runtime',
        'validate_instance',
        'create_binding',
        'remove_binding',
        'delete_instance',
        'test_cluster_alertmanager',
    )

    missing_functions = [name for name in action_functions if name not in functions]
    assert not missing_functions, f'Alertmanager action routes are missing: {missing_functions}'

    missing_audit_calls = []
    for name in action_functions:
        has_activity_call = any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == 'record_instance_activity'
            for node in ast.walk(functions[name])
        )
        if not has_activity_call:
            missing_audit_calls.append(name)

    assert not missing_audit_calls, (
        'Every Alertmanager mutation must create persistent notification and Activity Audit feedback: '
        f'{missing_audit_calls}'
    )


def test_obsolete_cluster_configuration_template_is_removed() -> None:
    assert not LEGACY_CONFIG.exists(), (
        'The unreferenced blue-gradient Alertmanager cluster configuration template '
        'must not remain alongside the canonical instance workflow.'
    )
