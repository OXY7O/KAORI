"""Guard web-independent Vault connection input and AppRole proof ownership."""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
VAULT_APPLICATION = ROOT / 'app/integrations/secrets_management/secrets_pki/providers/vault/application'
INPUT_IMPORT = 'app.integrations.secrets_management.secrets_pki.providers.vault.application.types'


def test_vault_service_and_registration_do_not_import_web_forms() -> None:
    for filename in ('service.py', 'registration.py'):
        source = (VAULT_APPLICATION / filename).read_text(encoding='utf-8')
        tree = ast.parse(source)
        imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
        assert INPUT_IMPORT in imports, filename
        assert not any(module and module.endswith('.forms') for module in imports), filename


def test_vault_connection_input_is_application_owned_and_form_mapped() -> None:
    typed_source = (VAULT_APPLICATION / 'types.py').read_text(encoding='utf-8')
    tree = ast.parse(typed_source)
    inputs = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'VaultConnectionInput']
    assert len(inputs) == 1
    fields = [node.target.id for node in inputs[0].body if isinstance(node, ast.AnnAssign)]
    assert fields == [
        'name',
        'environment',
        'description',
        'endpoint',
        'namespace',
        'auth_mount',
        'role_id',
        'secret_id',
        'timeout',
        'enabled',
        'kv2_mounts',
        'pki_mounts',
        'pki_stored_certs_enabled',
    ]
    assert '@dataclass(frozen=True, slots=True)' in typed_source
    assert 'flask' not in typed_source.lower()
    assert 'wtforms' not in typed_source.lower()

    form_source = (VAULT_APPLICATION / 'forms.py').read_text(encoding='utf-8')
    assert f'from {INPUT_IMPORT} import VaultConnectionInput' in form_source
    assert 'def to_input(self) -> VaultConnectionInput:' in form_source
    assert 'return VaultConnectionInput(' in form_source
    assert 'class VaultConnectionInput:' not in form_source


def test_vault_proof_fingerprint_retains_secret_exclusion_and_ttl() -> None:
    source = (VAULT_APPLICATION / 'registration.py').read_text(encoding='utf-8')
    assert 'fields = asdict(values)' in source
    assert "fields.pop('secret_id')" in source
    assert "'encrypted_secret_id': encrypted" in source
    assert 'max_age=600' in source
    assert 'hmac.compare_digest' in source
