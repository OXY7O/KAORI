"""QR offers the canonical one-time TOTP provisioning secret locally (#3261)."""

from __future__ import annotations

import base64
from io import BytesIO

from PIL import Image

from app.access.authentication.mfa.factors import totp_provisioning_uri
from app.access.authentication.mfa.qr import build_totp_qr_data_uri


def test_local_qr_is_png_and_uri_is_never_a_remote_service_url() -> None:
    secret = 'JBSWY3DPEHPK3PXP'
    data_uri = build_totp_qr_data_uri(secret, account_label='mfa-uat-account')
    assert data_uri.startswith('data:image/png;base64,')
    assert secret not in data_uri
    assert 'otpauth://' not in data_uri
    assert 'http://' not in data_uri
    assert 'https://' not in data_uri

    encoded = data_uri.removeprefix('data:image/png;base64,')
    with Image.open(BytesIO(base64.b64decode(encoded))) as img:
        img.verify()
    with Image.open(BytesIO(base64.b64decode(encoded))) as img:
        assert img.format == 'PNG'
        assert img.size[0] >= 100 and img.size[1] >= 100
        assert img.size[0] == img.size[1]


def test_qr_reuses_vetted_totp_uri_contract_without_external_lookup() -> None:
    uri = totp_provisioning_uri('JBSWY3DPEHPK3PXP', account_label='uat:admin@example.test')
    assert uri.startswith('otpauth://totp/KAORI%3A')
    assert 'secret=JBSWY3DPEHPK3PXP' in uri
    assert 'issuer=KAORI' in uri
    assert 'algorithm=SHA1&digits=6&period=30' in uri
    assert 'admin%40example.test' in uri


def test_qr_function_preserves_provider_identity_boundary_and_no_network_calls() -> None:
    from pathlib import Path

    qr_source = (
        Path(__file__).resolve().parents[3] / 'app/access/authentication/mfa/qr.py'
    ).read_text(encoding='utf-8')
    assert 'totp_provisioning_uri(secret, account_label=account_label)' in qr_source
    assert 'qrcode.QRCode(' in qr_source
    assert 'requests' not in qr_source
    assert 'httpx' not in qr_source
    assert 'urlopen' not in qr_source
    assert 'external' in qr_source
