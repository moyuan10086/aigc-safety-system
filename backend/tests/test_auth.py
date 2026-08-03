"""Tests for password hashing, signed sessions and auth endpoints."""

import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

import config
from routers.auth import _failures, router
from services import auth_service


class AuthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app = FastAPI()
        app.include_router(router)
        cls.client = TestClient(app)

    def setUp(self):
        _failures.clear()
        self.password = "Correct-Horse-2026"
        self.config = patch.multiple(
            config,
            AUTH_USERNAME="operator",
            AUTH_DISPLAY_NAME="审核员",
            AUTH_ROLE="operator",
            AUTH_PASSWORD_HASH=auth_service.hash_password(self.password, iterations=100_000),
            AUTH_SESSION_SECRET="test-session-secret-with-enough-entropy",
            AUTH_SESSION_TTL_SECONDS=3600,
            AUTH_COOKIE_SECURE=False,
        )
        self.config.start()

    def tearDown(self):
        self.config.stop()
        self.client.cookies.clear()

    def test_hash_verification(self):
        digest = auth_service.hash_password(self.password, iterations=100_000)
        self.assertTrue(auth_service.verify_password(self.password, digest))
        self.assertFalse(auth_service.verify_password("wrong", digest))

    def test_login_session_and_logout(self):
        login = self.client.post(
            "/api/auth/login",
            json={"username": "operator", "password": self.password},
        )
        self.assertEqual(login.status_code, 200)
        self.assertTrue(login.json()["authenticated"])
        self.assertIn("HttpOnly", login.headers["set-cookie"])

        session = self.client.get("/api/auth/session")
        self.assertTrue(session.json()["authenticated"])
        self.assertEqual(session.json()["user"]["display_name"], "审核员")

        logout = self.client.post("/api/auth/logout")
        self.assertEqual(logout.status_code, 200)
        self.assertFalse(self.client.get("/api/auth/session").json()["authenticated"])

    def test_invalid_credentials_and_tampered_cookie(self):
        invalid = self.client.post(
            "/api/auth/login",
            json={"username": "operator", "password": "wrong"},
        )
        self.assertEqual(invalid.status_code, 401)

        user = auth_service.current_user()
        token = auth_service.create_session(user, now=100)
        self.assertIsNotNone(auth_service.verify_session(token, now=101))
        self.assertIsNone(auth_service.verify_session(token + "x", now=101))
        self.assertIsNone(auth_service.verify_session(token, now=4000))

    def test_unconfigured_server_is_explicit(self):
        with patch.object(config, "AUTH_PASSWORD_HASH", ""):
            response = self.client.post(
                "/api/auth/login",
                json={"username": "operator", "password": self.password},
            )
        self.assertEqual(response.status_code, 503)
        self.assertIn("尚未配置", response.json()["detail"])

    def test_repeated_failures_are_rate_limited(self):
        for _ in range(5):
            response = self.client.post(
                "/api/auth/login",
                json={"username": "operator", "password": "wrong"},
            )
            self.assertEqual(response.status_code, 401)
        limited = self.client.post(
            "/api/auth/login",
            json={"username": "operator", "password": self.password},
        )
        self.assertEqual(limited.status_code, 429)
        self.assertEqual(limited.headers["retry-after"], "300")


if __name__ == "__main__":
    unittest.main()
