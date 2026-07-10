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
