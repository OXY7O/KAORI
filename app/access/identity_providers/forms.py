from __future__ import annotations

from flask import current_app
from flask_wtf import FlaskForm
from wtforms import BooleanField, HiddenField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional, ValidationError

from app.access.authentication.identity_provider.adapters.ldap.client import (
    ExternalProviderError,
    resolve_ldap_transport,
)
from app.access.authentication.identity_provider.catalog import configurable_provider_choices, provider_definition
from app.access.authentication.identity_provider.configuration import (
    IdentityProviderConfiguration,
    normalize_instance_key,
)


class IdentityProviderForm(FlaskForm):
    key = StringField('Provider Key', validators=[DataRequired(), Length(max=80)])
    display_name = StringField('Display Name', validators=[DataRequired(), Length(max=150)])
    provider_key = SelectField(
        'Provider', choices=[('', 'Select provider'), *configurable_provider_choices()], validators=[DataRequired()]
    )
    enabled = BooleanField('Enabled')
    jit_enabled = BooleanField('JIT Provisioning')
    default_role_id = SelectField('JIT Default Role', coerce=int, validators=[Optional()])
    admission_values = TextAreaField('Admission Policy Values', validators=[Optional(), Length(max=4000)])
    server_uri = StringField('LDAP Server URI', validators=[Optional(), Length(max=500)])
    base_dn = StringField('Base DN', validators=[Optional(), Length(max=500)])
    bind_dn = StringField('Bind DN', validators=[Optional(), Length(max=500)])
    bind_password_env = StringField('Bind Password Environment Variable', validators=[Optional(), Length(max=150)])
    user_filter = StringField('User Search Filter', validators=[Optional(), Length(max=500)])
    tls_mode = SelectField(
        'TLS Mode',
        choices=[('ldaps', 'LDAPS'), ('starttls', 'StartTLS'), ('plain', 'Plain (development only)')],
        validate_choice=False,
    )
    username_attribute = StringField('Username Attribute', validators=[Length(max=100)], default='sAMAccountName')
    email_attribute = StringField('Email Attribute', validators=[Length(max=100)], default='mail')
    display_name_attribute = StringField('Display Name Attribute', validators=[Length(max=100)], default='displayName')
    stable_id_attribute = StringField('Stable ID Attribute', validators=[Length(max=100)], default='objectGUID')
    client_id = StringField('OAuth / OIDC Client ID', validators=[Optional(), Length(max=255)])
    client_secret_env = StringField('Client Secret Environment Variable', validators=[Optional(), Length(max=150)])
    submit = SubmitField('Save Provider')

    def definition(self):
        return provider_definition(str(self.provider_key.data or ''))

    def validate_key(self, field) -> None:
        try:
            field.data = normalize_instance_key(field.data)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

    def _require_ldap_attribute(self, field, label: str) -> None:
        if self.definition().adapter_key == 'ldap' and not (field.data or '').strip():
            raise ValidationError(f'{label} is required for LDAP adapters.')

    def validate_tls_mode(self, field) -> None:
        if self.definition().adapter_key != 'ldap':
            return
        if field.data not in {'ldaps', 'starttls', 'plain'}:
            raise ValidationError('Select a supported LDAP TLS mode.')
        server_uri = (self.server_uri.data or '').strip()
        if not server_uri:
            return
        try:
            resolve_ldap_transport(
                server_uri,
                field.data,
                allow_plaintext=bool(current_app.config.get('AUTH_LDAP_ALLOW_PLAINTEXT', False)),
            )
        except ExternalProviderError as exc:
            raise ValidationError(str(exc)) from exc

    def validate_username_attribute(self, field) -> None:
        self._require_ldap_attribute(field, 'Username attribute')

    def validate_email_attribute(self, field) -> None:
        self._require_ldap_attribute(field, 'Email attribute')

    def validate_display_name_attribute(self, field) -> None:
        self._require_ldap_attribute(field, 'Display name attribute')

    def validate_stable_id_attribute(self, field) -> None:
        self._require_ldap_attribute(field, 'Stable ID attribute')

    def validate_enabled(self, field) -> None:
        if not field.data:
            return
        definition = self.definition()
        if definition.configuration_profile == 'ldap':
            required = [self.server_uri.data, self.base_dn.data, self.bind_dn.data, self.bind_password_env.data]
            if not all(value and str(value).strip() for value in required):
                raise ValidationError('Enabled LDAP providers require server, base DN, bind DN, and secret reference.')
        elif definition.configuration_profile == 'browser_client':
            if not (self.client_id.data and self.client_secret_env.data):
                raise ValidationError('Enabled browser SSO providers require a client ID and client-secret reference.')

    def validate_jit_enabled(self, field) -> None:
        if not field.data:
            return
        definition = self.definition()
        if not definition.supports_jit:
            raise ValidationError('The selected provider does not support JIT provisioning.')
        if not self.default_role_id.data:
            raise ValidationError('JIT requires a default role.')
        if definition.admission_policy in {'verified_email_domain_allowlist', 'subject_allowlist'}:
            if not _split_values(self.admission_values.data):
                raise ValidationError('JIT requires at least one admission-policy value.')


class ExternalIdentitySearchForm(FlaskForm):
    provider_id = SelectField('Directory Provider', coerce=int, validators=[DataRequired()])
    query = StringField('Search Directory', validators=[DataRequired(), Length(min=2, max=150)])
    submit = SubmitField('Search')


class ExternalIdentityProvisionForm(FlaskForm):
    provider_id = HiddenField(validators=[DataRequired()])
    projection_proof = HiddenField(validators=[DataRequired()])
    role_id = SelectField('Assigned Role', coerce=int, validators=[DataRequired()])
    is_active = BooleanField('Active', default=True)
    submit = SubmitField('Provision User')


def configuration_from_form(form: IdentityProviderForm) -> IdentityProviderConfiguration:
    definition = form.definition()
    configuration: dict[str, object]
    if definition.configuration_profile == 'ldap':
        configuration = {
            'server_uri': _optional_text(form.server_uri.data),
            'base_dn': _optional_text(form.base_dn.data),
            'bind_dn': _optional_text(form.bind_dn.data),
            'bind_password_env': _optional_text(form.bind_password_env.data),
            'user_filter': _optional_text(form.user_filter.data),
            'tls_mode': str(form.tls_mode.data or 'ldaps'),
            'connect_timeout_seconds': 5,
            'username_attribute': str(form.username_attribute.data or 'sAMAccountName'),
            'email_attribute': str(form.email_attribute.data or 'mail'),
            'display_name_attribute': str(form.display_name_attribute.data or 'displayName'),
            'stable_id_attribute': str(form.stable_id_attribute.data or 'objectGUID'),
        }
    else:
        configuration = {
            'client_id': _optional_text(form.client_id.data),
            'client_secret_env': _optional_text(form.client_secret_env.data),
            'connect_timeout_seconds': 5,
        }
    admission_policy = {
        'profile': definition.admission_policy,
        'values': _split_values(form.admission_values.data),
    }
    return IdentityProviderConfiguration(
        provider_key=definition.provider_key,
        key=str(form.key.data or ''),
        display_name=str(form.display_name.data or ''),
        enabled=bool(form.enabled.data),
        jit_enabled=bool(form.jit_enabled.data),
        default_role_id=form.default_role_id.data or None,
        configuration=configuration,
        admission_policy=admission_policy,
    )


def populate_form(form: IdentityProviderForm, provider) -> None:
    form.key.data = provider.key
    form.display_name.data = provider.display_name
    form.provider_key.data = provider.provider_key
    form.enabled.data = provider.enabled
    form.jit_enabled.data = provider.jit_enabled
    form.default_role_id.data = provider.default_role_id or 0
    form.admission_values.data = '\n'.join(provider.admission_values)
    config = provider.configuration_json or {}
    form.server_uri.data = config.get('server_uri')
    form.base_dn.data = config.get('base_dn')
    form.bind_dn.data = config.get('bind_dn')
    form.bind_password_env.data = config.get('bind_password_env')
    form.user_filter.data = config.get('user_filter')
    form.tls_mode.data = config.get('tls_mode') or 'ldaps'
    form.username_attribute.data = config.get('username_attribute') or 'sAMAccountName'
    form.email_attribute.data = config.get('email_attribute') or 'mail'
    form.display_name_attribute.data = config.get('display_name_attribute') or 'displayName'
    form.stable_id_attribute.data = config.get('stable_id_attribute') or 'objectGUID'
    form.client_id.data = config.get('client_id')
    form.client_secret_env.data = config.get('client_secret_env')


def _split_values(value: object) -> list[str]:
    normalized = str(value or '').replace(',', '\n')
    return [item.strip().lower() for item in normalized.splitlines() if item.strip()]


def _optional_text(value: object) -> str | None:
    normalized = str(value or '').strip()
    return normalized or None
