"""Persistent, per-device Web Push subscriptions and VAPID identity."""

from __future__ import annotations

import base64
import json
import os
import secrets
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from pywebpush import webpush


def _directory() -> Path:
    return Path(os.environ.get("EFACE_PUSH_DIR", "/data/push"))


def _atomic(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{secrets.token_hex(8)}.tmp")
    try:
        with temporary.open("xb") as file:
            os.chmod(temporary, 0o600)
            file.write(value)
            file.flush()
            os.fsync(file.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def keys() -> tuple[Path, str]:
    private_path = _directory() / "vapid-private.pem"
    public_path = _directory() / "vapid-public.txt"
    if not private_path.is_file() or not public_path.is_file():
        private = ec.generate_private_key(ec.SECP256R1())
        private_pem = private.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
        public_raw = private.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
        public = base64.urlsafe_b64encode(public_raw).rstrip(b"=").decode("ascii")
        _atomic(private_path, private_pem)
        _atomic(public_path, public.encode("ascii"))
    return private_path, public_path.read_text(encoding="ascii").strip()


def load() -> dict:
    try:
        value = json.loads((_directory() / "subscriptions.json").read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save(value: dict) -> None:
    _atomic(_directory() / "subscriptions.json", json.dumps(value, separators=(",", ":")).encode())


def validate(subscription: object) -> dict:
    if not isinstance(subscription, dict) or not {"endpoint", "keys"}.issubset(subscription) or not set(subscription).issubset({"endpoint", "expirationTime", "keys"}):
        raise ValueError("Sottoscrizione push non valida")
    endpoint, key_values = subscription.get("endpoint"), subscription.get("keys")
    if not isinstance(endpoint, str) or not endpoint.startswith("https://") or len(endpoint) > 2048:
        raise ValueError("Endpoint push non valido")
    if not isinstance(key_values, dict) or set(key_values) != {"p256dh", "auth"}:
        raise ValueError("Chiavi push non valide")
    if any(not isinstance(key_values.get(key), str) or not 8 <= len(key_values[key]) <= 256 for key in ("p256dh", "auth")):
        raise ValueError("Chiavi push non valide")
    return subscription


def send(subscription: dict, payload: dict) -> bool:
    private_path, _ = keys()
    try:
        webpush(subscription_info=subscription, data=json.dumps(payload), vapid_private_key=str(private_path),
                vapid_claims={"sub": "mailto:push@e-control.tech"}, ttl=60,
                headers={"Urgency": "high", "Topic": "eface-intercom-call"})
        return True
    except Exception:
        return False
