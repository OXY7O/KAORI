"""Vault integration detail must not imply independent Secret access."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ROUTES = ROOT / 'app/integrations/secrets_management/secrets_pki/providers/vault/application/routes.py'
DETAIL = ROOT / 'app/templates/integrations/secrets_management/vault/detail.html'


def test_vault_detail_uses_canonical_tabs_not_cross_domain_shortcuts() -> None:
    """The provider detail is scoped; Secrets & PKI navigation stays domain-owned."""
    route = ROUTES.read_text(encoding='utf-8')
    page = DETAIL.read_text(encoding='utf-8')
    assert 'id="vault-operational-evidence-title"' not in page
    assert 'Secrets and PKI operational workspaces' not in page
    assert "url_for('secrets_pki." not in page
    assert 'id="vault-detail-tabs"' in page
    assert "app/templates/integrations/secrets_management/vault/detail.html" not in route
    assert "integrations/secrets_management/vault/detail.html" in route
    # No permissions broadened: the provider detail still requires
    # integrations.manage, rather than implying a scoped secrets_pki grant.
    assert "@permission_required('integrations.manage')\ndef detail(" in route
