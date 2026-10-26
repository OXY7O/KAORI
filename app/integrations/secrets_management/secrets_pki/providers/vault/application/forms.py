from __future__ import annotations

from dataclasses import dataclass

from flask_wtf import FlaskForm
from wtforms import BooleanField, IntegerField, PasswordField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, Length, NumberRange, Optional, ValidationError

from app.integrations.secrets_management.secrets_pki.providers.vault.kv2_inventory import parse_approved_kv2_mounts
from app.integrations.secrets_management.secrets_pki.providers.vault.pki_public_evidence import (
    parse_approved_pki_mounts,
)
from app.integrations.secrets_management.secrets_pki.providers.vault.transport import (
    validate_auth_mount,
    validate_vault_endpoint,
)
from app.kubernetes.cluster.constants import ENVIRONMENTS
from app.models.vault import VaultInstance


@dataclass(frozen=True, slots=True)
class VaultConnectionInput:
    name: str
    environment: str
    description: str | None
    endpoint: str
    namespace: str | None
    auth_mount: str
    role_id: str
    secret_id: str
    timeout: int
    enabled: bool
    kv2_mounts: tuple[str, ...] = ()
    pki_mounts: tuple[str, ...] = ()
    pki_stored_certs_enabled: bool = False


class VaultConnectionForm(FlaskForm):
    name = StringField('Connection Name', validators=[DataRequired(), Length(min=2, max=160)])
    environment = SelectField('Environment', choices=ENVIRONMENTS, validators=[DataRequired()])
    description = TextAreaField('Description', validators=[Optional(), Length(max=2000)])
    endpoint = StringField('HTTPS Endpoint', validators=[DataRequired(), Length(max=500)])
    namespace = StringField('Vault Namespace (optional)', validators=[Optional(), Length(max=255)])
    auth_mount = StringField('AppRole Auth Mount', default='approle', validators=[DataRequired(), Length(max=160)])
    role_id = StringField('AppRole RoleID', validators=[DataRequired(), Length(max=255)])
    secret_id = PasswordField('AppRole SecretID', validators=[Length(max=4096)])
    timeout = IntegerField('Request Timeout (seconds)', default=5, validators=[DataRequired(), NumberRange(min=1, max=30)])
    enabled = BooleanField('Enable Provider Connection', default=True)
    kv2_mounts = StringField('Approved KV v2 Mounts (comma-separated)', validators=[Optional(), Length(max=1500)])
    pki_mounts = StringField('Approved PKI Mounts (comma-separated)', validators=[Optional(), Length(max=650)])
    pki_stored_certs_enabled = BooleanField('Enable Stored PKI Certificate Collection', default=False)
    connection_test_proof = StringField('Connection Test Proof', validators=[Optional()])

    def __init__(self, *args, existing: VaultInstance | None = None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.existing = existing
        # Never hydrate a decrypted AppRole SecretID into rendered form data.
        if not self.is_submitted():
            self.secret_id.data = ''
            self.kv2_mounts.data = ', '.join(existing.kv2_mounts or ()) if existing is not None else ''
            self.pki_mounts.data = ', '.join(existing.pki_mounts or ()) if existing is not None else ''
            self.pki_stored_certs_enabled.data = bool(existing.pki_stored_certs_enabled) if existing is not None else False

    def validate_endpoint(self, field: StringField) -> None:
        try:
            field.data = validate_vault_endpoint(str(field.data or ''))
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

    def validate_namespace(self, field: StringField) -> None:
        value = str(field.data or '').strip('/')
        if value and (any(chr(code) in value for code in (9, 10, 13)) or value.startswith('..') or '//' in value):
            raise ValidationError('Vault namespace contains invalid characters.')

    def validate_auth_mount(self, field: StringField) -> None:
        try:
            field.data = validate_auth_mount(str(field.data or ''))
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

    def validate_kv2_mounts(self, field: StringField) -> None:
        try:
            field.data = ', '.join(parse_approved_kv2_mounts(str(field.data or '')))
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

    def validate_pki_mounts(self, field: StringField) -> None:
        try:
            field.data = ', '.join(parse_approved_pki_mounts(str(field.data or '')))
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

    def validate_secret_id(self, field: PasswordField) -> None:
        if not str(field.data or '') and self.existing is None and not self.connection_test_proof.data:
            raise ValidationError('AppRole SecretID is required.')

    def to_input(self) -> VaultConnectionInput:
        secret_id = str(self.secret_id.data or '') or (
            str(self.existing.secret_id) if self.existing is not None else ''
        )
        return VaultConnectionInput(
            name=str(self.name.data or '').strip(),
            environment=str(self.environment.data or '').strip(),
            description=str(self.description.data or '').strip() or None,
            endpoint=str(self.endpoint.data or '').strip(),
            namespace=str(self.namespace.data or '').strip('/') or None,
            auth_mount=str(self.auth_mount.data or 'approle').strip('/'),
            role_id=str(self.role_id.data or '').strip(),
            secret_id=secret_id,
            timeout=int(self.timeout.data or 5),
            enabled=bool(self.enabled.data),
            kv2_mounts=parse_approved_kv2_mounts(str(self.kv2_mounts.data or '')),
            pki_mounts=parse_approved_pki_mounts(str(self.pki_mounts.data or '')),
            pki_stored_certs_enabled=bool(self.pki_stored_certs_enabled.data),
        )
