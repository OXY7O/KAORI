from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


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
    assert "dialog.showModal()" in controller
    assert "js/native_dialogs.js" in layout


def test_provider_bound_scope_tables_are_full_width_before_decision_split() -> None:
    prometheus = read('app/templates/prometheus/partials/_detail_scope.html')
    alertmanager = read('app/templates/alertmanager/partials/_detail_scope.html')

    for template in (prometheus, alertmanager):
        marker = template.index('data-kaori-bound-scopes-full-width')
        decision = template.index('Binding Decision')
        assert marker < decision
    assert 'Bound Kubernetes Scopes' in prometheus
    assert 'Bound Operational Scopes' in alertmanager


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
    assert 'dark:text-kaori-accent' in provider_tabs


def test_operational_toast_countdown_has_visible_htmx_safe_animation() -> None:
    toast = read('app/templates/components/operational_toast.html')
    progress = read('app/templates/components/operational_progress_toast.html')
    script = read('app/static/js/operational_toasts.js')

    assert 'data-operational-toast-timer' in toast
    assert 'origin-left' in toast
    assert 'style=' not in toast
    assert "timerBar.animate" in script
    assert 'void timerBar.offsetWidth' in script
    assert "timerBar.style.transform = 'scaleX(0)'" in script
    assert 'current.animation?.pause?.()' in script
    assert 'dark:bg-kaori-primary' in toast
    assert 'dark:bg-kaori-primary' in progress


def test_integration_templates_do_not_use_inline_dom_handlers() -> None:
    roots = (
        ROOT / 'app/templates/integrations',
        ROOT / 'app/templates/prometheus',
        ROOT / 'app/templates/alertmanager',
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
