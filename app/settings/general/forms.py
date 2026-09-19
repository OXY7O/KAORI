from __future__ import annotations

from flask_wtf import FlaskForm
from wtforms import HiddenField, RadioField, SelectField, SubmitField
from wtforms.validators import DataRequired, Optional

from app.common.timezone import timezone_choices

_LOCALE_CHOICES = [
    ('en-US', 'English (United States)'),
    ('id-ID', 'Bahasa Indonesia (Indonesia)'),
]
_DATE_FORMAT_CHOICES = [
    ('day_month_year', '17 Jul 2026'),
    ('year_month_day', '2026-07-17'),
    ('day_month_numeric', '17/07/2026'),
    ('month_day_numeric', '07/17/2026'),
]
_TIME_FORMAT_CHOICES = [
    ('24h', '24-hour · 15:04'),
    ('12h', '12-hour · 03:04 PM'),
]


class TimezonePreferenceForm(FlaskForm):
    timezone_mode = RadioField(
        'Timezone source',
        choices=[
            ('automatic', 'Automatic from browser'),
            ('manual', 'Choose manually'),
        ],
        validators=[DataRequired()],
    )
    timezone = SelectField(
        'Manual timezone',
        choices=[(name, name) for name in timezone_choices()],
        validators=[Optional()],
    )
    browser_timezone = HiddenField()
    submit_timezone = SubmitField('Save')


class RegionalFormatForm(FlaskForm):
    locale = SelectField(
        'Regional locale',
        choices=_LOCALE_CHOICES,
        validators=[DataRequired()],
    )
    date_format = SelectField(
        'Date format',
        choices=_DATE_FORMAT_CHOICES,
        validators=[DataRequired()],
    )
    time_format = SelectField(
        'Time format',
        choices=_TIME_FORMAT_CHOICES,
        validators=[DataRequired()],
    )
    submit_regional = SubmitField('Save')
