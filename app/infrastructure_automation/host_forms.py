"""CSRF-protected, credential-free host identity form (#5168)."""

from __future__ import annotations

from flask_wtf import FlaskForm
from wtforms import IntegerField, SelectField, StringField
from wtforms.validators import DataRequired, InputRequired, Length, NumberRange


class AutomationHostEnrollmentForm(FlaskForm):
    name = StringField(
        'Host Name',
        validators=[DataRequired(), Length(min=2, max=96)],
        render_kw={'placeholder': 'control-01'},
    )
    address = StringField(
        'Private IPv4 Address',
        validators=[DataRequired(), Length(max=45)],
        render_kw={'placeholder': '10.10.10.11'},
    )
    ssh_port = IntegerField(
        'SSH Port',
        default=22,
        validators=[InputRequired(), NumberRange(min=1, max=65535)],
    )
    role = SelectField(
        'Kubernetes Role',
        choices=[('control_plane', 'Control Plane'), ('worker', 'Worker')],
        validators=[DataRequired()],
    )
