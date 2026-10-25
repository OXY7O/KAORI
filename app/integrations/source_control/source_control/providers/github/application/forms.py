"""GitHub App registration form using the existing Flask-WTF/KAORI fields."""

from __future__ import annotations

from flask_wtf import FlaskForm
from wtforms import BooleanField, PasswordField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional

from app.integrations.source_control.source_control.providers.github.registration import (
    GitHubConnectionInput,
)
from app.kubernetes.cluster.constants import ENVIRONMENTS


class GitHubAppConnectionForm(FlaskForm):
    name = StringField(
        'Connection Name', validators=[DataRequired(), Length(min=2, max=160)],
        render_kw={'placeholder': 'GitHub Production'},
    )
    environment = SelectField(
        'Environment', choices=ENVIRONMENTS, validators=[DataRequired()],
    )
    description = TextAreaField(
        'Description', validators=[Optional(), Length(max=2000)],
        render_kw={'rows': 3, 'placeholder': 'Operational purpose and ownership context'},
    )
    app_id = StringField(
        'GitHub App ID', validators=[DataRequired(), Length(max=80)],
        render_kw={'placeholder': '123456'},
    )
    installation_id = StringField(
        'Installation ID', validators=[DataRequired(), Length(max=80)],
        render_kw={'placeholder': '654321'},
    )
    account_id = StringField(
        'Organization / Account ID', validators=[DataRequired(), Length(max=80)],
        render_kw={'placeholder': '789012'},
    )
    private_key_pem = TextAreaField(
        'App Private Key (PEM)', validators=[DataRequired(), Length(max=20_000)],
        render_kw={'rows': 5, 'spellcheck': 'false', 'autocomplete': 'off'},
    )
    webhook_secret = PasswordField(
        'Webhook Secret', validators=[DataRequired(), Length(min=16, max=4096)],
        render_kw={'autocomplete': 'new-password'},
    )
    enabled = BooleanField('Allow KAORI to Use This Connection', default=True)

    def to_input(self) -> GitHubConnectionInput:
        return GitHubConnectionInput(
            name=str(self.name.data or '').strip(),
            environment=str(self.environment.data or '').strip(),
            description=str(self.description.data or '').strip() or None,
            app_id=str(self.app_id.data or '').strip(),
            installation_id=str(self.installation_id.data or '').strip(),
            account_id=str(self.account_id.data or '').strip(),
            private_key_pem=str(self.private_key_pem.data or ''),
            webhook_secret=str(self.webhook_secret.data or ''),
            enabled=bool(self.enabled.data),
        )

    def clear_sensitive_fields(self) -> None:
        """Prevent secret rehydration into a failed or successful POST response."""
        self.private_key_pem.data = ''
        self.webhook_secret.data = ''


class GitHubAppConnectionEditForm(FlaskForm):
    """Edit canonical connection settings without exposing shared App secrets."""

    name = StringField(
        'Connection Name', validators=[DataRequired(), Length(min=2, max=160)],
    )
    environment = SelectField(
        'Environment', choices=ENVIRONMENTS, validators=[DataRequired()],
    )
    description = TextAreaField(
        'Description', validators=[Optional(), Length(max=2000)],
        render_kw={'rows': 3},
    )
    enabled = BooleanField('Allow KAORI to Use This Connection')
