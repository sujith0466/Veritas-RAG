"""Tests for Webhook Secret Cryptographic Utilities."""

import pytest
import os
from backend.core.security.webhook_crypto import (
    encrypt_webhook_secret,
    decrypt_webhook_secret,
    WebhookCryptoError,
)

def test_webhook_secret_roundtrip():
    plain_secret = "whsec_test_secret_1234567890abcdef"
    token = encrypt_webhook_secret(plain_secret)
    
    assert token.startswith("v1:")
    assert token != plain_secret
    
    decrypted = decrypt_webhook_secret(token)
    assert decrypted == plain_secret

def test_webhook_secret_empty_fails():
    with pytest.raises(WebhookCryptoError):
        encrypt_webhook_secret("")
    with pytest.raises(WebhookCryptoError):
        decrypt_webhook_secret("")

def test_webhook_secret_tamper_fails():
    plain_secret = "whsec_valid_key"
    token = encrypt_webhook_secret(plain_secret)
    parts = token.split(":")
    
    # Tamper with the ciphertext (parts[2])
    tampered_ct = parts[2][:-4] + "AAAA"
    tampered_token = f"v1:{parts[1]}:{tampered_ct}"
    
    with pytest.raises(WebhookCryptoError):
        decrypt_webhook_secret(tampered_token)

def test_webhook_secret_wrong_key(monkeypatch):
    plain_secret = "whsec_key_to_switch"
    token = encrypt_webhook_secret(plain_secret)
    
    # Change the encryption key
    monkeypatch.setenv("WEBHOOK_ENCRYPTION_KEY", "01234567890123456789012345678901")
    
    with pytest.raises(WebhookCryptoError):
        decrypt_webhook_secret(token)

def test_webhook_secret_malformed_token():
    with pytest.raises(WebhookCryptoError):
        decrypt_webhook_secret("not_a_valid_token")
    with pytest.raises(WebhookCryptoError):
        decrypt_webhook_secret("v2:invalid:version")
