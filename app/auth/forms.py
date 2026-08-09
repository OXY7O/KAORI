from flask_wtf import FlaskForm
from wtforms import BooleanField, HiddenField, PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, EqualTo, Length


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
        validators=[DataRequired()],
    )

    new_password = PasswordField(
        'New Password',
        validators=[
            DataRequired(),
            Length(min=8, message='Password must be at least 8 characters.'),
        ],
    )

    confirm_password = PasswordField(
        'Confirm New Password',
        validators=[
            DataRequired(),
            EqualTo('new_password', message='Password confirmation does not match.'),
        ],
    )

    submit_password = SubmitField('Update Password')
