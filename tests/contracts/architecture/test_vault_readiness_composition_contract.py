"""Vault provider UI consumes committed Secrets & PKI readiness through app-scoped composition."""

from pathlib import Path
from typing import cast

import pytest
from flask import Flask

from app.integrations.secrets_management.secrets_pki.providers.vault.application.routes import (
    _committed_pki_readiness,
)
from app.models.vault import VaultInstance

ROOT = Path(__file__).resolve().parents[3]
VAULT_ROOT = ROOT / 'app/integrations/secrets_management/secrets_pki'


def test_vault_provider_does_not_import_operational_secrets_pki_modules() -> None:
    for source in VAULT_ROOT.rglob('*.py'):
        content = source.read_text(encoding='utf-8')
        assert 'from app.secrets_pki.' not in content, str(source)
        assert 'import app.secrets_pki.' not in content, str(source)
    routes = (VAULT_ROOT / 'providers/vault/application/routes.py').read_text(encoding='utf-8')
    assert "current_app.extensions.get('kaori_vault_pki_readiness')" in routes
    assert 'public_pki_readiness=public_pki' in routes
    assert 'stored_cert_readiness=stored_pki' in routes


def test_bootstrap_composes_secrets_pki_owned_readers_per_app() -> None:
    source = (ROOT / 'app/bootstrap/blueprints.py').read_text(encoding='utf-8')
    assert "app.extensions['kaori_vault_pki_readiness'] = {" in source
    assert "'public_pki_readiness': pki_public_readiness" in source
    assert "'stored_cert_readiness': stored_pki_certificate_readiness" in source


def test_missing_or_invalid_readiness_reader_fails_closed() -> None:
    app = Flask(__name__)
    instance = cast(VaultInstance, object())
    with app.app_context():
        with pytest.raises(RuntimeError, match='providers are not registered'):
            _committed_pki_readiness(instance)
        app.extensions['kaori_vault_pki_readiness'] = {'public_pki_readiness': lambda **_: {}}
        with pytest.raises(RuntimeError, match='providers are not registered'):
            _committed_pki_readiness(instance)


def test_composed_readers_receive_the_same_instance_and_return_both_snapshots() -> None:
    app = Flask(__name__)
    instance = cast(VaultInstance, object())
    seen: list[object] = []

    def public(*, instance: VaultInstance) -> dict[str, object]:
        seen.append(instance)
        return {'status': 'ready', 'source': 'public'}

    def stored(*, instance: VaultInstance) -> dict[str, object]:
        seen.append(instance)
        return {'status': 'not_collected', 'source': 'stored'}

    app.extensions['kaori_vault_pki_readiness'] = {
        'public_pki_readiness': public,
        'stored_cert_readiness': stored,
    }
    with app.app_context():
        public_result, stored_result = _committed_pki_readiness(instance)
    assert seen == [instance, instance]
    assert public_result == {'status': 'ready', 'source': 'public'}
    assert stored_result == {'status': 'not_collected', 'source': 'stored'}
