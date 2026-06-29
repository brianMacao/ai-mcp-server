"""Fernet-based symmetric encryption for api_key at rest.

Master key resolution priority:
1. Environment variable AI_MCP_MASTER_KEY (base64 Fernet key)
2. System keyring (service='ai-mcp-server', user='master-key')
3. Generate a new key and store it in the keyring
"""
from __future__ import annotations

import os

import keyring
from cryptography.fernet import Fernet, InvalidToken

_KEYRING_SERVICE = "ai-mcp-server"
_KEYRING_USER = "master-key"
_ENV_VAR = "AI_MCP_MASTER_KEY"


class MasterKeyError(RuntimeError):
    """Raised when master key cannot be obtained or decryption fails."""


def _get_or_create_key() -> bytes:
    env_value = os.environ.get(_ENV_VAR)
    if env_value:
        return env_value.encode("utf-8")
    try:
        stored = keyring.get_password(_KEYRING_SERVICE, _KEYRING_USER)
    except keyring.errors.KeyringError as e:  # pragma: no cover - platform specific
        raise MasterKeyError(
            f"Cannot access system keyring; set {_ENV_VAR} env var instead"
        ) from e
    if stored:
        return stored.encode("utf-8")
    new_key = Fernet.generate_key()
    try:
        keyring.set_password(_KEYRING_SERVICE, _KEYRING_USER, new_key.decode("utf-8"))
    except keyring.errors.KeyringError as e:  # pragma: no cover
        raise MasterKeyError(
            f"Cannot write to keyring; set {_ENV_VAR} env var instead"
        ) from e
    return new_key


def _cipher() -> Fernet:
    key = _get_or_create_key()
    try:
        return Fernet(key)
    except (ValueError, TypeError) as e:
        raise MasterKeyError(
            f"Invalid master key format. Expected base64 Fernet key (got: {len(key)} bytes)"
        ) from e


def encrypt(plaintext: str) -> bytes:
    """Encrypt api_key for storage."""
    return _cipher().encrypt(plaintext.encode("utf-8"))


def decrypt(ciphertext: bytes) -> str:
    """Decrypt api_key for outbound use. Raises MasterKeyError if key is wrong."""
    try:
        return _cipher().decrypt(ciphertext).decode("utf-8")
    except InvalidToken as e:
        raise MasterKeyError(
            "Cannot decrypt api_key. The master key has changed or the data is corrupt. "
            f"Re-add the endpoint, or restore {_ENV_VAR}."
        ) from e
