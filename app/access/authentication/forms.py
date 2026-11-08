from flask_wtf import FlaskForm
from wtforms import BooleanField, HiddenField, PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, EqualTo, Length

from app.access.authentication.password_policy import LOCAL_PASSWORD_MAX_LENGTH, LocalPasswordPolicy


# Form for user login
class LoginForm(FlaskForm):
    next = HiddenField()

    username = StringField('Username', validators=[DataRequired(), Length(max=100)])

    password = PasswordField('Password', validators=[DataRequired(), Length(max=1024)])

    remember = BooleanField('Remember Me')

    submit = SubmitField('Sign In')


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField(
        'Current Password',
        validators=[DataRequired(), Length(max=LOCAL_PASSWORD_MAX_LENGTH)],
    )

    new_password = PasswordField(
        'New Password',
        validators=[
            DataRequired(),
            LocalPasswordPolicy(),
        ],
    )

    confirm_password = PasswordField(
        'Confirm New Password',
        validators=[
            DataRequired(),
            Length(max=LOCAL_PASSWORD_MAX_LENGTH),
            EqualTo('new_password', message='Password confirmation does not match.'),
        ],
    )

    submit_password = SubmitField('Update Password')


class MfaChallengeForm(FlaskForm):
    verification_code = StringField(
        'Authenticator or Recovery Code', validators=[DataRequired(), Length(min=6, max=64)]
    )
    submit = SubmitField('Verify & Sign In')
