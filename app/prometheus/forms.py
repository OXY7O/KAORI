from flask_wtf import FlaskForm
from wtforms import BooleanField, IntegerField, PasswordField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, Length, NumberRange, Optional, ValidationError

from app.models.prometheus import PrometheusInstance


class PrometheusConfigForm(FlaskForm):
    existing_instance: PrometheusInstance | None = None

    endpoint = StringField(
        'Endpoint',
        validators=[
            DataRequired(),
            Length(
                min=10,
                max=255,
            ),
        ],
        render_kw={
            'placeholder': 'http://localhost:9090',
        },
    )

    version_detection_mode = SelectField(
        'Compatibility Detection',
        choices=[
            ('automatic', 'Automatic — Direct Prometheus'),
            ('manual', 'Manual — Prometheus-Compatible Gateway'),
        ],
        default='automatic',
        validators=[DataRequired()],
    )

    source_prometheus_major = SelectField(
        'Prometheus Source Version',
        choices=[
            ('', 'Select Source Version'),
            ('2', 'Prometheus v2'),
            ('3', 'Prometheus v3'),
        ],
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
        validators=[
            Optional(),
            Length(max=255),
        ],
        render_kw={
            'placeholder': 'admin',
        },
    )

    password = PasswordField(
        'Password',
        validators=[
            Optional(),
            Length(max=255),
        ],
    )

    bearer_token = PasswordField(
        'Bearer Token',
        validators=[
            Optional(),
            Length(max=4096),
        ],
        render_kw={
            'placeholder': 'eyJhbGciOi...',
        },
    )

    timeout = IntegerField(
        'Request Timeout',
        validators=[
            DataRequired(),
            NumberRange(
                min=1,
                max=5,
            ),
        ],
        default=5,
    )

    verify_ssl = BooleanField(
        'Verify TLS Certificate',
        default=True,
    )

    def validate_endpoint(
        self,
        field: StringField,
    ) -> None:
        endpoint = (field.data or '').strip()

        if not endpoint.startswith(
            (
                'http://',
                'https://',
            )
        ):
            raise ValidationError(
                'Endpoint must start with http:// or https://',
            )

    def validate_username(
        self,
        field: StringField,
    ) -> None:
        if self.auth_type.data == 'basic' and not field.data:
            raise ValidationError(
                'Username is required',
            )

    def validate_password(
        self,
        field: PasswordField,
    ) -> None:
        existing = getattr(self, 'existing_instance', None)
        has_existing = bool(existing and existing.auth_type == 'basic' and existing.password)
        if self.auth_type.data == 'basic' and not field.data and not has_existing:
            raise ValidationError(
                'Password is required',
            )

    def validate_bearer_token(
        self,
        field: PasswordField,
    ) -> None:
        existing = getattr(self, 'existing_instance', None)
        has_existing = bool(existing and existing.auth_type == 'bearer' and existing.bearer_token)
        if self.auth_type.data == 'bearer' and not field.data and not has_existing:
            raise ValidationError(
                'Bearer token is required',
            )

    def validate_source_prometheus_major(self, field: SelectField) -> None:
        if self.version_detection_mode.data == 'manual' and not field.data:
            raise ValidationError(
                'Select the Prometheus major version used behind the intermediary endpoint.',
            )


class PrometheusInstanceForm(PrometheusConfigForm):
    name = StringField(
        'Instance Name',
        validators=[DataRequired(), Length(min=2, max=160)],
        render_kw={'placeholder': 'Prometheus Production'},
    )
    description = TextAreaField(
        'Description',
        validators=[Optional(), Length(max=2000)],
        render_kw={'rows': 3, 'placeholder': 'Operational purpose and ownership context'},
    )
    enabled = BooleanField('Allow KAORI to Use This Connection', default=True)
