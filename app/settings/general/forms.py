from __future__ import annotations

from flask_wtf import FlaskForm
from wtforms import HiddenField, RadioField, SelectField, SubmitField
from wtforms.validators import DataRequired, Optional

from app.common.timezone import (
    date_format_choices,
    locale_choices,
    time_format_choices,
    timezone_choices,
)


class TimezonePreferenceForm(FlaskForm):
    timezone_mode = RadioField(
        "Timezone source",
        choices=[
            ("automatic", "Automatic from browser"),
            ("manual", "Choose manually"),
        ],
        validators=[DataRequired()],
    )
    timezone = SelectField(
        "Manual timezone",
        choices=[(name, name) for name in timezone_choices()],
        validators=[Optional()],
    )
    browser_timezone = HiddenField()
    submit_timezone = SubmitField("Save")


class RegionalFormatForm(FlaskForm):
    locale = SelectField(
        "Regional locale",
        choices=locale_choices(),
        validators=[DataRequired()],
    )
    date_format = SelectField(
        "Date format",
        choices=date_format_choices(),
        validators=[DataRequired()],
    )
    time_format = SelectField(
        "Time format",
        choices=time_format_choices(),
        validators=[DataRequired()],
    )
    submit_regional = SubmitField("Save")
