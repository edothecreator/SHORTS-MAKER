"""Production Task 25.4: Load Test Configuration.

Locust-based load testing configuration for Shorts Engine Studio.
Simulates 50 concurrent users across multiple scenarios:
- Upload scenario
- Render scenario
- Download scenario

Performance thresholds:
- p95 < 2s for API endpoints
- p95 < 5min for render operations
- Error rate < 1% under normal load

Usage:
    locust -f backend/tests/load_test_config.py --host=http://localhost:8000
    locust -f backend/tests/load_test_config.py --host=https://api.shortsengine.com

    # Headless with 50 users:
    locust -f backend/tests/load_test_config.py \
        --host=http://localhost:8000 \
        --users 50 \
        --spawn-rate 5 \
        --run-time 5m \
        --headless
"""
from __future__ import annotations

import json
import os
import random
import time
from typing import Optional


try:
    from locust import HttpUser, task, between, events, tag
    from locust.runners import MasterRunner
    LOCUST_AVAILABLE = True
except ImportError:
    LOCUST_AVAILABLE = False
    # Provide stub classes for environments without locust installed
    class HttpUser:  # type: ignore[no-redef]
        pass
    def task(weight=1):  # type: ignore[no-redef]
        def decorator(func):
            return func
        return decorator if callable(weight) is False else (lambda f: f)
    def between(a, b):  # type: ignore[no-redef]
        return 1
    def tag(*tags):  # type: ignore[no-redef]
        def decorator(func):
            return func
        return decorator


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Performance thresholds
THRESHOLDS = {
    "api_p95_ms": 2000,        # p95 < 2 seconds for API calls
    "render_p95_ms": 300000,   # p95 < 5 minutes for render operations
    "error_rate_pct": 1.0,     # Error rate < 1%
    "upload_p95_ms": 10000,    # p95 < 10 seconds for upload presign
}

# Load test parameters
LOAD_CONFIG = {
    "target_users": 50,           # 50 concurrent users
    "spawn_rate": 5,              # Spawn 5 users per second
    "run_time_seconds": 300,      # Run for 5 minutes
    "scenarios": {
        "upload": {"weight": 3},   # 30% of users upload
        "render": {"weight": 4},   # 40% of users render
        "download": {"weight": 3}, # 30% of users download
    },
}

# Test data
TEST_ACCOUNTS = [
    {"email": f"loadtest-user-{i}@example.com", "password": "LoadTest123!"}
    for i in range(50)
]



# ---------------------------------------------------------------------------
# User Scenarios
# ---------------------------------------------------------------------------

if LOCUST_AVAILABLE:

    class UploadUser(HttpUser):
        """Simulates users uploading videos.

        Scenario: Login → Request presigned URL → Confirm upload → Wait
        Weight: 30% of total traffic
        """
        weight = 3
        wait_time = between(5, 15)

        def on_start(self):
            """Login and get auth token."""
            account = random.choice(TEST_ACCOUNTS)
            response = self.client.post(
                "/api/auth/login",
                json={
                    "email": account["email"],
                    "password": account["password"],
                },
                name="/api/auth/login",
            )
            if response.status_code == 200:
                data = response.json()
                token = data.get("access_token", data.get("token", ""))
                self.headers = {"Authorization": f"Bearer {token}"}
            else:
                # Try signup then login
                self.client.post("/api/auth/signup", json={
                    "email": account["email"],
                    "password": account["password"],
                    "name": f"Load Test User",
                })
                resp = self.client.post("/api/auth/login", json={
                    "email": account["email"],
                    "password": account["password"],
                })
                if resp.status_code == 200:
                    data = resp.json()
                    token = data.get("access_token", data.get("token", ""))
                    self.headers = {"Authorization": f"Bearer {token}"}
                else:
                    self.headers = {}

        @task(3)
        @tag("upload")
        def request_presigned_url(self):
            """Request a presigned URL for video upload."""
            self.client.post(
                "/api/upload/presign",
                headers=self.headers,
                json={
                    "filename": f"test-video-{random.randint(1, 10000)}.mp4",
                    "content_type": "video/mp4",
                    "file_size": random.randint(10_000_000, 500_000_000),
                },
                name="/api/upload/presign",
            )

        @task(2)
        @tag("upload")
        def list_projects(self):
            """List user's projects."""
            self.client.get(
                "/api/v1/projects",
                headers=self.headers,
                name="/api/v1/projects [GET]",
            )

        @task(1)
        @tag("upload")
        def check_credits(self):
            """Check remaining credits."""
            self.client.get(
                "/api/v1/credits",
                headers=self.headers,
                name="/api/v1/credits",
            )



    class RenderUser(HttpUser):
        """Simulates users triggering render jobs.

        Scenario: Login → Create project → Trigger render → Poll status
        Weight: 40% of total traffic
        """
        weight = 4
        wait_time = between(10, 30)

        def on_start(self):
            """Login and get auth token."""
            account = random.choice(TEST_ACCOUNTS)
            response = self.client.post(
                "/api/auth/login",
                json={
                    "email": account["email"],
                    "password": account["password"],
                },
                name="/api/auth/login",
            )
            if response.status_code == 200:
                data = response.json()
                token = data.get("access_token", data.get("token", ""))
                self.headers = {"Authorization": f"Bearer {token}"}
            else:
                self.headers = {}
            self.project_ids = []

        @task(2)
        @tag("render")
        def create_project(self):
            """Create a new project."""
            response = self.client.post(
                "/api/v1/projects",
                headers=self.headers,
                json={"title": f"Load Test Project {random.randint(1, 10000)}"},
                name="/api/v1/projects [POST]",
            )
            if response.status_code in (200, 201):
                data = response.json()
                pid = data.get("id", data.get("project_id"))
                if pid:
                    self.project_ids.append(pid)

        @task(3)
        @tag("render")
        def trigger_render(self):
            """Trigger render on an existing project."""
            if not self.project_ids:
                return
            project_id = random.choice(self.project_ids)
            self.client.post(
                f"/api/v1/projects/{project_id}/render",
                headers=self.headers,
                json={"segments": [0, 1, 2]},
                name="/api/v1/projects/{id}/render",
            )

        @task(5)
        @tag("render")
        def poll_status(self):
            """Poll render status (simulates SSE polling fallback)."""
            if not self.project_ids:
                return
            project_id = random.choice(self.project_ids)
            self.client.get(
                f"/api/v1/projects/{project_id}",
                headers=self.headers,
                name="/api/v1/projects/{id} [GET]",
            )

        @task(2)
        @tag("render")
        def score_segments(self):
            """Request virality scores for segments."""
            self.client.post(
                "/api/v1/score",
                headers=self.headers,
                json={
                    "segments": [
                        {
                            "transcript": "This is amazing content "
                                         "that everyone will love",
                            "start_sec": 0,
                            "end_sec": 30,
                            "title": f"Segment {i}",
                        }
                        for i in range(random.randint(1, 5))
                    ]
                },
                name="/api/v1/score",
            )



    class DownloadUser(HttpUser):
        """Simulates users downloading rendered clips.

        Scenario: Login → List projects → Get clips → Download
        Weight: 30% of total traffic
        """
        weight = 3
        wait_time = between(3, 10)

        def on_start(self):
            """Login and get auth token."""
            account = random.choice(TEST_ACCOUNTS)
            response = self.client.post(
                "/api/auth/login",
                json={
                    "email": account["email"],
                    "password": account["password"],
                },
                name="/api/auth/login",
            )
            if response.status_code == 200:
                data = response.json()
                token = data.get("access_token", data.get("token", ""))
                self.headers = {"Authorization": f"Bearer {token}"}
            else:
                self.headers = {}

        @task(3)
        @tag("download")
        def list_projects(self):
            """List available projects."""
            self.client.get(
                "/api/v1/projects",
                headers=self.headers,
                name="/api/v1/projects [GET]",
            )

        @task(4)
        @tag("download")
        def get_clips(self):
            """Get clips for a project (simulates download page load)."""
            self.client.get(
                "/api/v1/projects/latest/clips",
                headers=self.headers,
                name="/api/v1/projects/{id}/clips",
            )

        @task(2)
        @tag("download")
        def download_clip(self):
            """Request download URL for a clip."""
            self.client.get(
                "/api/v1/download/test-clip-id",
                headers=self.headers,
                name="/api/v1/download/{id}",
            )

        @task(1)
        @tag("download")
        def health_check(self):
            """Hit health endpoint (simulates keep-alive)."""
            self.client.get("/health", name="/health")


# ---------------------------------------------------------------------------
# Event Hooks — Threshold Validation
# ---------------------------------------------------------------------------

if LOCUST_AVAILABLE:

    @events.quitting.add_listener
    def check_thresholds(environment, **kwargs):
        """Validate performance thresholds after test run.

        Fails the load test if any threshold is exceeded.
        Exit code 1 = thresholds breached.
        """
        stats = environment.runner.stats
        failures = []

        for entry in stats.entries.values():
            # Check API p95 threshold
            if entry.name != "/health" and entry.num_requests > 0:
                p95 = entry.get_response_time_percentile(0.95) or 0
                if "render" not in entry.name.lower():
                    if p95 > THRESHOLDS["api_p95_ms"]:
                        failures.append(
                            f"{entry.name}: p95={p95}ms "
                            f"(threshold: {THRESHOLDS['api_p95_ms']}ms)"
                        )

        # Check overall error rate
        total_requests = stats.total.num_requests
        total_failures = stats.total.num_failures
        if total_requests > 0:
            error_rate = (total_failures / total_requests) * 100
            if error_rate > THRESHOLDS["error_rate_pct"]:
                failures.append(
                    f"Error rate: {error_rate:.2f}% "
                    f"(threshold: {THRESHOLDS['error_rate_pct']}%)"
                )

        if failures:
            print("\n" + "=" * 60)
            print("LOAD TEST FAILED — Thresholds Exceeded:")
            print("=" * 60)
            for f in failures:
                print(f"  FAIL: {f}")
            print("=" * 60 + "\n")
            environment.process_exit_code = 1
        else:
            print("\n" + "=" * 60)
            print("LOAD TEST PASSED — All thresholds met")
            print("=" * 60 + "\n")


# ---------------------------------------------------------------------------
# k6 Configuration (alternative to Locust)
# ---------------------------------------------------------------------------

K6_CONFIG = """
// k6 load test configuration (alternative to Locust)
// Usage: k6 run backend/tests/load_test_k6.js
//
// import http from 'k6/http';
// import { check, sleep } from 'k6';
//
// export const options = {
//   stages: [
//     { duration: '1m', target: 25 },   // Ramp up to 25 users
//     { duration: '3m', target: 50 },   // Hold at 50 users
//     { duration: '1m', target: 0 },    // Ramp down
//   ],
//   thresholds: {
//     http_req_duration: ['p(95)<2000'],  // p95 < 2s
//     http_req_failed: ['rate<0.01'],     // Error rate < 1%
//   },
// };
"""
