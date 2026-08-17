from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from flask_wtf import FlaskForm
from wtforms import BooleanField, IntegerField, PasswordField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, Length, NumberRange, Optional, ValidationError

from app.integrations.storage.object_storage.providers.minio.application.contracts import MinioRegistrationInput
from app.integrations.storage.object_storage.providers.minio.compatibility import (
    PROFILE_LABEL,
    SUPPORTED_RELEASE,
    SUPPORTED_RELEASE_RANGE_LABEL,
    evaluate_minio_release,
)
from app.kubernetes.cluster.constants import ENVIRONMENTS

if TYPE_CHECKING:
    from app.models.minio import MinioInstance


class MinioInstanceForm(FlaskForm):
    def __init__(self, *args, existing_instance: MinioInstance | None = None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.existing_instance = existing_instance
        if existing_instance is not None:
            self.secret_key.render_kw = {
                **(self.secret_key.render_kw or {}),
                'placeholder': 'Leave blank to keep the current secret key',
            }

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
        validators=[Length(max=4096)],
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
        description=f'Profile · {PROFILE_LABEL} · Supported Range · {SUPPORTED_RELEASE_RANGE_LABEL}',
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

    def validate_secret_key(self, field: PasswordField) -> None:
        if self.existing_instance is None and not str(field.data or '').strip():
            raise ValidationError('Secret Key is required for a new MinIO connection.')

    def validate_declared_release(self, field: StringField) -> None:
        compatibility = evaluate_minio_release(str(field.data or '').strip(), product='minio')
        if compatibility.readiness != 'ready':
            raise ValidationError(compatibility.message)

    def to_input(self, *, existing_instance: MinioInstance | None = None) -> MinioRegistrationInput:
        current = existing_instance or getattr(self, 'existing_instance', None)
        submitted_secret = str(self.secret_key.data or '')
        secret_key = submitted_secret or (str(current.secret_key) if current is not None else '')
        return MinioRegistrationInput(
            name=str(self.name.data or '').strip(),
            environment=str(self.environment.data or '').strip(),
            description=str(self.description.data or '').strip() or None,
            endpoint=str(self.endpoint.data or '').strip().rstrip('/'),
            access_key=str(self.access_key.data or '').strip(),
            secret_key=secret_key,
            region=str(self.region.data or 'us-east-1').strip(),
            addressing_style=str(self.addressing_style.data or 'path').strip(),
            timeout=int(self.timeout.data or 5),
            verify_ssl=bool(self.verify_ssl.data),
            declared_release=str(self.declared_release.data or '').strip(),
            enabled=bool(self.enabled.data),
        )
