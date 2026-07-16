from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    IntegerField,
    PasswordField,
    SelectField,
    StringField,
)
from wtforms.validators import (
    DataRequired,
    Length,
    NumberRange,
    Optional,
    ValidationError,
)


class PrometheusConfigForm(FlaskForm):
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
            ('automatic', 'Automatic — direct Prometheus endpoint'),
            ('manual', 'Manual — Prometheus-compatible intermediary'),
        ],
        default='automatic',
        validators=[DataRequired()],
    )

    source_prometheus_profile = SelectField(
        'Prometheus Source Version',
        choices=[
            ('', 'Select a supported major version'),
            ('prometheus-v2-kubernetes-v1', 'Prometheus 2.x'),
            ('prometheus-v3-kubernetes-v1', 'Prometheus 3.x'),
        ],
        default='',
        validators=[Optional()],
    )

    auth_type = SelectField(
        'Authentication',
        choices=[
            ('none', 'None'),
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
        'Timeout',
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
        'Verify SSL',
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
        if self.auth_type.data == 'basic' and not field.data:
            raise ValidationError(
                'Password is required',
            )

    def validate_bearer_token(
        self,
        field: PasswordField,
    ) -> None:
        if self.auth_type.data == 'bearer' and not field.data:
            raise ValidationError(
                'Bearer token is required',
            )


    def validate_source_prometheus_profile(self, field: SelectField) -> None:
        if self.version_detection_mode.data == 'manual' and not field.data:
            raise ValidationError(
                'Select the Prometheus major version used behind the intermediary endpoint.',
            )
