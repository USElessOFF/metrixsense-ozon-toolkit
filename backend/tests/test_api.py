
from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient


class TestHealth:
    
    @pytest.mark.asyncio
    async def test_health_ok(self, client: AsyncClient):
        """GET /health should return 200 with service info"""
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "MetrixSense"
        assert data["version"] == "1.0.0"

    @pytest.mark.asyncio
    async def test_health_method_not_allowed(self, client: AsyncClient):
        """POST /health should return 405"""
        resp = await client.post("/health")
        assert resp.status_code == 405


class TestAuthRegister:

    REGISTER_URL = "/auth/register"

    @pytest.mark.asyncio
    async def test_register_success(self, client: AsyncClient):
        """Register new user returns 201 with user data"""
        resp = await client.post(
            self.REGISTER_URL,
            json={"username": "newuser", "password": "password123"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["username"] == "newuser"
        assert data["is_active"] is True
        assert "id" in data

    @pytest.mark.asyncio
    async def test_register_duplicate(self, client: AsyncClient):
        """Register with existing username returns 409"""
        await client.post(
            self.REGISTER_URL,
            json={"username": "uniqueuser", "password": "pass123"},
        )
        resp = await client.post(
            self.REGISTER_URL,
            json={"username": "uniqueuser", "password": "pass456"},
        )
        assert resp.status_code == 409
        assert "already" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_register_short_password(self, client: AsyncClient):
        """Register with password < 4 chars returns 422"""
        resp = await client.post(
            self.REGISTER_URL,
            json={"username": "user123", "password": "ab"},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_register_missing_fields(self, client: AsyncClient):
        """Register without required fields returns 422"""
        resp = await client.post(
            self.REGISTER_URL,
            json={"username": "user123"},
        )
        assert resp.status_code == 422

        resp = await client.post(
            self.REGISTER_URL,
            json={"password": "password123"},
        )
        assert resp.status_code == 422


class TestAuthLogin:

    LOGIN_URL = "/auth/login"

    @pytest.mark.asyncio
    async def test_login_default_user(self, client: AsyncClient):
        """Login with default metrixsense:metrixsense returns 200 + token"""
        resp = await client.post(
            self.LOGIN_URL,
            json={"username": "metrixsense", "password": "metrixsense"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["token_type"] == "bearer"
        assert data["access_token"]
        assert "expires_in" in data

    @pytest.mark.asyncio
    async def test_login_after_register(self, client: AsyncClient):
        """Login after registration should work"""
        await client.post(
            "/auth/register",
            json={"username": "testlogin", "password": "testpass123"},
        )
        resp = await client.post(
            self.LOGIN_URL,
            json={"username": "testlogin", "password": "testpass123"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["access_token"]

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client: AsyncClient):
        """Login with wrong password returns 401"""
        resp = await client.post(
            self.LOGIN_URL,
            json={"username": "metrixsense", "password": "wrongpassword"},
        )
        assert resp.status_code == 401
        assert "invalid" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, client: AsyncClient):
        """Login with nonexistent user returns 401"""
        resp = await client.post(
            self.LOGIN_URL,
            json={"username": "ghostuser", "password": "password123"},
        )
        assert resp.status_code == 401


class TestAuthMe:

    ME_URL = "/auth/me"

    @pytest.mark.asyncio
    async def test_me_authenticated(self, client: AsyncClient, auth_headers: dict[str, Any]):
        """GET /auth/me with valid token returns user info"""
        resp = await client.get(self.ME_URL, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "metrixsense"
        assert data["is_active"] is True
        assert "id" in data
        assert "created_at" in data

    @pytest.mark.asyncio
    async def test_me_no_token(self, client: AsyncClient):
        """GET /auth/me without token returns 401"""
        resp = await client.get(self.ME_URL)
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_me_invalid_token(self, client: AsyncClient):
        """GET /auth/me with invalid token returns 401"""
        headers = {"Authorization": "Bearer invalidtoken123"}
        resp = await client.get(self.ME_URL, headers=headers)
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_me_expired_token(self, client: AsyncClient):
        """GET /auth/me with expired token returns 401"""
        # Manually crafted expired JWT
        expired = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwidXNlciI6Im1ldHJpeHNlbnNlIiwiZXhwIjoxNTAwMDAwMDAwfQ.xxx"
        headers = {"Authorization": f"Bearer {expired}"}
        resp = await client.get(self.ME_URL, headers=headers)
        assert resp.status_code == 401


class TestAuthLogout:

    @pytest.mark.asyncio
    async def test_logout_success(self, client: AsyncClient):
        """POST /auth/logout returns success message"""
        resp = await client.post("/auth/logout")
        assert resp.status_code == 200
        data = resp.json()
        assert "logged out" in data["message"].lower()


class TestSecrets:

    SECRETS_URL = "/api/secrets"

    @pytest.mark.asyncio
    async def test_get_secrets_no_auth(self, client: AsyncClient):
        """GET /api/secrets without auth returns 401"""
        resp = await client.get(self.SECRETS_URL)
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_get_secrets_empty(self, client: AsyncClient, auth_headers: dict[str, Any]):
        """GET /api/secrets with no stored secrets returns empty object"""
        resp = await client.get(self.SECRETS_URL, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)

    @pytest.mark.asyncio
    async def test_upsert_secrets(self, client: AsyncClient, auth_headers: dict[str, Any]):
        """POST /api/secrets stores secrets successfully"""
        secrets = {
            "seller_client_id": "test_seller_id",
            "seller_api_key": "test_seller_key",
        }
        resp = await client.post(
            self.SECRETS_URL,
            headers=auth_headers,
            json=secrets,
        )
        assert resp.status_code == 200

        # Verify stored secrets are returned masked (full keys never leave the server)
        resp = await client.get(self.SECRETS_URL, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("seller_client_id") == "te********r_id"
        assert data.get("seller_api_key") == "te********_key"

    @pytest.mark.asyncio
    async def test_secrets_user_isolation(self, client: AsyncClient, auth_headers: dict[str, Any]):
        """Secrets should be isolated per user"""
        # Store secrets for user1
        await client.post(
            self.SECRETS_URL,
            headers=auth_headers,
            json={"seller_client_id": "user1_secret"},
        )

        # Create second user and login
        await client.post(
            "/auth/register",
            json={"username": "user2", "password": "user2pass123"},
        )
        resp = await client.post(
            "/auth/login",
            json={"username": "user2", "password": "user2pass123"},
        )
        user2_headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}

        # User2 should not see user1's secrets
        resp = await client.get(self.SECRETS_URL, headers=user2_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("seller_client_id") is None


class TestSettings:

    SETTINGS_URL = "/api/settings"

    @pytest.mark.asyncio
    async def test_get_settings_no_auth(self, client: AsyncClient):
        """GET /api/settings without auth returns 401"""
        resp = await client.get(self.SETTINGS_URL)
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_get_settings_default(self, client: AsyncClient, auth_headers: dict[str, Any]):
        """GET /api/settings returns default settings"""
        resp = await client.get(self.SETTINGS_URL, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        # Should contain default fields
        assert "tax_system" in data
        assert "ad_budget_percent" in data

    @pytest.mark.asyncio
    async def test_upsert_settings(self, client: AsyncClient, auth_headers: dict[str, Any]):
        """POST /api/settings stores settings successfully"""
        settings: dict[str, Any] = {
            "tax_system": "usn_6",
            "ad_budget_percent": 10.5,
            "logistics_cost": 5.0,
            "fbo": True,
        }
        resp = await client.post(
            self.SETTINGS_URL,
            headers=auth_headers,
            json=settings,
        )
        assert resp.status_code == 200

        # Verify stored settings
        resp = await client.get(self.SETTINGS_URL, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["tax_system"] == "usn_6"
        assert data["ad_budget_percent"] == 10.5
        assert data["fbo"] is True

    @pytest.mark.asyncio
    async def test_settings_user_isolation(self, client: AsyncClient, auth_headers: dict[str, Any]):
        """Settings should be isolated per user"""
        # Store settings for user1
        await client.post(
            self.SETTINGS_URL,
            headers=auth_headers,
            json={"tax_system": "usn_15", "ad_budget_percent": 15.0},
        )

        # Create second user and login
        await client.post(
            "/auth/register",
            json={"username": "settings_user2", "password": "pass123"},
        )
        resp = await client.post(
            "/auth/login",
            json={"username": "settings_user2", "password": "pass123"},
        )
        user2_headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}

        # User2 should see default settings, not user1's
        resp = await client.get(self.SETTINGS_URL, headers=user2_headers)
        assert resp.status_code == 200
        data = resp.json()
        # Should be default values, not user1's
        assert data["tax_system"] != "osno"
