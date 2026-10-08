from __future__ import annotations

import hashlib
import secrets

from app.extensions.db import db
from app.models.integration import IntegrationInstance
from app.models.registry import RegistryWebhookEndpoint


def generate_webhook_token(integration_instance_id: int) -> str:
    identity = db.session.get(IntegrationInstance, integration_instance_id)
    if identity is None or identity.integration_type != 'registry':
        raise LookupError('Registry integration does not exist.')
    token = secrets.token_urlsafe(32)
    endpoint = db.session.get(RegistryWebhookEndpoint, integration_instance_id)
    if endpoint is None:
        endpoint = RegistryWebhookEndpoint()
        endpoint.integration_instance_id = integration_instance_id
        db.session.add(endpoint)
    endpoint.enabled = True
    endpoint.token_digest = hashlib.sha256(token.encode()).hexdigest()
    endpoint.last_error = None
    db.session.commit()
    return token


def disable_webhook(integration_instance_id: int) -> None:
    endpoint = db.session.get(RegistryWebhookEndpoint, integration_instance_id)
    if endpoint is None:
        endpoint = RegistryWebhookEndpoint()
        endpoint.integration_instance_id = integration_instance_id
        db.session.add(endpoint)
    endpoint.enabled = False
    endpoint.token_digest = None
    db.session.commit()
