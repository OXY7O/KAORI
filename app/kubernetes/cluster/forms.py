from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired
from wtforms import BooleanField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional

from app.kubernetes.cluster.constants import ENVIRONMENTS


class ClusterCreateForm(FlaskForm):
    name = StringField(
        'Connection Name',
        validators=[
            DataRequired(),
            Length(
                max=100,
            ),
        ],
        render_kw={'placeholder': 'Kubernetes Production'},
    )

    environment = SelectField(
        'Environment',
        choices=ENVIRONMENTS,
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
        render_kw={'placeholder': 'Operational purpose and ownership context'},
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
        choices=ENVIRONMENTS,
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
        'Replacement Kubeconfig',
        validators=[Optional()],
    )

    kube_verify_ssl = BooleanField(
        'Verify Kubernetes API TLS Certificate',
        default=True,
    )

    kube_allow_weak_tls = BooleanField(
        'Allow legacy TLS certificate',
        default=False,
    )
