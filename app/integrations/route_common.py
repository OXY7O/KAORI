"""Shared blueprint identity for capability-first Integrations route modules."""

from flask import Blueprint

integrations_bp = Blueprint('integrations', __name__, url_prefix='/integrations')
