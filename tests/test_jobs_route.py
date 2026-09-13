from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from job_hunter.api.routes_jobs import (
    get_live_sources,
    get_raw_jobs_path,
    get_resume_store,
    router,
)
from job_hunter.auth import AuthUser, get_current_user
from job_hunter.models import JobListing
from job_hunter.sources.base import JobSource


class FakeStoreWithProfile:
    def __init__(self, profile: dict | None) -> None:
        self.profile = profile

    def get_candidate_profile(self, user_id: str) -> dict | None:
        return self.profile


class FakeLiveSource(JobSource):
    source_name = "fake-live"

    def __init__(self, jobs: list[JobListing]) -> None:
        super().__init__()
        self._jobs = jobs

    def fetch_jobs(
        self, queries: list[str], keywords: list[str], locations: list[str]
    ) -> list[JobListing]:
        return self._jobs


def _write_fixture_jobs(path: Path) -> None:
    jobs = [
        JobListing(
            source="arbeitnow",
            source_id="1",
            title="Senior Python Developer",
            company="Acme",
            location="Remote",
            url="https://example.com/1",
            description="Looking for Python and Docker experience.",
            tags=["python", "docker"],
            remote=True,
        ),
        JobListing(
            source="arbeitnow",
            source_id="2",
            title="Frontend React Developer",
            company="Beta",
            location="Remote",
            url="https://example.com/2",
            description="React, TypeScript, and CSS expertise required.",
            tags=["react", "typescript"],
            remote=True,
        ),
    ]
    path.write_text(json.dumps([job.to_dict() for job in jobs], indent=2), encoding="utf-8")


def _build_test_app(
    store, raw_jobs_path: Path, live_sources: list[JobSource] | None = None
) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: AuthUser(id="user-1")
    app.dependency_overrides[get_resume_store] = lambda: store
    app.dependency_overrides[get_raw_jobs_path] = lambda: raw_jobs_path
    # Default to no live sources so tests never make real network calls;
    # tests that care about the live-query merge pass their own fakes in.
    app.dependency_overrides[get_live_sources] = lambda: live_sources or []
    return app


class JobsRouteTests(unittest.TestCase):
    def test_no_resume_uploaded_returns_empty_with_message(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "raw_jobs.json"
            _write_fixture_jobs(path)
            store = FakeStoreWithProfile(profile=None)
            client = TestClient(_build_test_app(store, path))

            resp = client.get("/api/jobs")
            self.assertEqual(resp.status_code, 200)
            body = resp.json()
            self.assertEqual(body["jobs"], [])
            self.assertIn("Upload a resume", body["message"])

    def test_python_profile_matches_python_job_not_react_job(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "raw_jobs.json"
            _write_fixture_jobs(path)
            store = FakeStoreWithProfile(
                profile={
                    "skills": ["Python", "Docker"],
                    "preferred_titles": ["Python Developer"],
                    "experience_years": 4,
                }
            )
            client = TestClient(_build_test_app(store, path))

            resp = client.get("/api/jobs")
            self.assertEqual(resp.status_code, 200)
            jobs = resp.json()["jobs"]
            titles = [j["title"] for j in jobs]
            self.assertIn("Senior Python Developer", titles)
            self.assertNotIn("Frontend React Developer", titles)

    def test_react_profile_matches_react_job_not_python_job(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "raw_jobs.json"
            _write_fixture_jobs(path)
            store = FakeStoreWithProfile(
                profile={
                    "skills": ["React", "TypeScript"],
                    "preferred_titles": ["React Developer"],
                    "experience_years": 3,
                }
            )
            client = TestClient(_build_test_app(store, path))

            resp = client.get("/api/jobs")
            jobs = resp.json()["jobs"]
            titles = [j["title"] for j in jobs]
            self.assertIn("Frontend React Developer", titles)
            self.assertNotIn("Senior Python Developer", titles)

    def test_missing_raw_jobs_file_returns_empty_list(self) -> None:
        store = FakeStoreWithProfile(profile={"skills": ["Python"]})
        client = TestClient(_build_test_app(store, Path("/nonexistent/raw_jobs.json")))
        resp = client.get("/api/jobs")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["jobs"], [])

    def test_live_source_jobs_are_merged_with_shared_pool(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "raw_jobs.json"
            _write_fixture_jobs(path)
            store = FakeStoreWithProfile(
                profile={"skills": ["Go"], "preferred_titles": ["Go Developer"]}
            )
            live_job = JobListing(
                source="arbeitnow",
                source_id="3",
                title="Go Backend Developer",
                company="Gamma",
                location="Remote",
                url="https://example.com/3",
                description="Go and Kubernetes experience required.",
                tags=["go"],
                remote=True,
            )
            live_source = FakeLiveSource([live_job])
            client = TestClient(_build_test_app(store, path, live_sources=[live_source]))

            resp = client.get("/api/jobs")
            self.assertEqual(resp.status_code, 200)
            titles = [j["title"] for j in resp.json()["jobs"]]
            self.assertIn("Go Backend Developer", titles)

    def test_duplicate_live_job_already_in_shared_pool_is_not_repeated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "raw_jobs.json"
            _write_fixture_jobs(path)
            store = FakeStoreWithProfile(
                profile={"skills": ["Python"], "preferred_titles": ["Python Developer"]}
            )
            duplicate_job = JobListing(
                source="arbeitnow",
                source_id="1",
                title="Senior Python Developer",
                company="Acme",
                location="Remote",
                url="https://example.com/1",
                description="Looking for Python and Docker experience.",
                tags=["python", "docker"],
                remote=True,
            )
            live_source = FakeLiveSource([duplicate_job])
            client = TestClient(_build_test_app(store, path, live_sources=[live_source]))

            resp = client.get("/api/jobs")
            titles = [j["title"] for j in resp.json()["jobs"]]
            self.assertEqual(titles.count("Senior Python Developer"), 1)

    def test_failing_live_source_does_not_break_response(self) -> None:
        class BrokenSource(JobSource):
            source_name = "broken"

            def fetch_jobs(
                self, queries: list[str], keywords: list[str], locations: list[str]
            ) -> list[JobListing]:
                raise RuntimeError("upstream API is down")

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "raw_jobs.json"
            _write_fixture_jobs(path)
            store = FakeStoreWithProfile(
                profile={"skills": ["Python"], "preferred_titles": ["Python Developer"]}
            )
            client = TestClient(
                _build_test_app(store, path, live_sources=[BrokenSource()])
            )

            resp = client.get("/api/jobs")
            self.assertEqual(resp.status_code, 200)
            titles = [j["title"] for j in resp.json()["jobs"]]
            self.assertIn("Senior Python Developer", titles)


if __name__ == "__main__":
    unittest.main()
