from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from flask_wtf import FlaskForm
from wtforms import BooleanField, IntegerField, PasswordField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, Length, NumberRange, Optional, ValidationError

from app.integrations.registry.providers.harbor.application.contracts import HarborRegistrationInput
from app.kubernetes.cluster.constants import ENVIRONMENTS

if TYPE_CHECKING:
    from app.models.harbor import HarborInstance


class HarborInstanceForm(FlaskForm):
    def __init__(self, *args, existing_instance: HarborInstance | None = None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.existing_instance = existing_instance
        if existing_instance is not None:
            self.password.render_kw = {
                **(self.password.render_kw or {}),
                'placeholder': 'Leave blank to keep the current password',
            }

    name = StringField(
        'Connection Name',
        validators=[DataRequired(), Length(min=2, max=160)],
        render_kw={'placeholder': 'Harbor Production'},
    )
    environment = SelectField('Environment', choices=ENVIRONMENTS, validators=[DataRequired()])
    description = TextAreaField(
        'Description',
        validators=[Optional(), Length(max=2000)],
        render_kw={'rows': 3, 'placeholder': 'Operational purpose and ownership context'},
    )
    endpoint = StringField(
        'Harbor API Endpoint',
        validators=[DataRequired(), Length(max=500)],
        render_kw={'placeholder': 'https://harbor.example.internal'},
    )
    auth_type = SelectField(
        'Authentication',
        choices=[
            ('basic', 'Basic Authentication'),
            ('anonymous', 'Anonymous / Public Read-Only'),
        ],
        default='basic',
        validators=[DataRequired()],
    )
    username = StringField(
        'Username',
        validators=[Optional(), Length(max=255)],
        render_kw={'placeholder': 'kaori-reader'},
    )
    password = PasswordField(
        'Password',
        validators=[Length(max=4096)],
        render_kw={'placeholder': 'Enter password'},
    )
    timeout = IntegerField(
        'Request Timeout',
        validators=[DataRequired(), NumberRange(min=1, max=30)],
        default=5,
    )
    verify_ssl = BooleanField('Verify TLS Certificate', default=True)
    enabled = BooleanField('Allow KAORI to Use This Connection', default=True)

    def validate_endpoint(self, field: StringField) -> None:
        endpoint = str(field.data or '').strip().rstrip('/')
        parsed = urlsplit(endpoint)
        if parsed.scheme not in {'http', 'https'} or not parsed.hostname:
            raise ValidationError('Endpoint must be a valid HTTP or HTTPS URL.')
        if parsed.username or parsed.password:
            raise ValidationError('Do not embed credentials in the Harbor endpoint URL.')
        if parsed.query or parsed.fragment:
            raise ValidationError('Endpoint must not include query parameters or a fragment.')
        field.data = endpoint

    def validate_username(self, field: StringField) -> None:
        if self.auth_type.data == 'basic' and not str(field.data or '').strip():
            raise ValidationError('Username is required for Basic Authentication.')

    def validate_password(self, field: PasswordField) -> None:
        if self.auth_type.data != 'basic':
            return
        submitted = str(field.data or '')
        current_password = (
            str(self.existing_instance.password)
            if self.existing_instance is not None and self.existing_instance.password is not None
            else ''
        )
        if not submitted and not current_password:
            raise ValidationError('Password is required for Basic Authentication.')

    def to_input(self, *, existing_instance: HarborInstance | None = None) -> HarborRegistrationInput:
        current = existing_instance or getattr(self, 'existing_instance', None)
        auth_type = str(self.auth_type.data or 'basic').strip().lower()
        username = str(self.username.data or '').strip() or None
        submitted_password = str(self.password.data or '')
        password = submitted_password or (
            str(current.password) if current is not None and current.password is not None else None
        )
        if auth_type == 'anonymous':
            username = None
            password = None
        return HarborRegistrationInput(
            name=str(self.name.data or '').strip(),
            environment=str(self.environment.data or '').strip(),
            description=str(self.description.data or '').strip() or None,
            endpoint=str(self.endpoint.data or '').strip().rstrip('/'),
            auth_type=auth_type,
            username=username,
            password=password,
            timeout=int(self.timeout.data or 5),
            verify_ssl=bool(self.verify_ssl.data),
            enabled=bool(self.enabled.data),
        )
