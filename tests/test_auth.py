from __future__ import annotations

import time
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import HTTPException

from job_hunter.auth import PyJWKClient, get_current_user
from job_hunter.config import StorageConfig


def _fake_request(supabase_url: str | None) -> SimpleNamespace:
    storage = StorageConfig(supabase_url=supabase_url)
    return SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(config=SimpleNamespace(storage=storage)))
    )


def _credentials(token: str) -> SimpleNamespace:
    return SimpleNamespace(credentials=token)


def _generate_keypair():
    private_key = ec.generate_private_key(ec.SECP256R1())
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return private_pem, private_key.public_key()


class AuthTests(unittest.TestCase):
    def setUp(self) -> None:
        self.private_pem, self.public_key = _generate_keypair()
        self.other_private_pem, _ = _generate_keypair()  # simulates a forged/wrong key
        self.request = _fake_request("https://fake-project.supabase.co")

    def _sign(self, private_pem: bytes, **claims) -> str:
        payload = {"sub": "user-123", "aud": "authenticated", "exp": int(time.time()) + 3600}
        payload.update(claims)
        return jwt.encode(payload, private_pem, algorithm="ES256", headers={"kid": "test-key-1"})

    def _mock_signing_key(self):
        fake_signing_key = MagicMock()
        fake_signing_key.key = self.public_key
        return patch.object(
            PyJWKClient, "get_signing_key_from_jwt", return_value=fake_signing_key
        )

    def test_accepts_valid_token(self) -> None:
        token = self._sign(self.private_pem, email="test@example.com")
        with self._mock_signing_key():
            user = get_current_user(self.request, _credentials(token))
        self.assertEqual(user.id, "user-123")
        self.assertEqual(user.email, "test@example.com")

    def test_rejects_token_signed_with_wrong_key(self) -> None:
        # Signed with a different private key than the one JWKS "publishes".
        forged_token = self._sign(self.other_private_pem)
        with self._mock_signing_key():
            with self.assertRaises(HTTPException) as ctx:
                get_current_user(self.request, _credentials(forged_token))
        self.assertEqual(ctx.exception.status_code, 401)

    def test_rejects_expired_token(self) -> None:
        token = self._sign(self.private_pem, exp=int(time.time()) - 10)
        with self._mock_signing_key():
            with self.assertRaises(HTTPException) as ctx:
                get_current_user(self.request, _credentials(token))
        self.assertEqual(ctx.exception.status_code, 401)

    def test_rejects_missing_credentials(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            get_current_user(self.request, None)
        self.assertEqual(ctx.exception.status_code, 401)

    def test_rejects_when_server_missing_supabase_url(self) -> None:
        token = self._sign(self.private_pem)
        with self.assertRaises(HTTPException) as ctx:
            get_current_user(_fake_request(None), _credentials(token))
        self.assertEqual(ctx.exception.status_code, 500)


if __name__ == "__main__":
    unittest.main()
