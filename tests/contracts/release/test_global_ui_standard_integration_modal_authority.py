from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

_SHARED_INTEGRATION_MODAL_AUTHORITIES = (
    'app/templates/integrations/components/_asset_owner_delete_modal.html',
    'app/templates/integrations/components/_observability_binding_modal.html',
)


def test_shared_integration_modals_own_intentional_semantic_borders() -> None:
    verifier = (ROOT / 'scripts/verify_ui_style.py').read_text(encoding='utf-8')
    baseline = json.loads((ROOT / 'docs/architecture/ui-style-debt-baseline.json').read_text(encoding='utf-8'))['files']

    for relative in _SHARED_INTEGRATION_MODAL_AUTHORITIES:
        source = (ROOT / relative).read_text(encoding='utf-8')

        assert 'border-status-critical-border' in source
        assert f"'{relative}'" in verifier
        assert baseline.get(relative, {}).get('semantic_border_utilities', 0) == 0
