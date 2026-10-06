from __future__ import annotations

from flask_wtf import FlaskForm
from wtforms import BooleanField, HiddenField, PasswordField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length, Optional

from app.access.authentication.password_policy import LOCAL_PASSWORD_MAX_LENGTH, LocalPasswordPolicy


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
