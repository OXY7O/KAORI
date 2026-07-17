from __future__ import annotations

from flask_wtf import FlaskForm
from wtforms import BooleanField, HiddenField, PasswordField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, EqualTo, Length, Optional, ValidationError

AUTH_SOURCE_CHOICES = [
    ('database', 'Local Database'),
    ('ldap', 'LDAP / Active Directory (use Directory Provisioning)'),
    ('sso', 'SSO / Identity Provider (OIDC next phase)'),
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
    provider_type = SelectField('Provider Type', choices=[('ldap', 'LDAP / Active Directory'), ('oidc', 'OIDC SSO')])
    enabled = BooleanField('Enabled')
    jit_enabled = BooleanField('JIT Provisioning')
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
    oidc_issuer = StringField('OIDC Issuer', validators=[Optional(), Length(max=500)])
    oidc_client_id = StringField('OIDC Client ID', validators=[Optional(), Length(max=255)])
    oidc_client_secret_env = StringField('OIDC Client Secret Environment Variable', validators=[Optional(), Length(max=150)])
    submit = SubmitField('Save Provider')

    def validate_enabled(self, field):
        if self.provider_type.data == 'oidc' and field.data:
            raise ValidationError('OIDC configuration is reserved for the next SSO phase and cannot be enabled yet.')

    def validate_jit_enabled(self, field):
        if field.data:
            raise ValidationError('JIT provisioning remains disabled until RBAC role mapping is implemented.')


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
