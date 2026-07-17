from __future__ import annotations

from flask_wtf import FlaskForm
from wtforms import BooleanField, HiddenField, PasswordField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, EqualTo, Length, Optional

AUTH_SOURCE_CHOICES = [
    ('database', 'Local Database'),
    ('ldap', 'LDAP / Active Directory (planned)'),
    ('sso', 'SSO / Identity Provider (planned)'),
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
