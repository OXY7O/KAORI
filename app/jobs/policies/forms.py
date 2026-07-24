from flask_wtf import FlaskForm
from wtforms import BooleanField, IntegerField
from wtforms.validators import InputRequired, NumberRange


class JobPolicyForm(FlaskForm):
    enabled = BooleanField('Enable Automatic Execution')
    interval_minutes = IntegerField(
        'Execution Interval (Minutes)',
        validators=[InputRequired(), NumberRange(min=5, max=1440)],
    )


class ManualJobRunForm(FlaskForm):
    """CSRF-protected request to dispatch a registered job manually."""
