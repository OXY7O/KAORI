from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired
from wtforms import BooleanField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional

from app.cluster.constants import ENVIRONMENTS

ENVIRONMENT_CHOICES = ENVIRONMENTS


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
