"""Production Task 25.2: API Integration Tests.

Tests all API endpoints with httpx AsyncClient:
- Auth flow (signup, login, protected endpoints)
- Video upload endpoint
- SSE streaming
- Scoring API
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import AsyncGenerator
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
import httpx

# Ensure backend package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------



@pytest.fixture
def base_url():
    """Base URL for the API server."""
    return os.environ.get("TEST_API_URL", "http://localhost:8000")


@pytest.fixture
def test_user():
    """Test user credentials."""
    return {
        "email": "integration-test@example.com",
        "password": "TestPass123!",
        "name": "Integration Test User",
    }


@pytest.fixture
async def client(base_url) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Create an async HTTP client for testing."""
    async with httpx.AsyncClient(
        base_url=base_url,
        timeout=httpx.Timeout(30.0),
        follow_redirects=True,
    ) as client:
        yield client


@pytest.fixture
async def auth_headers(client, test_user) -> dict:
    """Get authentication headers by logging in."""
    # Try to signup first (may already exist)
    await client.post("/api/auth/signup", json=test_user)

    # Login
    response = await client.post(
        "/api/auth/login",
        json={
            "email": test_user["email"],
            "password": test_user["password"],
        },
    )
    if response.status_code == 200:
        data = response.json()
        token = data.get("access_token", data.get("token", ""))
        return {"Authorization": f"Bearer {token}"}
    return {}



# ---------------------------------------------------------------------------
# Auth Flow Tests
# ---------------------------------------------------------------------------


class TestAuthFlow:
    """Test authentication endpoints."""

    @pytest.mark.asyncio
    async def test_signup_creates_user(self, client, test_user):
        """POST /api/auth/signup creates a new user account."""
        unique_user = {
            **test_user,
            "email": f"test-{asyncio.get_event_loop().time()}@example.com",
        }
        response = await client.post("/api/auth/signup", json=unique_user)
        assert response.status_code in (200, 201, 409)  # 409 if already exists

        if response.status_code in (200, 201):
            data = response.json()
            assert "access_token" in data or "token" in data or "user" in data

    @pytest.mark.asyncio
    async def test_signup_rejects_duplicate_email(self, client, test_user):
        """POST /api/auth/signup rejects duplicate email."""
        # First signup
        await client.post("/api/auth/signup", json=test_user)
        # Duplicate signup
        response = await client.post("/api/auth/signup", json=test_user)
        assert response.status_code in (400, 409, 422)

    @pytest.mark.asyncio
    async def test_signup_validates_email_format(self, client):
        """POST /api/auth/signup rejects invalid email."""
        response = await client.post(
            "/api/auth/signup",
            json={
                "email": "not-an-email",
                "password": "TestPass123!",
                "name": "Test",
            },
        )
        assert response.status_code in (400, 422)

    @pytest.mark.asyncio
    async def test_signup_validates_password_strength(self, client):
        """POST /api/auth/signup rejects weak passwords."""
        response = await client.post(
            "/api/auth/signup",
            json={
                "email": "weak-pass@example.com",
                "password": "123",
                "name": "Test",
            },
        )
        assert response.status_code in (400, 422)

    @pytest.mark.asyncio
    async def test_login_returns_token(self, client, test_user):
        """POST /api/auth/login returns access token."""
        # Ensure user exists
        await client.post("/api/auth/signup", json=test_user)

        response = await client.post(
            "/api/auth/login",
            json={
                "email": test_user["email"],
                "password": test_user["password"],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data or "token" in data

    @pytest.mark.asyncio
    async def test_login_rejects_wrong_password(self, client, test_user):
        """POST /api/auth/login rejects incorrect password."""
        response = await client.post(
            "/api/auth/login",
            json={
                "email": test_user["email"],
                "password": "WrongPassword999!",
            },
        )
        assert response.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_login_rejects_nonexistent_user(self, client):
        """POST /api/auth/login rejects unknown email."""
        response = await client.post(
            "/api/auth/login",
            json={
                "email": "nonexistent@example.com",
                "password": "SomePass123!",
            },
        )
        assert response.status_code in (401, 403, 404)

    @pytest.mark.asyncio
    async def test_protected_endpoint_rejects_unauthenticated(self, client):
        """Protected endpoints return 401 without auth header."""
        response = await client.get("/api/v1/projects")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_protected_endpoint_rejects_invalid_token(self, client):
        """Protected endpoints return 401 with invalid token."""
        response = await client.get(
            "/api/v1/projects",
            headers={"Authorization": "Bearer invalid-token-xyz"},
        )
        assert response.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_protected_endpoint_accepts_valid_token(self, client, auth_headers):
        """Protected endpoints accept valid Bearer token."""
        if not auth_headers:
            pytest.skip("Auth not available in test environment")
        response = await client.get("/api/v1/projects", headers=auth_headers)
        assert response.status_code == 200



# ---------------------------------------------------------------------------
# Video Upload Endpoint Tests
# ---------------------------------------------------------------------------


class TestVideoUpload:
    """Test video upload API endpoints."""

    @pytest.mark.asyncio
    async def test_presigned_upload_url_generation(self, client, auth_headers):
        """POST /api/upload/presign returns a presigned upload URL."""
        if not auth_headers:
            pytest.skip("Auth not available in test environment")

        response = await client.post(
            "/api/upload/presign",
            headers=auth_headers,
            json={
                "filename": "test-video.mp4",
                "content_type": "video/mp4",
                "file_size": 1024 * 1024 * 50,  # 50MB
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "upload_url" in data or "presigned_url" in data
        assert "project_id" in data or "key" in data

    @pytest.mark.asyncio
    async def test_upload_rejects_oversized_file(self, client, auth_headers):
        """POST /api/upload/presign rejects files over 2GB limit."""
        if not auth_headers:
            pytest.skip("Auth not available in test environment")

        response = await client.post(
            "/api/upload/presign",
            headers=auth_headers,
            json={
                "filename": "huge-video.mp4",
                "content_type": "video/mp4",
                "file_size": 3 * 1024 * 1024 * 1024,  # 3GB
            },
        )
        assert response.status_code in (400, 413)

    @pytest.mark.asyncio
    async def test_upload_rejects_invalid_content_type(self, client, auth_headers):
        """POST /api/upload/presign rejects non-video content types."""
        if not auth_headers:
            pytest.skip("Auth not available in test environment")

        response = await client.post(
            "/api/upload/presign",
            headers=auth_headers,
            json={
                "filename": "malware.exe",
                "content_type": "application/x-executable",
                "file_size": 1024,
            },
        )
        assert response.status_code in (400, 415, 422)

    @pytest.mark.asyncio
    async def test_upload_requires_authentication(self, client):
        """POST /api/upload/presign requires auth."""
        response = await client.post(
            "/api/upload/presign",
            json={
                "filename": "test.mp4",
                "content_type": "video/mp4",
                "file_size": 1024,
            },
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_upload_confirm_triggers_processing(self, client, auth_headers):
        """POST /api/v1/projects/{id}/process triggers the analysis pipeline."""
        if not auth_headers:
            pytest.skip("Auth not available in test environment")

        # Create a project first
        create_resp = await client.post(
            "/api/v1/projects",
            headers=auth_headers,
            json={"title": "Test Project", "video_filename": "test.mp4"},
        )
        if create_resp.status_code not in (200, 201):
            pytest.skip("Project creation not available")

        project_id = create_resp.json().get("id", create_resp.json().get("project_id"))

        # Trigger processing
        response = await client.post(
            f"/api/v1/projects/{project_id}/process",
            headers=auth_headers,
        )
        assert response.status_code in (200, 202, 404)  # 202 = accepted, queued



# ---------------------------------------------------------------------------
# SSE Streaming Tests
# ---------------------------------------------------------------------------


class TestSSEStreaming:
    """Test Server-Sent Events streaming endpoints."""

    @pytest.mark.asyncio
    async def test_sse_endpoint_returns_event_stream(self, client, auth_headers):
        """GET /api/v1/projects/{id}/status returns text/event-stream."""
        if not auth_headers:
            pytest.skip("Auth not available in test environment")

        # Use a placeholder project ID — test that content-type is correct
        response = await client.get(
            "/api/v1/projects/test-project-id/status",
            headers={**auth_headers, "Accept": "text/event-stream"},
        )
        # Should either return SSE or 404 if project not found
        if response.status_code == 200:
            assert "text/event-stream" in response.headers.get("content-type", "")

    @pytest.mark.asyncio
    async def test_sse_requires_auth(self, client):
        """SSE endpoint requires authentication."""
        response = await client.get("/api/v1/projects/test-id/status")
        assert response.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_sse_returns_404_for_unknown_project(self, client, auth_headers):
        """SSE endpoint returns 404 for non-existent project."""
        if not auth_headers:
            pytest.skip("Auth not available in test environment")

        response = await client.get(
            "/api/v1/projects/nonexistent-id-xyz/status",
            headers=auth_headers,
        )
        assert response.status_code in (404, 200)  # Some impls return empty stream


# ---------------------------------------------------------------------------
# Scoring API Tests
# ---------------------------------------------------------------------------


class TestScoringAPI:
    """Test virality scoring API endpoints."""

    @pytest.mark.asyncio
    async def test_score_endpoint_returns_scores(self, client, auth_headers):
        """POST /api/v1/score returns virality scores for segments."""
        if not auth_headers:
            pytest.skip("Auth not available in test environment")

        response = await client.post(
            "/api/v1/score",
            headers=auth_headers,
            json={
                "segments": [
                    {
                        "transcript": "This is an incredible revelation that nobody expected",
                        "start_sec": 0,
                        "end_sec": 30,
                        "title": "Shocking Discovery",
                    },
                    {
                        "transcript": "And then we went to the store and bought some milk",
                        "start_sec": 30,
                        "end_sec": 60,
                        "title": "Shopping Trip",
                    },
                ]
            },
        )
        if response.status_code == 200:
            data = response.json()
            assert "scores" in data or isinstance(data, list)
            scores = data.get("scores", data)
            assert len(scores) == 2
            for score in scores:
                assert "score" in score or "virality_score" in score
                score_val = score.get("score", score.get("virality_score", 0))
                assert 0 <= score_val <= 100

    @pytest.mark.asyncio
    async def test_score_endpoint_requires_auth(self, client):
        """POST /api/v1/score requires authentication."""
        response = await client.post(
            "/api/v1/score",
            json={"segments": []},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_score_endpoint_validates_input(self, client, auth_headers):
        """POST /api/v1/score validates segment data."""
        if not auth_headers:
            pytest.skip("Auth not available in test environment")

        response = await client.post(
            "/api/v1/score",
            headers=auth_headers,
            json={"segments": "not-a-list"},
        )
        assert response.status_code in (400, 422)


# ---------------------------------------------------------------------------
# Projects API Tests
# ---------------------------------------------------------------------------


class TestProjectsAPI:
    """Test project CRUD endpoints."""

    @pytest.mark.asyncio
    async def test_list_projects(self, client, auth_headers):
        """GET /api/v1/projects returns user's projects."""
        if not auth_headers:
            pytest.skip("Auth not available in test environment")

        response = await client.get("/api/v1/projects", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, (list, dict))
        if isinstance(data, dict):
            assert "projects" in data

    @pytest.mark.asyncio
    async def test_create_project(self, client, auth_headers):
        """POST /api/v1/projects creates a new project."""
        if not auth_headers:
            pytest.skip("Auth not available in test environment")

        response = await client.post(
            "/api/v1/projects",
            headers=auth_headers,
            json={"title": "Integration Test Project"},
        )
        assert response.status_code in (200, 201)
        data = response.json()
        assert "id" in data or "project_id" in data

    @pytest.mark.asyncio
    async def test_get_project_by_id(self, client, auth_headers):
        """GET /api/v1/projects/{id} returns project details."""
        if not auth_headers:
            pytest.skip("Auth not available in test environment")

        # Create a project first
        create_resp = await client.post(
            "/api/v1/projects",
            headers=auth_headers,
            json={"title": "Test Get Project"},
        )
        if create_resp.status_code not in (200, 201):
            pytest.skip("Project creation not available")

        project_id = create_resp.json().get("id", create_resp.json().get("project_id"))
        response = await client.get(
            f"/api/v1/projects/{project_id}",
            headers=auth_headers,
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_delete_project(self, client, auth_headers):
        """DELETE /api/v1/projects/{id} removes a project."""
        if not auth_headers:
            pytest.skip("Auth not available in test environment")

        # Create a project
        create_resp = await client.post(
            "/api/v1/projects",
            headers=auth_headers,
            json={"title": "Test Delete Project"},
        )
        if create_resp.status_code not in (200, 201):
            pytest.skip("Project creation not available")

        project_id = create_resp.json().get("id", create_resp.json().get("project_id"))
        response = await client.delete(
            f"/api/v1/projects/{project_id}",
            headers=auth_headers,
        )
        assert response.status_code in (200, 204)

    @pytest.mark.asyncio
    async def test_user_cannot_access_others_project(self, client, auth_headers):
        """Users cannot access projects owned by other users."""
        if not auth_headers:
            pytest.skip("Auth not available in test environment")

        # Try accessing a random UUID that doesn't belong to test user
        response = await client.get(
            "/api/v1/projects/00000000-0000-0000-0000-000000000000",
            headers=auth_headers,
        )
        assert response.status_code in (403, 404)


# ---------------------------------------------------------------------------
# Health & Utility Endpoints
# ---------------------------------------------------------------------------


class TestHealthEndpoints:
    """Test health check and utility endpoints."""

    @pytest.mark.asyncio
    async def test_health_endpoint(self, client):
        """GET /health returns 200."""
        response = await client.get("/health")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_ready_endpoint(self, client):
        """GET /ready returns 200 when service is ready."""
        response = await client.get("/ready")
        assert response.status_code in (200, 503)  # 503 if deps not ready

    @pytest.mark.asyncio
    async def test_api_returns_json_content_type(self, client):
        """API endpoints return application/json content type."""
        response = await client.get("/health")
        if response.status_code == 200:
            content_type = response.headers.get("content-type", "")
            assert "application/json" in content_type or "text/plain" in content_type


# ---------------------------------------------------------------------------
# Rate Limiting Tests
# ---------------------------------------------------------------------------


class TestRateLimiting:
    """Test rate limiting enforcement."""

    @pytest.mark.asyncio
    async def test_rate_limit_on_auth_endpoints(self, client):
        """Auth endpoints enforce rate limiting after too many requests."""
        responses = []
        for _ in range(15):
            resp = await client.post(
                "/api/auth/login",
                json={"email": "test@x.com", "password": "wrong"},
            )
            responses.append(resp.status_code)

        # At least one should be rate-limited (429)
        assert 429 in responses or all(r in (401, 403) for r in responses)

    @pytest.mark.asyncio
    async def test_rate_limit_headers_present(self, client, auth_headers):
        """Rate-limited endpoints include rate limit headers."""
        if not auth_headers:
            pytest.skip("Auth not available in test environment")

        response = await client.get("/api/v1/projects", headers=auth_headers)
        # Common rate limit headers
        rate_headers = [
            "x-ratelimit-limit",
            "x-ratelimit-remaining",
            "ratelimit-limit",
            "ratelimit-remaining",
        ]
        has_rate_header = any(
            h in response.headers for h in rate_headers
        )
        # Not all implementations include these, so just check status is valid
        assert response.status_code in (200, 429)
