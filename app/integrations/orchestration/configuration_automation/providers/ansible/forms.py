"""WTForms validation for source-only Ansible Kubernetes Lifecycle registration."""

from __future__ import annotations

from flask_wtf import FlaskForm
from wtforms import SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional, Regexp

from app.integrations.orchestration.configuration_automation.providers.ansible.contract import (
    _NONPRODUCTION,
    AnsibleConnectionInput,
    require_registration_policy,
)
from app.integrations.source_control.source_control.providers.github.public_automation_source import (
    ANSIBLE_CORE_VERSION,
    ANSIBLE_RUNNER_VERSION,
    KUBESPRAY_RELEASE,
    PROFILE_KEY,
    REPOSITORY,
    SOURCE_CANDIDATE_SHA,
)
from app.kubernetes.cluster.constants import ENVIRONMENTS


class AnsibleSourceConnectionForm(FlaskForm):
    name = StringField('Connection Name', validators=[DataRequired(), Length(min=2, max=160)])
    description = TextAreaField('Description', validators=[Optional(), Length(max=1000)])
    environment = SelectField(
        'Environment',
        choices=[row for row in ENVIRONMENTS if row[0] in _NONPRODUCTION],
        validators=[DataRequired()],
    )
    profile_key = SelectField(
        'Automation Profile',
        choices=[(PROFILE_KEY, 'Kubernetes Lifecycle · Kubespray')],
        default=PROFILE_KEY,
        validators=[DataRequired()],
    )
    repository = StringField('Git Repository', default=REPOSITORY, validators=[DataRequired(), Length(max=120)])
    revision = StringField(
        'Git Commit SHA',
        default=SOURCE_CANDIDATE_SHA,
        validators=[DataRequired(), Regexp(r'^[a-f0-9]{40}$')],
    )
    ansible_core_version = SelectField(
        'Ansible Core Version',
        choices=[(ANSIBLE_CORE_VERSION, ANSIBLE_CORE_VERSION)],
        default=ANSIBLE_CORE_VERSION,
    )
    ansible_runner_version = SelectField(
        'Ansible Runner Version',
        choices=[(ANSIBLE_RUNNER_VERSION, ANSIBLE_RUNNER_VERSION)],
        default=ANSIBLE_RUNNER_VERSION,
    )
    kubespray_release = SelectField(
        'Kubespray Release', choices=[(KUBESPRAY_RELEASE, KUBESPRAY_RELEASE)], default=KUBESPRAY_RELEASE
    )
    execution_environment_digest = StringField('Execution Environment Digest', validators=[Optional()])
    source_test_proof = StringField('Source Validation Proof', validators=[Optional()])

    def to_input(self) -> AnsibleConnectionInput:
        values = AnsibleConnectionInput(
            name=str(self.name.data or '').strip(),
            description=str(self.description.data or '').strip() or None,
            environment=str(self.environment.data or '').strip(),
            profile_key=str(self.profile_key.data or '').strip(),
            repository=str(self.repository.data or '').strip(),
            revision=str(self.revision.data or '').strip(),
            ansible_core_version=str(self.ansible_core_version.data or '').strip(),
            ansible_runner_version=str(self.ansible_runner_version.data or '').strip(),
            kubespray_release=str(self.kubespray_release.data or '').strip(),
            execution_environment_digest=str(self.execution_environment_digest.data or '').strip() or None,
        )
        require_registration_policy(values)
        return values
