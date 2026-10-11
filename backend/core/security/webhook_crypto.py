"""Webhook Secret Cryptographic Utilities.

Provides authenticated AES-256-GCM symmetric encryption for webhook shared secrets at rest.
Derives a 256-bit encryption key using HKDF-SHA256 from the application secret key
or uses a dedicated WEBHOOK_ENCRYPTION_KEY if provided in the environment.
"""

import base64
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes

from backend.core.config import get_settings


class WebhookCryptoError(Exception):
    """Base exception for webhook cryptographic failures."""
    pass


def _get_encryption_key() -> bytes:
    """Derives or retrieves the 32-byte AES-256 key for webhook secrets."""
    # 1. Dedicated override key if provided (hex or base64 or raw 32 bytes)
    dedicated_key = os.getenv("WEBHOOK_ENCRYPTION_KEY")
    if dedicated_key:
        try:
            if len(dedicated_key) == 64:
                return bytes.fromhex(dedicated_key)
            elif len(dedicated_key) == 44 and dedicated_key.endswith("="):
                return base64.b64decode(dedicated_key)
            elif len(dedicated_key.encode("utf-8")) == 32:
                return dedicated_key.encode("utf-8")
        except Exception as e:
            raise WebhookCryptoError(f"Invalid WEBHOOK_ENCRYPTION_KEY format: {e}")

    # 2. Derive key from application secret key using HKDF-SHA256
    settings = get_settings()
    app_secret = getattr(settings.app, "secret_key", None)
    if not app_secret:
        raise WebhookCryptoError("No cryptographic key available: APP_SECRET_KEY is not configured.")

    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"veritas_rag_webhook_secret_salt_v1",
        info=b"webhook_symmetric_encryption_key",
    )
    return hkdf.derive(app_secret.encode("utf-8"))


def encrypt_webhook_secret(plain_secret: str) -> str:
    """Encrypts a plaintext webhook secret using AES-256-GCM.
    
    Returns:
        String format: 'v1:{base64(nonce)}:{base64(ciphertext_with_tag)}'
    """
    if not plain_secret:
        raise WebhookCryptoError("Cannot encrypt empty secret.")

    key = _get_encryption_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)  # 96-bit nonce recommended for GCM

    data = plain_secret.encode("utf-8")
    ciphertext = aesgcm.encrypt(nonce, data, None)

    nonce_b64 = base64.b64encode(nonce).decode("ascii")
    ct_b64 = base64.b64encode(ciphertext).decode("ascii")

    return f"v1:{nonce_b64}:{ct_b64}"


def decrypt_webhook_secret(encrypted_token: str) -> str:
    """Decrypts a webhook secret token created by encrypt_webhook_secret.
    
    Raises:
        WebhookCryptoError if token is malformed, tampering is detected, or decryption fails.
    """
    if not encrypted_token:
        raise WebhookCryptoError("Cannot decrypt empty token.")

    parts = encrypted_token.split(":")
    if len(parts) != 3 or parts[0] != "v1":
        raise WebhookCryptoError("Malformed or unsupported encrypted secret format.")

    try:
        nonce = base64.b64decode(parts[1])
        ciphertext = base64.b64decode(parts[2])
    except Exception as e:
        raise WebhookCryptoError(f"Base64 decoding failed for encrypted token: {e}")

    key = _get_encryption_key()
    aesgcm = AESGCM(key)

    try:
        decrypted_bytes = aesgcm.decrypt(nonce, ciphertext, None)
        return decrypted_bytes.decode("utf-8")
    except Exception as e:
        raise WebhookCryptoError(f"Decryption failed or ciphertext was tampered with: {e}")
