"""Sensitive, response-local MFA QR rendering; never call an external QR provider.

QR encodes the same canonical TOTP provisioning URI as the manual setup
workflow. Only return it after successful fresh-authenticated enrollment.
No QR, URI or seed is persisted, logged, or placed in a browser URL.
"""

from __future__ import annotations

import base64
from io import BytesIO

import qrcode

from app.access.authentication.mfa.factors import totp_provisioning_uri


def build_totp_qr_data_uri(secret: str, *, account_label: str) -> str:
    """Return a local PNG data URI encoding the one-time authenticator setup."""
    uri = totp_provisioning_uri(secret, account_label=account_label)
    qr = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=6,
        border=4,
    )
    qr.add_data(uri)
    qr.make(fit=True)
    output = BytesIO()
    qr.make_image(fill_color='black', back_color='white').save(output, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(output.getvalue()).decode('ascii')
