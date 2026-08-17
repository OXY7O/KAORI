from __future__ import annotations

from flask_wtf import FlaskForm
from wtforms import BooleanField, HiddenField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional, Regexp


class RoleForm(FlaskForm):
    role_id = HiddenField()
    role_version = HiddenField()
    permission_scope = HiddenField()
    name = StringField(
        'Role Slug',
        validators=[
            DataRequired(),
            Length(min=2, max=80),
            Regexp(
                r'^[A-Za-z0-9 _-]+$',
                message='Use letters, numbers, spaces, hyphens, or underscores only.',
            ),
        ],
    )
    display_name = StringField('Display Name', validators=[DataRequired(), Length(min=2, max=120)])
    description = TextAreaField('Description', validators=[Optional(), Length(max=500)])
    is_active = BooleanField('Active')
    impact_acknowledged = BooleanField('I understand the access impact of deactivating this referenced role.')
    submit = SubmitField('Save Role')


class DeleteRoleForm(FlaskForm):
    role_id = HiddenField(validators=[DataRequired()])
    role_version = HiddenField(validators=[DataRequired()])
    submit = SubmitField('Delete Role')
