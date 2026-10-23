"""Vault integration detail must not imply independent Secret access."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ROUTES = ROOT / 'app/integrations/secrets_management/secrets_pki/providers/vault/application/routes.py'
DETAIL = ROOT / 'app/templates/integrations/secrets_management/vault/detail.html'


def test_vault_operational_links_are_explicitly_role_gated():
    route = ROUTES.read_text(encoding='utf-8')
    page = DETAIL.read_text(encoding='utf-8')
    assert "can_view_secrets_pki=current_user.has_permission('secrets_pki.view')" in route
    assert "and current_user.has_permission('analytics.view')" in route
    assert '{% if can_view_secrets_pki %}' in page
    assert '{% if can_view_cert_analytics %}' in page
    for endpoint in ('overview', 'inventory', 'lifecycle', 'certificate_analytics'):
        assert "url_for('secrets_pki." + endpoint + "')" in page
    assert 'The independent <code>secrets_pki.view</code> permission is required' in page
    assert 'instance_id=instance.id' not in page.split(
        'id="vault-operational-evidence-title"'
    )[1].split('id="vault-detail-tabs"')[0]
