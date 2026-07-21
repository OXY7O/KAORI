from __future__ import annotations

from cryptography.fernet import Fernet
from flask import Flask

from app.security.credentials import decrypt_credential, encrypt_credential


def test_integration_credentials_are_encrypted_and_round_trip() -> None:
    app = Flask(__name__)
    app.config['INTEGRATION_CREDENTIAL_KEY'] = Fernet.generate_key().decode('ascii')
    app.config['SECRET_KEY'] = 'test-only-secret'

    with app.app_context():
        encrypted = encrypt_credential('sensitive-value')
        assert encrypted is not None
        assert encrypted.startswith('enc:v1:')
        assert 'sensitive-value' not in encrypted
        assert decrypt_credential(encrypted) == 'sensitive-value'


def test_plaintext_read_is_supported_only_as_cutover_input() -> None:
    app = Flask(__name__)
    app.config['INTEGRATION_CREDENTIAL_KEY'] = Fernet.generate_key().decode('ascii')
    app.config['SECRET_KEY'] = 'test-only-secret'

    with app.app_context():
        assert decrypt_credential('legacy-plaintext') == 'legacy-plaintext'


def test_previous_key_can_decrypt_during_rotation() -> None:
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'test-only-secret'
    old_key = Fernet.generate_key().decode('ascii')
    new_key = Fernet.generate_key().decode('ascii')
    app.config['INTEGRATION_CREDENTIAL_KEY'] = old_key
    app.config['INTEGRATION_CREDENTIAL_PREVIOUS_KEYS'] = ''
    with app.app_context():
        encrypted = encrypt_credential('rotate-me')

    app.config['INTEGRATION_CREDENTIAL_KEY'] = new_key
    app.config['INTEGRATION_CREDENTIAL_PREVIOUS_KEYS'] = old_key
    with app.app_context():
        assert decrypt_credential(encrypted) == 'rotate-me'
        assert encrypt_credential('new-value') != encrypted
