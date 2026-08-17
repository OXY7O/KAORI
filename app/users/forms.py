from __future__ import annotations

from flask import current_app
from flask_wtf import FlaskForm
from wtforms import BooleanField, HiddenField, PasswordField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Email, EqualTo, Length, Optional, ValidationError

from app.auth.password_policy import LOCAL_PASSWORD_MAX_LENGTH, LocalPasswordPolicy
from app.auth.provider_configuration import normalize_provider_key
from app.auth.providers.catalog import configurable_provider_choices
from app.auth.providers.ldap import ExternalProviderError, resolve_ldap_transport


class UserForm(FlaskForm):
    user_id = HiddenField()
    username = StringField('Username', validators=[DataRequired(), Length(max=100)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=255)])
    display_name = StringField('Display Name', validators=[Optional(), Length(max=150)])
    auth_source = HiddenField(default='database')
    external_id = HiddenField()
    role_id = SelectField('Role', coerce=int, validators=[DataRequired()])
    is_active = BooleanField('Active')
    is_super_admin = BooleanField('Super Admin')
    password = PasswordField('Password', validators=[Optional(), LocalPasswordPolicy()])
    confirm_password = PasswordField(
        'Confirm Password',
        validators=[
            Length(max=LOCAL_PASSWORD_MAX_LENGTH),
            EqualTo('password', message='Password confirmation does not match.'),
        ],
    )
    submit = SubmitField('Save User')


class ResetPasswordForm(FlaskForm):
    password = PasswordField('New Password', validators=[DataRequired(), LocalPasswordPolicy()])
    confirm_password = PasswordField(
        'Confirm Password',
        validators=[
            DataRequired(),
            Length(max=LOCAL_PASSWORD_MAX_LENGTH),
            EqualTo('password', message='Password confirmation does not match.'),
        ],
    )
    submit = SubmitField('Reset Password')


class IdentityProviderForm(FlaskForm):
    key = StringField('Provider Key', validators=[DataRequired(), Length(max=80)])
    display_name = StringField('Display Name', validators=[DataRequired(), Length(max=150)])
    provider_type = SelectField(
        'Provider Type',
        choices=configurable_provider_choices(),
    )
    enabled = BooleanField('Enabled')
    jit_enabled = BooleanField('JIT Provisioning')
    default_role_id = SelectField('JIT Default Role', coerce=int, validators=[Optional()])
    allowed_domains = TextAreaField('Allowed Google Domains', validators=[Optional(), Length(max=2000)])
    allowed_subjects = TextAreaField('Allowed GitHub Users', validators=[Optional(), Length(max=4000)])
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
    oidc_client_id = StringField('OAuth Client ID', validators=[Optional(), Length(max=255)])
    oidc_client_secret_env = StringField('Client Secret Environment Variable', validators=[Optional(), Length(max=150)])
    submit = SubmitField('Save Provider')

    def validate_key(self, field):
        try:
            field.data = normalize_provider_key(field.data)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

    def _require_ldap_attribute(self, field, label: str) -> None:
        if self.provider_type.data == 'ldap' and not (field.data or '').strip():
            raise ValidationError(f'{label} is required for LDAP providers.')

    def validate_tls_mode(self, field):
        if self.provider_type.data != 'ldap':
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

    def validate_username_attribute(self, field):
        self._require_ldap_attribute(field, 'Username attribute')

    def validate_email_attribute(self, field):
        self._require_ldap_attribute(field, 'Email attribute')

    def validate_display_name_attribute(self, field):
        self._require_ldap_attribute(field, 'Display name attribute')

    def validate_stable_id_attribute(self, field):
        self._require_ldap_attribute(field, 'Stable ID attribute')

    def validate_enabled(self, field):
        if not field.data:
            return
        if self.provider_type.data == 'ldap':
            required = [self.server_uri.data, self.base_dn.data, self.bind_dn.data, self.bind_password_env.data]
            if not all(value and str(value).strip() for value in required):
                raise ValidationError('Enabled LDAP providers require server, base DN, bind DN, and secret reference.')
        elif not (self.oidc_client_id.data and self.oidc_client_secret_env.data):
            raise ValidationError('Enabled SSO providers require a client ID and client-secret environment reference.')

    def validate_jit_enabled(self, field):
        if not field.data:
            return
        if self.provider_type.data == 'ldap':
            raise ValidationError('LDAP JIT remains disabled; use controlled directory provisioning.')
        if not self.default_role_id.data:
            raise ValidationError('SSO JIT requires a default role.')
        if self.provider_type.data == 'google_oidc' and not (self.allowed_domains.data or '').strip():
            raise ValidationError('Google JIT requires at least one allowed email domain.')
        if self.provider_type.data == 'github_oauth' and not (self.allowed_subjects.data or '').strip():
            raise ValidationError('GitHub JIT requires at least one allowed username or numeric user ID.')


class ExternalIdentitySearchForm(FlaskForm):
    provider_id = SelectField('LDAP Provider', coerce=int, validators=[DataRequired()])
    query = StringField('Search Directory', validators=[DataRequired(), Length(min=2, max=150)])
    submit = SubmitField('Search')


class ExternalIdentityProvisionForm(FlaskForm):
    provider_id = HiddenField(validators=[DataRequired()])
    projection_proof = HiddenField(validators=[DataRequired()])
    role_id = SelectField('Assigned Role', coerce=int, validators=[DataRequired()])
    is_active = BooleanField('Active', default=True)
    submit = SubmitField('Provision User')
