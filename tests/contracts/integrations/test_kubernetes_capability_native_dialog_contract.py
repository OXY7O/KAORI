from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding='utf-8')


def test_capability_view_more_uses_native_top_layer_dialog() -> None:
    capability = read('app/templates/integrations/kubernetes/partials/_capability_workspace.html')
    modal = read('app/templates/integrations/components/_record_detail_modal.html')

    assert 'data-kaori-capability-native-dialogs' in capability
    assert 'data-kaori-dialog-open' in capability
    assert 'data-dialog-target="capability-detail-modal-{{ loop.index }}"' in capability
    assert 'aria-haspopup="dialog"' in capability
    assert 'record_detail_modal.render(' in capability

    assert '<dialog id="{{ modal_id }}"' in modal
    assert 'data-kaori-native-dialog' in modal
    assert 'method="dialog"' in modal
    assert 'onclick=' not in modal
    assert 'data-kaori-dialog-close' in modal
    assert 'kaori-native-dialog' in modal
    assert 'backdrop:bg-slate-950/70' not in modal

    assert 'x-teleport="body"' not in modal
    assert 'x-show=' not in modal
    assert 'detailOpen' not in modal
    assert 'selectedDetail' not in modal
    assert 'openDetail(key)' not in capability
    assert 'detailOpen: false' not in capability
    assert 'selectedDetail: null' not in capability


def test_capability_dialog_uses_compact_professional_decision_layout() -> None:
    capability = read('app/templates/integrations/kubernetes/partials/_capability_workspace.html')
    modal = read('app/templates/integrations/components/_record_detail_modal.html')

    for marker in (
        'data-kaori-capability-modal-v2',
        'data-kaori-capability-decision-summary',
        'data-kaori-capability-validation-scope',
        'data-kaori-capability-operational-guidance',
        'data-kaori-capability-verification-script',
    ):
        assert marker in capability

    for label in (
        'Validation Decision',
        'Contract Context',
        'Validation Scope',
        'Operational Guidance',
        'Operational Impact',
        'Recommended Action',
        'Governance Boundary',
        'Independent Verification',
        'Execution Context',
        'Copy Script',
    ):
        assert label in capability

    assert "size='standard'" in capability
    assert 'technical_check.render(' not in capability
    assert 'Kubernetes API and RBAC Check' not in capability
    assert 'data-kaori-dialog-size="{{ size }}"' in modal
    assert "size='wide'" in modal
    assert 'max-w-5xl' in modal
    assert 'max-h-[calc(100dvh-1rem)]' in modal
