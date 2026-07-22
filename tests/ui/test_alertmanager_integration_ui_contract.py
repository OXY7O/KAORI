import ast
from pathlib import Path


LANDING = Path('app/templates/integrations/alertmanager.html')
INSTANCE_FORM = Path('app/templates/alertmanager/instance_form.html')
INSTANCE_DETAIL = Path('app/templates/alertmanager/instance_detail.html')
DETAIL_CONFIGURATION = Path('app/templates/alertmanager/partials/_detail_configuration.html')
DETAIL_VALIDATION = Path('app/templates/alertmanager/partials/_detail_validation.html')
DETAIL_VALIDATION_CONTENT = Path('app/templates/alertmanager/partials/_detail_validation_content.html')
DETAIL_RUNTIME = Path('app/templates/alertmanager/partials/_detail_runtime.html')
DETAIL_SCOPE = Path('app/templates/alertmanager/partials/_detail_scope.html')
RUNTIME_PANEL = Path('app/templates/alertmanager/partials/_runtime_panel.html')
RUNTIME_RESPONSE = Path('app/templates/alertmanager/partials/_runtime_refresh_response.html')
RUNTIME_HISTORY = Path('app/templates/integrations/partials/_runtime_history.html')
FEEDBACK_OOB = Path('app/templates/alertmanager/partials/_operation_feedback_oob.html')
ROUTES = Path('app/alertmanager/routes.py')
REGISTRATION = Path('app/alertmanager/registration.py')
ALERTMANAGER_README = Path('app/alertmanager/README.md')
LEGACY_CONFIG = Path('app/templates/alertmanager/config.html')


def test_alertmanager_delete_actions_use_kaori_confirmation_modal() -> None:
    source = '\n'.join((
        INSTANCE_FORM.read_text(encoding='utf-8'),
        INSTANCE_DETAIL.read_text(encoding='utf-8'),
        DETAIL_SCOPE.read_text(encoding='utf-8'),
    ))
    modal = Path(
        'app/templates/alertmanager/partials/_delete_confirmation_modal.html'
    ).read_text(encoding='utf-8')

    required_form_fragments = (
        'data-delete-title="Remove scope binding?"',
        'data-delete-title="Delete Alertmanager instance?"',
        'data-delete-action-label="Remove binding"',
        'data-delete-action-label="Delete instance"',
        "alertmanager/partials/_delete_confirmation_modal.html",
    )
    missing = [fragment for fragment in required_form_fragments if fragment not in source]
    assert not missing, f'Alertmanager delete triggers are incomplete: {missing}'

    required_modal_fragments = (
        'id="alertmanager-delete-modal"',
        'role="dialog"',
        'border-status-critical-border',
        'data-alertmanager-delete-close',
        'data-operation-submit',
        "closest('[data-alertmanager-delete-button]')",
        "event.key === 'Escape'",
    )
    missing = [fragment for fragment in required_modal_fragments if fragment not in modal]
    assert not missing, f'Alertmanager delete modal contract is incomplete: {missing}'


def test_obsolete_cluster_configuration_template_is_removed() -> None:
    assert not LEGACY_CONFIG.exists(), (
        'The unreferenced blue-gradient Alertmanager cluster configuration template '
        'must not remain alongside the canonical instance workflow.'
    )
