from typing import TYPE_CHECKING

from flask_wtf import FlaskForm
from wtforms import BooleanField, HiddenField, IntegerField, PasswordField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, Length, NumberRange, Optional, ValidationError

from app.integrations.observability.metrics_source.application.contracts import MetricsSourceConfigurationInput
from app.integrations.observability.metrics_source.providers import PROVIDERS, provider_definition, provider_keys

if TYPE_CHECKING:
    from app.models.metrics_source import MetricsSource


def _compatibility_profile_choices() -> list[tuple[str, str]]:
    choices: dict[str, str] = {}
    for definition in PROVIDERS.values():
        for value, label in definition.compatibility_profile_options:
            choices[value] = label
    return [('', 'Automatic / Not Required'), *sorted(choices.items(), key=lambda item: item[1].casefold())]


class MetricsSourceConfigForm(FlaskForm):
    _existing_instance: 'MetricsSource | None' = None

    provider_key = HiddenField('Metrics Provider', validators=[DataRequired()])

    endpoint = StringField(
        'Endpoint',
        validators=[DataRequired(), Length(min=10, max=500)],
        render_kw={'placeholder': 'https://metrics.example.internal'},
    )

    version_detection_mode = HiddenField(
        'Compatibility Detection',
        default='automatic',
        validators=[DataRequired()],
    )

    compatibility_profile_override = SelectField(
        'API Compatibility Profile',
        choices=_compatibility_profile_choices(),
        default='',
        validators=[Optional()],
    )

    auth_type = SelectField(
        'Authentication',
        choices=[
            ('none', 'No Authentication'),
            ('basic', 'Basic Authentication'),
            ('bearer', 'Bearer Token'),
        ],
        default='none',
    )

    username = StringField(
        'Username',
        validators=[Optional(), Length(max=255)],
        render_kw={'placeholder': 'service-account'},
    )
    password = PasswordField('Password', validators=[Optional(), Length(max=255)])
    bearer_token = PasswordField(
        'Bearer Token',
        validators=[Optional(), Length(max=4096)],
        render_kw={'placeholder': 'Enter bearer token'},
    )
    timeout = IntegerField(
        'Request Timeout',
        validators=[DataRequired(), NumberRange(min=1, max=5)],
        default=5,
    )
    verify_ssl = BooleanField('Verify TLS Certificate', default=True)

    def validate_provider_key(self, field: HiddenField) -> None:
        key = str(field.data or '').strip().lower()
        if key not in provider_keys():
            raise ValidationError('Select a supported metrics source provider.')

    def validate_version_detection_mode(self, field: HiddenField) -> None:
        expected = provider_definition(str(self.provider_key.data or '')).version_detection_mode
        if str(field.data or '').strip().lower() != expected:
            raise ValidationError('Metrics source compatibility mode does not match the selected provider contract.')

    def validate_compatibility_profile_override(self, field: SelectField) -> None:
        definition = provider_definition(str(self.provider_key.data or ''))
        allowed = {value for value, _label in definition.compatibility_profile_options}
        selected = str(field.data or '').strip()
        if definition.version_detection_mode == 'manual' and not selected:
            raise ValidationError('Select the API compatibility profile required by this metrics provider.')
        if selected and selected not in allowed:
            raise ValidationError('The selected API compatibility profile is not valid for this metrics provider.')

    def validate_endpoint(self, field: StringField) -> None:
        endpoint = (field.data or '').strip()
        if not endpoint.startswith(('http://', 'https://')):
            raise ValidationError('Endpoint must start with http:// or https://')

    def validate_username(self, field: StringField) -> None:
        if self.auth_type.data == 'basic' and not field.data:
            raise ValidationError('Username is required')

    def validate_password(self, field: PasswordField) -> None:
        existing = self._existing_instance
        has_existing = bool(existing and existing.auth_type == 'basic' and existing.password)
        if self.auth_type.data == 'basic' and not field.data and not has_existing:
            raise ValidationError('Password is required')

    def validate_bearer_token(self, field: PasswordField) -> None:
        existing = self._existing_instance
        has_existing = bool(existing and existing.auth_type == 'bearer' and existing.bearer_token)
        if self.auth_type.data == 'bearer' and not field.data and not has_existing:
            raise ValidationError('Bearer token is required')


class MetricsSourceForm(MetricsSourceConfigForm):
    name = StringField(
        'Connection Name',
        validators=[DataRequired(), Length(min=2, max=160)],
        render_kw={'placeholder': 'Production Metrics'},
    )
    description = TextAreaField(
        'Description',
        validators=[Optional(), Length(max=2000)],
        render_kw={'rows': 3, 'placeholder': 'Operational purpose and ownership context'},
    )
    enabled = BooleanField('Allow KAORI to Use This Connection', default=True)

    def to_configuration_input(self) -> MetricsSourceConfigurationInput:
        """Translate validated web-form state into the provider-neutral service contract."""
        return MetricsSourceConfigurationInput(
            name=(self.name.data or '').strip(),
            description=(self.description.data or '').strip() or None,
            provider_key=str(self.provider_key.data or '').strip().lower(),
            endpoint=(self.endpoint.data or '').strip(),
            compatibility_profile_override=(self.compatibility_profile_override.data or '').strip() or None,
            auth_type=str(self.auth_type.data or 'none').strip().lower(),
            username=(self.username.data or '').strip() or None,
            password=self.password.data or None,
            bearer_token=self.bearer_token.data or None,
            timeout=int(self.timeout.data or 5),
            verify_ssl=bool(self.verify_ssl.data),
            enabled=bool(self.enabled.data),
        )
