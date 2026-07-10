from __future__ import annotations

from flask_wtf import FlaskForm
from wtforms import BooleanField, HiddenField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional


class RoleForm(FlaskForm):
    role_id = HiddenField()
    name = StringField('Role Slug', validators=[DataRequired(), Length(max=80)])
    display_name = StringField('Display Name', validators=[DataRequired(), Length(max=120)])
    description = TextAreaField('Description', validators=[Optional(), Length(max=500)])
    is_active = BooleanField('Active')
    submit = SubmitField('Save Role')
