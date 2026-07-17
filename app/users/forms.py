from __future__ import annotations

from flask_wtf import FlaskForm
from wtforms import BooleanField, HiddenField, PasswordField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, EqualTo, Length, Optional, ValidationError

AUTH_SOURCE_CHOICES = [
    ('database', 'Local Database'),
    ('ldap', 'LDAP / Active Directory (use Directory Provisioning)'),
    ('sso', 'SSO / Identity Provider'),
]


class UserForm(FlaskForm):
    user_id = HiddenField()
    username = StringField('Username', validators=[DataRequired(), Length(max=100)])
    email = StringField('Email', validators=[DataRequired(), Length(max=255)])
    display_name = StringField('Display Name', validators=[Optional(), Length(max=150)])
    auth_source = SelectField('Auth Source', choices=AUTH_SOURCE_CHOICES, default='database')
    external_id = StringField('External ID', validators=[Optional(), Length(max=255)])
    role_id = SelectField('Role', coerce=int, validators=[DataRequired()])
    is_active = BooleanField('Active')
    is_super_admin = BooleanField('Super Admin')
    password = PasswordField('Password', validators=[Optional(), Length(min=8)])
    confirm_password = PasswordField(
        'Confirm Password', validators=[EqualTo('password', message='Password confirmation does not match.')]
    )
    submit = SubmitField('Save User')


class ResetPasswordForm(FlaskForm):
    password = PasswordField('New Password', validators=[DataRequired(), Length(min=8)])
    confirm_password = PasswordField(
        'Confirm Password',
        validators=[DataRequired(), EqualTo('password', message='Password confirmation does not match.')],
    )
    submit = SubmitField('Reset Password')

class IdentityProviderForm(FlaskForm):
    key = StringField('Provider Key', validators=[DataRequired(), Length(max=80)])
    display_name = StringField('Display Name', validators=[DataRequired(), Length(max=150)])
    provider_type = SelectField(
        'Provider Type',
        choices=[
            ('ldap', 'LDAP / Active Directory'),
            ('google_oidc', 'Google OpenID Connect'),
            ('github_oauth', 'GitHub OAuth'),
        ],
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
    tls_mode = SelectField('TLS Mode', choices=[('ldaps', 'LDAPS'), ('starttls', 'StartTLS'), ('plain', 'Plain (development only)')])
    username_attribute = StringField('Username Attribute', validators=[DataRequired(), Length(max=100)], default='sAMAccountName')
    email_attribute = StringField('Email Attribute', validators=[DataRequired(), Length(max=100)], default='mail')
    display_name_attribute = StringField('Display Name Attribute', validators=[DataRequired(), Length(max=100)], default='displayName')
    stable_id_attribute = StringField('Stable ID Attribute', validators=[DataRequired(), Length(max=100)], default='objectGUID')
    oidc_client_id = StringField('OAuth Client ID', validators=[Optional(), Length(max=255)])
    oidc_client_secret_env = StringField('Client Secret Environment Variable', validators=[Optional(), Length(max=150)])
    submit = SubmitField('Save Provider')

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
    subject = HiddenField(validators=[DataRequired()])
    external_username = HiddenField(validators=[DataRequired()])
    distinguished_name = HiddenField(validators=[DataRequired()])
    email = HiddenField()
    display_name = HiddenField()
    role_id = SelectField('Assigned Role', coerce=int, validators=[DataRequired()])
    is_active = BooleanField('Active', default=True)
    submit = SubmitField('Provision User')
