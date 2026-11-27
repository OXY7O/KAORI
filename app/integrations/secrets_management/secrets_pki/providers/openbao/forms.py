"""OpenBao local connection form; no stored credential is hydrated."""

from flask_wtf import FlaskForm
from wtforms import PasswordField, StringField
from wtforms.validators import DataRequired, Length

from app.integrations.secrets_management.secrets_pki.providers.openbao.service import OpenBaoConnectionInput


class OpenBaoConnectionForm(FlaskForm):
    name = StringField('Connection Name', validators=[DataRequired(), Length(min=2, max=160)])
    endpoint = StringField('HTTPS Endpoint', validators=[DataRequired(), Length(max=500)])
    cluster_id = StringField('Expected Cluster UUID', validators=[DataRequired(), Length(min=36, max=36)])
    auth_mount = StringField('AppRole Mount', validators=[DataRequired(), Length(max=160)], default='approle')
    role_id = StringField('AppRole RoleID', validators=[DataRequired(), Length(max=255)])
    secret_id = PasswordField('AppRole SecretID', validators=[DataRequired(), Length(max=4096)])

    def to_input(self) -> OpenBaoConnectionInput:
        return OpenBaoConnectionInput(
            str(self.name.data or '').strip(),
            'external',
            str(self.endpoint.data or '').strip(),
            str(self.cluster_id.data or '').strip(),
            str(self.auth_mount.data or '').strip(),
            str(self.role_id.data or '').strip(),
            str(self.secret_id.data or ''),
        )
