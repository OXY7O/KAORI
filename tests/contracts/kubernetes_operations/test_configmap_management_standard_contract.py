from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text()


def test_configmap_operations_use_canonical_live_runtime_and_signed_delete_receipts() -> None:
    service = read('app/kubernetes_operations/configmaps/service.py')
    runtime = read('app/kubernetes_operations/configmaps/runtime.py')
    receipts = read('app/kubernetes_operations/configmaps/receipts.py')
    routes = read('app/kubernetes_operations/configmaps/routes.py')

    assert 'filter_current_generation(ConfigurationInventory.query' in service
    assert 'filter_current_generation(PodInventory.query' in service
    assert 'pod_collection_state != COLLECTED' in service
    assert 'perform(server_dry_run=True)' in service
    assert 'perform(server_dry_run=False)' in service
    assert "dry_run='All' if server_dry_run else None" in service
    assert 'expected_resource_version' in service
    assert 'V1Preconditions(resource_version=resource_version)' in service
    assert 'connection_for_cluster(cluster)' in runtime
    assert "salt='kaori-configmap-delete-validation-v2'" in receipts
    assert 'max_age=_DELETE_RECEIPT_MAX_AGE_SECONDS' in receipts
    assert 'session' not in receipts
    assert 'verify_delete_receipt(' in routes


def test_configmap_workflows_have_persistent_validation_evidence() -> None:
    for relative in (
        'app/templates/kubernetes_operations/configmaps/create.html',
        'app/templates/kubernetes_operations/configmaps/update.html',
        'app/templates/kubernetes_operations/configmaps/delete.html',
    ):
        source = read(relative)
        assert '_validation_preview.html' in source
        assert 'hx-sync="this:drop"' in source
        assert 'hx-disabled-elt="find button"' in source

    preview = read('app/templates/kubernetes_operations/configmaps/_validation_preview.html')
    assert 'Validation Required' in preview
    assert 'Validated' in preview
    assert 'Failed' in preview
    assert 'data-validation-status' in preview

    editor_js = read('app/static/js/configmap_editor.js')
    assert "new Event('input', { bubbles: true })" in editor_js
    assert editor_js.count('invalidateForm(form)') >= 2


def test_operational_toast_is_the_only_canonical_feedback_surface() -> None:
    app_layout = read('app/templates/layouts/app.html')
    auth_layout = read('app/templates/layouts/auth.html')
    toast = read('app/templates/components/operational_toast.html')
    toast_js = read('app/static/js/operational_toasts.js')
    progress = read('app/templates/components/operational_progress_toast.html')
    notification_service = read('app/notifications/service.py')
    feedback = read('app/notifications/feedback.py')

    for layout in (app_layout, auth_layout):
        assert 'id="operational-toast-stack"' in layout
        assert 'js/operational_toasts.js' in layout
        assert 'dismissQuickActionToast' not in layout
        assert 'data-quick-action-toast' not in layout

    assert 'data-operational-toast' in toast
    assert 'data-auto-dismiss-ms' in toast
    assert 'Activity Audit' in toast
    assert 'Activity Audit not confirmed' in toast
    assert 'resolved_activity_audit_expected' in toast
    assert 'data-operational-toast-close' in toast
    assert '<script' not in toast and 'style=' not in toast
    assert 'components/progress_bar.html' in progress and 'style=' not in progress
    assert 'OperationalFeedbackSpec' in feedback and 'OperationalFeedbackSpec(' in notification_service
    assert 'activity_audit_expected: bool = True' in feedback
    assert 'activity_audit_expected=False' in notification_service
    assert 'def queue_operational_feedback' not in notification_service
    assert 'def pop_operational_feedback' not in notification_service
    assert 'maximumVisibleToasts = 4' in toast_js
    assert 'mouseenter' in toast_js and 'focusin' in toast_js
    assert 'border border-outline-default bg-surface-elevated' in toast
    assert 'absolute inset-y-0 left-0 w-1' not in toast
    assert 'tone_dot_classes(resolved_tone)' not in toast
    assert 'data-operational-toast-timer' in toast
    assert 'mt-3 h-1.5 w-24 overflow-hidden rounded-full bg-surface-hover' in toast
    assert 'h-full w-full origin-left rounded-full bg-kaori-primary' in toast
    assert 'timerBar.animate' in toast_js and 'scaleX(0)' in toast_js
    assert 'w-1.5 shrink-0 bg-kaori-primary' not in progress
    assert 'border border-outline-default bg-surface-elevated' in progress


def test_legacy_configmap_and_feedback_wrappers_are_removed() -> None:
    obsolete = (
        'app/templates/kubernetes_operations/_components.html',
        'app/templates/kubernetes_operations/configmaps/_operation_notification.html',
        'app/templates/components/navigation/_quick_sync_result.html',
        'app/templates/components/navigation/_operation_feedback_oob.html',
    )
    assert all(not (ROOT / path).exists() for path in obsolete)

    operations = ROOT / 'app' / 'templates' / 'kubernetes_operations'
    for template in operations.rglob('*.html'):
        source = template.read_text()
        assert 'kubernetes_operations/_components.html' not in source
        assert 'components/navigation/_quick_sync_result.html' not in source
        assert 'components/navigation/_operation_feedback_oob.html' not in source
