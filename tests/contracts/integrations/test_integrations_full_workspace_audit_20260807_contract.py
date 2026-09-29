from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


PROVIDER_TEMPLATE_ROOTS = (
    'app/templates/integrations/observability/metrics_source',
    'app/templates/integrations/observability/alert_source/providers/alertmanager',
)


def test_runtime_observation_state_view_is_exported_and_does_not_infer_health() -> None:
    presentation = read('app/integrations/runtime/presentation.py')
    assert 'def runtime_observation_state_view(' in presentation
    assert "'health_status': 'not_observed'" in presentation
    assert "'health_score_display': 'N/A'" in presentation
    assert 'without inferring health from connection state' in presentation


def test_runtime_observation_details_use_one_shared_native_dialog() -> None:
    history = read('app/templates/integrations/partials/_runtime_history.html')
    modal = read('app/templates/integrations/components/_runtime_observation_modal.html')
    controller = read('app/static/js/native_dialogs.js')
    actions = read('app/templates/integrations/components/_record_actions.html')
    layout = read('app/templates/layouts/app.html')

    assert 'integrations/components/_runtime_observation_modal.html' in history
    assert 'runtime_observation_modal.render(' in history
    assert 'record_actions.view_more(' in history
    assert "row.detail_id ~ '-dialog'" in history
    assert 'data-kaori-dialog-open' in actions
    assert 'data-dialog-target="{{ dialog_target }}"' in actions
    assert 'data-kaori-runtime-observation-detail' not in history
    assert 'record_detail_modal.render(' in modal
    assert "size='standard'" in modal
    assert 'data-kaori-runtime-observation-dialog-v4' in modal
    assert 'onclick=' not in history
    assert 'onclick=' not in modal
    assert 'dialog.showModal()' in controller
    assert 'js/native_dialogs.js' in layout


def test_provider_bound_scope_tables_are_full_width_before_decision_split() -> None:
    for template_root in PROVIDER_TEMPLATE_ROOTS:
        scope = read(f'{template_root}/partials/_detail_scope.html')
        registry = read(f'{template_root}/partials/_binding_registry.html')
        include_marker = scope.index('_binding_registry.html')
        decision = scope.index('Binding Decision')
        assert include_marker < decision
        assert 'data-kaori-bound-scopes-full-width' in registry
        assert '_binding_registry_layout.html' in registry
        assert 'binding_registry_layout.table_classes()' in registry

    assert 'Consumer Bindings' in read(
        'app/templates/integrations/observability/metrics_source/partials/_detail_scope.html'
    )
    assert 'Consumer Binding Registry' in read(
        'app/templates/integrations/observability/alert_source/providers/alertmanager/partials/_binding_registry.html'
    )


def test_compact_labels_are_one_line_by_default() -> None:
    labels = read('app/templates/components/table_label.html')
    assert labels.count('whitespace-nowrap') >= 4
    assert "if wrap else 'whitespace-nowrap'" in labels


def test_dark_mode_brand_identity_uses_dark_accent() -> None:
    workspace = read('app/templates/integrations/components/_workspace.html')
    framed_tabs = read('app/templates/components/framed_workspace_tabs.html')
    provider_tabs = read('app/templates/components/integration_workspace_tabs.html')

    assert 'dark:text-kaori-accent' in workspace
    assert 'dark:border-brand-outline' in workspace
    assert 'dark:text-kaori-accent' in framed_tabs
    assert 'components/framed_workspace_tabs.html' in provider_tabs
    assert 'framed_workspace_tabs.render(' in provider_tabs
    assert 'dark:text-kaori-accent' not in provider_tabs


def test_operational_toast_countdown_has_visible_htmx_safe_animation() -> None:
    toast = read('app/templates/components/operational_toast.html')
    progress = read('app/templates/components/operational_progress_toast.html')
    progress_primitive = read('app/templates/components/progress_bar.html')
    script = read('app/static/js/operational_toasts.js')

    assert 'data-operational-toast-timer' in toast
    assert 'origin-left' in toast
    assert 'style=' not in toast
    assert 'timerBar.animate' in script
    assert 'void timerBar.offsetWidth' in script
    assert "timerBar.style.transform = 'scaleX(0)'" in script
    assert 'current.animation?.pause?.()' in script
    assert 'dark:bg-kaori-primary' in toast
    assert 'progress_bar.notification_progress' in progress
    assert 'dark:bg-kaori-primary/15' in progress_primitive


def test_integration_templates_do_not_use_inline_dom_handlers() -> None:
    roots = (
        ROOT / 'app/templates/integrations',
        ROOT / 'app/templates/integrations/observability/metrics_source',
        ROOT / 'app/templates/integrations/observability/alert_source/providers/alertmanager',
    )
    offenders: list[str] = []
    for root in roots:
        for path in root.rglob('*.html'):
            source = path.read_text(encoding='utf-8')
            if any(token in source for token in ('onclick=', 'onchange=', 'onsubmit=')):
                offenders.append(path.relative_to(ROOT).as_posix())
    assert offenders == []


def test_integrations_standard_documents_full_audit_contract() -> None:
    standard = read('docs/design/components/INTEGRATIONS_WORKSPACE_STANDARD.md')
    audit = read('docs/design/audits/INTEGRATIONS_FULL_WORKSPACE_AUDIT_2026_08.md')
    for heading in (
        'Dark Mode Brand Allocation',
        'Single-Line Compact Label Contract',
        'Recent Runtime Observation Detail Contract',
        'Provider Binding Workspace Layout',
        'Toast Countdown Contract',
        'DRY Ownership Rules',
    ):
        assert heading in standard
    assert 'Integration Overview' in audit
    assert 'Kubernetes Integration' in audit
    assert 'Prometheus' in audit
    assert 'Alertmanager' in audit


def test_related_workspace_card_uses_shared_soft_violet_surface() -> None:
    card = read('app/templates/components/related_page_card.html')
    styles = read('frontend/styles.css')
    standard = read('docs/design/components/INTEGRATIONS_WORKSPACE_STANDARD.md')
    ownership = read('docs/design/components/REUSABLE_COMPONENT_OWNERSHIP.md')

    assert 'data-kaori-related-workspace-card' in card
    assert 'bg-kaori-soft' in card
    assert 'border-kaori-primary/20' in card
    assert 'text-kaori-primary' in card
    assert 'text-content-primary' in card
    assert 'text-content-secondary' in card
    assert 'bg-surface-card' in card
    assert 'bg-kaori-primary' in card
    assert 'kaori-brand-domain-panel' not in card
    assert 'text-brand-foreground' not in card
    assert '--kaori-brand-domain-panel' not in styles
    assert '.kaori-brand-domain-panel' not in styles
    assert 'soft Violet contextual-surface' in standard
    assert 'components/related_page_card.html' in ownership

    offenders: list[str] = []
    for path in (ROOT / 'app/templates').rglob('*.html'):
        if 'kaori-brand-domain-panel' in path.read_text(encoding='utf-8'):
            offenders.append(path.relative_to(ROOT).as_posix())
    assert offenders == []


def test_runtime_observation_modal_matches_capability_record_detail_hierarchy() -> None:
    runtime_modal = read('app/templates/integrations/components/_runtime_observation_modal.html')
    capability = read(
        'app/templates/integrations/orchestration/container_orchestrator/providers/'
        'kubernetes/partials/_capability_registry.html'
    )
    presentation = read('app/integrations/runtime/presentation.py')

    assert 'integrations/components/_record_detail_modal.html' in runtime_modal
    assert 'data-kaori-runtime-observation-decision-parity' in runtime_modal
    assert 'Runtime Decision' in runtime_modal
    assert 'Observation Snapshot' in runtime_modal
    assert 'p-5 sm:p-6' in runtime_modal
    assert 'border-t border-outline-subtle bg-surface-subtle px-5 py-4 sm:px-6' in runtime_modal
    assert 'data-kaori-capability-decision-summary' in capability
    assert 'Contract Snapshot' in capability
    assert "'summary': _runtime_primary_summary(" in presentation


def test_kubernetes_detail_copy_balance_follows_review_contract() -> None:
    connection = read(
        'app/templates/integrations/orchestration/container_orchestrator/providers/'
        'kubernetes/partials/_connection_contract.html'
    )
    capability_workspace = read(
        'app/templates/integrations/orchestration/container_orchestrator/providers/'
        'kubernetes/partials/_capability_workspace.html'
    )
    capability_registry = read(
        'app/templates/integrations/orchestration/container_orchestrator/providers/'
        'kubernetes/partials/_capability_registry.html'
    )

    assert 'Separates API, resource, and RBAC gaps; write access stays separately governed.' in connection
    assert 'Committed inventory, relationships, runtime evidence, reports, and audit stay traceable.' in connection
    assert 'Revalidate after Kubernetes upgrades, served-API changes, or RBAC policy changes.' in capability_workspace
    assert 'Required verbs are evaluated across all namespaces for this cluster-wide contract.' in capability_registry
    assert (
        'Required verbs are evaluated only in the approved namespace '
        'for this optional contract.'
    ) in capability_registry
