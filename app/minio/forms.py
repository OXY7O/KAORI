from __future__ import annotations

from urllib.parse import urlsplit

from flask_wtf import FlaskForm
from wtforms import BooleanField, IntegerField, PasswordField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, Length, NumberRange, Optional, ValidationError

from app.cluster.constants import ENVIRONMENTS
from app.integrations.minio.compatibility import SUPPORTED_RELEASE
from app.minio.contracts import MinioAlertBindingInput, MinioMetricsBindingInput, MinioRegistrationInput


class MinioInstanceForm(FlaskForm):
    name = StringField(
        'Connection Name',
        validators=[DataRequired(), Length(min=2, max=160)],
        render_kw={'placeholder': 'MinIO Production'},
    )
    environment = SelectField('Environment', choices=ENVIRONMENTS, validators=[DataRequired()])
    description = TextAreaField(
        'Description',
        validators=[Optional(), Length(max=2000)],
        render_kw={'rows': 3, 'placeholder': 'Operational purpose and ownership context'},
    )
    endpoint = StringField(
        'S3 API Endpoint',
        validators=[DataRequired(), Length(max=500)],
        render_kw={'placeholder': 'https://minio.example.internal'},
    )
    access_key = StringField(
        'Access Key',
        validators=[DataRequired(), Length(max=255)],
        render_kw={'placeholder': 'minio-reader'},
    )
    secret_key = PasswordField(
        'Secret Key',
        validators=[DataRequired(), Length(max=4096)],
        render_kw={'placeholder': 'Enter secret key'},
    )
    region = StringField(
        'S3 Region',
        validators=[DataRequired(), Length(max=80)],
        default='us-east-1',
        render_kw={'placeholder': 'us-east-1'},
    )
    addressing_style = SelectField(
        'S3 Addressing Style',
        choices=[('path', 'Path Style — Recommended for MinIO'), ('auto', 'Automatic')],
        default='path',
        validators=[DataRequired()],
    )
    timeout = IntegerField(
        'Request Timeout',
        validators=[DataRequired(), NumberRange(min=1, max=30)],
        default=5,
    )
    verify_ssl = BooleanField('Verify TLS Certificate', default=True)
    declared_release = StringField(
        'MinIO Server Release',
        validators=[DataRequired(), Length(max=96)],
        default=SUPPORTED_RELEASE,
        render_kw={'readonly': True},
    )
    enabled = BooleanField('Allow KAORI to Use This Connection', default=True)

    def validate_endpoint(self, field: StringField) -> None:
        endpoint = str(field.data or '').strip().rstrip('/')
        parsed = urlsplit(endpoint)
        if parsed.scheme not in {'http', 'https'} or not parsed.hostname:
            raise ValidationError('Endpoint must be a valid HTTP or HTTPS URL.')
        if parsed.username or parsed.password:
            raise ValidationError('Do not embed credentials in the MinIO endpoint URL.')
        if parsed.query or parsed.fragment:
            raise ValidationError('Endpoint must not include query parameters or a fragment.')
        field.data = endpoint

    def validate_declared_release(self, field: StringField) -> None:
        if str(field.data or '').strip() != SUPPORTED_RELEASE:
            raise ValidationError(f'This implementation currently supports {SUPPORTED_RELEASE}.')

    def to_input(self) -> MinioRegistrationInput:
        return MinioRegistrationInput(
            name=str(self.name.data or '').strip(),
            environment=str(self.environment.data or '').strip(),
            description=str(self.description.data or '').strip() or None,
            endpoint=str(self.endpoint.data or '').strip().rstrip('/'),
            access_key=str(self.access_key.data or '').strip(),
            secret_key=str(self.secret_key.data or ''),
            region=str(self.region.data or 'us-east-1').strip(),
            addressing_style=str(self.addressing_style.data or 'path').strip(),
            timeout=int(self.timeout.data or 5),
            verify_ssl=bool(self.verify_ssl.data),
            declared_release=str(self.declared_release.data or '').strip(),
            enabled=bool(self.enabled.data),
        )


class MinioMetricsBindingForm(FlaskForm):
    prometheus_instance_id = SelectField(
        'Prometheus Source',
        coerce=int,
        validators=[DataRequired()],
        choices=[],
    )
    selector_label = StringField(
        'Metrics Selector Label',
        validators=[DataRequired(), Length(max=120)],
        default='job',
        render_kw={'placeholder': 'job'},
    )
    selector_value = StringField(
        'Metrics Selector Value',
        validators=[DataRequired(), Length(max=255)],
        render_kw={'placeholder': 'minio-production'},
    )
    selector_operator = SelectField(
        'Selector Operator',
        choices=[('=', 'Equals (=)'), ('=~', 'Regex (=~)')],
        default='=',
        validators=[DataRequired()],
    )

    def to_input(self) -> MinioMetricsBindingInput:
        return MinioMetricsBindingInput(
            prometheus_instance_id=int(self.prometheus_instance_id.data),
            selector_label=str(self.selector_label.data or '').strip(),
            selector_value=str(self.selector_value.data or '').strip(),
            selector_operator=str(self.selector_operator.data or '=').strip(),
        )


class MinioAlertBindingForm(FlaskForm):
    alertmanager_instance_id = SelectField(
        'Alertmanager Source',
        coerce=int,
        validators=[DataRequired()],
        choices=[],
    )
    selector_label = StringField(
        'Alert Selector Label',
        validators=[DataRequired(), Length(max=120)],
        default='job',
        render_kw={'placeholder': 'job'},
    )
    selector_value = StringField(
        'Alert Selector Value',
        validators=[DataRequired(), Length(max=255)],
        render_kw={'placeholder': 'minio-production'},
    )
    selector_operator = SelectField(
        'Selector Operator',
        choices=[('=', 'Equals (=)'), ('=~', 'Regex (=~)')],
        default='=',
        validators=[DataRequired()],
    )

    def to_input(self) -> MinioAlertBindingInput:
        return MinioAlertBindingInput(
            alertmanager_instance_id=int(self.alertmanager_instance_id.data),
            selector_label=str(self.selector_label.data or '').strip(),
            selector_value=str(self.selector_value.data or '').strip(),
            selector_operator=str(self.selector_operator.data or '=').strip(),
        )
