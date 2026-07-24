from flask_wtf import FlaskForm
from wtforms import BooleanField, IntegerField, SelectMultipleField
from wtforms.validators import InputRequired, NumberRange, Optional


class JobPolicyForm(FlaskForm):
    enabled = BooleanField('Enable Automatic Execution')
    interval_minutes = IntegerField(
        'Execution Interval (Minutes)',
        validators=[InputRequired(), NumberRange(min=5, max=1440)],
    )
    analytics_time_ranges = SelectMultipleField(
        'Materialized Time Ranges',
        choices=[
            ('24h', '24 Hours'),
            ('7d', '7 Days'),
            ('30d', '30 Days'),
            ('60d', '60 Days'),
        ],
        validators=[Optional()],
    )
    forecast_history_windows = SelectMultipleField(
        'History Windows',
        choices=[('30d', '30 Days'), ('90d', '90 Days')],
        validators=[Optional()],
    )
    forecast_horizons = SelectMultipleField(
        'Forecast Horizons',
        choices=[('90d', '90 Days'), ('180d', '180 Days'), ('365d', '365 Days')],
        validators=[Optional()],
    )
    freshness_minutes = IntegerField(
        'Snapshot Freshness (Minutes)',
        validators=[Optional(), NumberRange(min=5, max=10080)],
    )
    stale_grace_minutes = IntegerField(
        'Stale Fallback Window (Minutes)',
        validators=[Optional(), NumberRange(min=15, max=43200)],
    )


class ManualJobRunForm(FlaskForm):
    """CSRF-protected request to dispatch a registered job manually."""
