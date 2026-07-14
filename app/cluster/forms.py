from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired
from wtforms import BooleanField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional

from app.cluster.constants import ENVIRONMENTS

ENVIRONMENT_CHOICES = ENVIRONMENTS
SECRET_REVEAL_POLICY_CHOICES = [
    ('disabled', 'Disabled'),
    ('step_up', 'Step-up authentication'),
    ('approval_required', 'Approval required'),
]


class ClusterCreateForm(FlaskForm):
    name = StringField(
        'Cluster Name',
        validators=[
            DataRequired(),
            Length(
                max=100,
            ),
        ],
    )

    environment = SelectField(
        'Environment',
        choices=ENVIRONMENT_CHOICES,
        validators=[
            DataRequired(),
        ],
    )

    description = TextAreaField(
        'Description',
        validators=[
            Optional(),
            Length(
                max=500,
            ),
        ],
    )

    kubeconfig = FileField(
        'Kubeconfig',
        validators=[
            FileRequired(),
        ],
    )

    kube_verify_ssl = BooleanField(
        'Verify Kubernetes API TLS Certificate',
        default=True,
    )

    kube_allow_weak_tls = BooleanField(
        'Allow legacy TLS certificate',
        default=False,
    )

    secret_reveal_policy = SelectField(
        'Protected Secret Reveal Policy',
        choices=SECRET_REVEAL_POLICY_CHOICES,
        default='disabled',
        validators=[DataRequired()],
    )

    secret_reveal_kubeconfig = FileField(
        'Dedicated Secret Reveal Kubeconfig',
        validators=[Optional()],
    )

    secret_reveal_encryption_verified = BooleanField(
        'Kubernetes Secret encryption at rest verified',
        default=False,
    )

    secret_reveal_audit_verified = BooleanField(
        'Kubernetes audit logging at Metadata level verified',
        default=False,
    )


class ClusterEditForm(FlaskForm):
    name = StringField(
        'Cluster Name',
        validators=[
            DataRequired(),
            Length(
                max=100,
            ),
        ],
    )

    environment = SelectField(
        'Environment',
        choices=ENVIRONMENT_CHOICES,
        validators=[
            DataRequired(),
        ],
    )

    description = TextAreaField(
        'Description',
        validators=[
            Optional(),
            Length(
                max=500,
            ),
        ],
    )

    kube_verify_ssl = BooleanField(
        'Verify Kubernetes API TLS Certificate',
        default=True,
    )

    kube_allow_weak_tls = BooleanField(
        'Allow legacy TLS certificate',
        default=False,
    )

    secret_reveal_policy = SelectField(
        'Protected Secret Reveal Policy',
        choices=SECRET_REVEAL_POLICY_CHOICES,
        default='disabled',
        validators=[DataRequired()],
    )

    secret_reveal_kubeconfig = FileField(
        'Dedicated Secret Reveal Kubeconfig',
        validators=[Optional()],
    )

    secret_reveal_encryption_verified = BooleanField(
        'Kubernetes Secret encryption at rest verified',
        default=False,
    )

    secret_reveal_audit_verified = BooleanField(
        'Kubernetes audit logging at Metadata level verified',
        default=False,
    )

    secret_reveal_remove_kubeconfig = BooleanField(
        'Remove dedicated Secret Reveal kubeconfig',
        default=False,
    )
