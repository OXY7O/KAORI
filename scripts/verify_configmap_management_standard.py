from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    errors: list[str] = []
    service = read('app/kubernetes_operations/configmaps/service.py')
    routes = read('app/kubernetes_operations/configmaps/routes.py')
    validation = read('app/kubernetes_operations/configmaps/validation.py')
    runtime = read('app/kubernetes_operations/configmaps/runtime.py')
    receipts = read('app/kubernetes_operations/configmaps/receipts.py')
    feedback = read('app/notifications/feedback.py')
    notification_service = read('app/notifications/service.py')
    presentation = read('app/bootstrap/presentation.py')
    app_layout = read('app/templates/layouts/app.html')
    auth_layout = read('app/templates/layouts/auth.html')
    toast = read('app/templates/components/operational_toast.html')
    toast_js = read('app/static/js/operational_toasts.js')
    progress_toast = read('app/templates/components/operational_progress_toast.html')
    editor_js = read('app/static/js/configmap_editor.js')
    delete_js = read('app/static/js/configmap_delete.js')
    preview = read('app/templates/kubernetes_operations/configmaps/_validation_preview.html')
    operation_response = read('app/templates/kubernetes_operations/configmaps/_operation_response.html')
    standard = read('docs/design/patterns/KUBERNETES_CONFIGMAP_SECRET_OPERATIONS.md')
    audit = read('docs/design/audits/KUBERNETES_CONFIGMAP_MANAGEMENT_TOAST_AUDIT_2026_08.md')
    quality_gate = read('scripts/quality_gate.sh')

    for token in (
        'filter_current_generation(ConfigurationInventory.query',
        'filter_current_generation(PodInventory.query',
        'pod_collection_state != COLLECTED',
        'pod_operational_state(pod.phase, pod.ready)',
        'perform(server_dry_run=True)',
        'perform(server_dry_run=False)',
        "dry_run='All' if server_dry_run else None",
        'V1Preconditions(resource_version=resource_version)',
    ):
        require(token in service, f'ConfigMap service missing canonical token: {token}', errors)
    require('validate_then_apply' not in service and 'validate_then_apply' not in routes,
            'ConfigMap operations must not use the generic validation wrapper.', errors)
    require('session' not in routes and 'session' not in receipts,
            'ConfigMap delete validation must not store target receipts in session.', errors)
    require("salt='kaori-configmap-delete-validation-v2'" in receipts,
            'Delete receipt must use the v2 signed contract.', errors)
    require('max_age=_DELETE_RECEIPT_MAX_AGE_SECONDS' in receipts,
            'Delete receipt must enforce the ten-minute expiry.', errors)
    require('expected_resource_version' in routes and 'verify_delete_receipt(' in routes,
            'Final delete must verify the signed resource-version receipt.', errors)
    require('connection_for_cluster(cluster)' in runtime and '_request_timeout=10' in service,
            'Live ConfigMap operations must use registered cluster runtime and bounded calls.', errors)

    for token in (
        "_ALLOWED_ENTRY_KINDS = {'text', 'binary'}",
        "_ALLOWED_UPDATE_MODES = {'merge', 'replace'}",
        'base64.b64decode(value, validate=True)',
        '_entries_payload_size(merged_data, merged_binary)',
        '_enforce_payload_limit(payload_size)',
        'ConfigMap entry row',
    ):
        require(token in validation, f'ConfigMap validation missing token: {token}', errors)

    for page in ('create.html', 'update.html', 'delete.html'):
        source = read(f'app/templates/kubernetes_operations/configmaps/{page}')
        require('_validation_preview.html' in source,
                f'{page} must include persistent validation evidence.', errors)
        require('hx-sync="this:drop"' in source and 'hx-disabled-elt="find button"' in source,
                f'{page} must block duplicate concurrent mutation submissions.', errors)
    for token in ('Validation Required', 'Validated', 'Failed', 'data-validation-status'):
        require(token in preview, f'Validation preview missing state token: {token}', errors)
    require('components/operation_feedback_oob.html' in operation_response,
            'ConfigMap HTMX responses must use canonical OOB operational feedback.', errors)
    require('kaori:operation-validation-invalidated' in editor_js,
            'ConfigMap editor must reset validation evidence after changed input.', errors)
    require("new Event('input', { bubbles: true })" in editor_js,
            'Programmatic ConfigMap row changes must invalidate the validation gate.', errors)
    require(editor_js.count('invalidateForm(form)') >= 2,
            'Both ConfigMap add and remove row paths must invalidate validation evidence.', errors)
    require('resetValidationPreview(form)' in delete_js,
            'Delete workflow must reset validation evidence after target/confirmation changes.', errors)

    for token in (
        'feedback_id',
        'auto_dismiss_ms',
        "'success': 8000",
        "'warning': 12000",
        "'error': 0",
        'OPERATIONAL_FEEDBACK_SESSION_KEY',
    ):
        require(token in feedback or token in read('app/notifications/constants.py'),
                f'Operational feedback contract missing token: {token}', errors)
    require('OperationalFeedbackSpec' in feedback and 'OperationalFeedbackSpec(' in notification_service,
            'Operational feedback must use the canonical typed specification.', errors)
    require('def queue_operational_feedback' not in notification_service and 'def pop_operational_feedback' not in notification_service,
            'Notification service must not retain feedback pass-through wrappers.', errors)
    require("'load_operational_feedback': _operational_feedback" in presentation,
            'Bootstrap must expose only canonical operational feedback context.', errors)
    for layout_name, layout in (('app', app_layout), ('auth', auth_layout)):
        require('id="operational-toast-stack"' in layout,
                f'{layout_name} layout must own the operational toast stack.', errors)
        require("js/operational_toasts.js" in layout,
                f'{layout_name} layout must load the global toast controller.', errors)
        require('dismissQuickActionToast' not in layout and 'data-quick-action-toast' not in layout,
                f'{layout_name} layout still contains legacy toast behavior.', errors)
    require('<script' not in toast and 'style=' not in toast,
            'Operational toast must not contain inline script or style debt.', errors)
    for token in (
        'data-operational-toast',
        'data-auto-dismiss-ms',
        'data-operational-toast-close',
        'Activity Audit',
        'Activity Audit not confirmed',
        'resolved_activity_audit_expected',
        'aria-live',
    ):
        require(token in toast, f'Operational toast missing token: {token}', errors)
    require('components/progress_bar.html' in progress_toast and 'style=' not in progress_toast,
            'Operational progress toast must reuse the shared progress component.', errors)
    for progress_usage in (
        'app/templates/components/navigation/_quick_sync_status.html',
        'app/templates/components/navigation/_individual_sync_status.html',
        'app/templates/governance/tls_certificates/partials/_sync_toast.html',
    ):
        require('components/operational_progress_toast.html' in read(progress_usage),
                f'Active progress surface must use canonical operational progress toast: {progress_usage}', errors)
    for token in (
        'maximumVisibleToasts = 4',
        "toast.addEventListener('mouseenter'",
        "toast.addEventListener('focusin'",
        'toast.dataset.toastId',
        'dismissOperationalToast',
    ):
        require(token in toast_js, f'Operational toast controller missing token: {token}', errors)

    obsolete = (
        'app/templates/kubernetes_operations/_components.html',
        'app/templates/kubernetes_operations/configmaps/_operation_notification.html',
        'app/templates/components/navigation/_quick_sync_result.html',
        'app/templates/components/navigation/_operation_feedback_oob.html',
    )
    for relative in obsolete:
        require(not (ROOT / relative).exists(), f'Legacy file must remain removed: {relative}', errors)

    active_roots = (ROOT / 'app',)
    forbidden = (
        'kubernetes_operations/_components.html',
        'components/navigation/_quick_sync_result.html',
        'components/navigation/_operation_feedback_oob.html',
        'dismissQuickActionToast',
        'build_quick_action_feedback',
        'queue_quick_action_feedback',
        'pop_quick_action_feedback',
        'load_quick_action_feedback',
    )
    for root in active_roots:
        for path in root.rglob('*'):
            if not path.is_file() or path.suffix not in {'.py', '.html', '.js', '.sh'}:
                continue
            source = path.read_text(encoding='utf-8')
            for token in forbidden:
                require(token not in source,
                        f'Legacy ConfigMap/toast token {token!r} remains in {path.relative_to(ROOT)}.', errors)

    require('ConfigMap validation evidence' in standard and 'Operational toast' in standard,
            'ConfigMap operations standard must document validation and toast contracts.', errors)
    require('Legacy removals' in audit and 'signed receipt' in audit,
            'ConfigMap audit must document legacy removal and signed delete validation.', errors)
    require('verify_configmap_management_standard.py' in quality_gate,
            'ConfigMap Management verifier must run in quality gate.', errors)

    if errors:
        for error in errors:
            print(f'ERROR: {error}')
        return 1

    print(
        'KAORI ConfigMap Management audit passed: live target authority, current-generation impact, '
        'single dry-run/mutation boundaries, signed delete receipt, persistent validation preview, '
        'canonical operational toast, Activity Audit, and legacy removal are aligned.'
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
