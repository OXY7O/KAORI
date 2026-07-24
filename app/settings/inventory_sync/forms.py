from flask_wtf import FlaskForm
from wtforms import BooleanField, IntegerField
from wtforms.validators import InputRequired, NumberRange


class InventorySyncPolicyForm(FlaskForm):
    enabled = BooleanField('Enable Automatic Inventory Sync')
    interval_minutes = IntegerField(
        'Sync Interval (Minutes)',
        validators=[InputRequired(), NumberRange(min=5, max=1440)],
    )


class ManualInventorySyncForm(FlaskForm):
    """CSRF-protected manual fleet synchronization request."""
