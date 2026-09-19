from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from job_hunter.api.routes_jobs import (
    get_groq_config,
    get_live_sources,
    get_raw_jobs_path,
    get_resume_store,
    router,
)
from job_hunter.auth import AuthUser, get_current_user
from job_hunter.config import GroqConfig
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
    # No Groq key by default: chat_json short-circuits to None, so the AI fit
    # reranker is a no-op and existing keyword-only tests are unaffected.
    app.dependency_overrides[get_groq_config] = lambda: GroqConfig(api_key=None)
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

    @patch("job_hunter.job_fit_ai.chat_json")
    def test_ai_fit_rerank_demotes_high_keyword_wrong_occupation_job(
        self, mock_chat_json
    ) -> None:
        # A tester's resume that also lists Java/SQL/Agile in passing will keyword-match
        # a ".NET Developer" posting (score ~44) more than an actual QA posting that only
        # mentions Selenium/TestNG (score ~32) -- exactly the reported bug. The AI reranker
        # should flip that order once it judges occupational fit.
        dotnet_job = JobListing(
            source="linkedin", source_id="dn1", title="Senior .NET Developer", company="Acme",
            location="Remote", url="https://example.com/dotnet",
            description="Java, SQL, Agile, .NET required.", tags=[], remote=True,
        )
        qa_job = JobListing(
            source="linkedin", source_id="qa1", title="QA Automation Engineer", company="Beta",
            location="Remote", url="https://example.com/qa",
            description="Selenium and TestNG experience required.", tags=[], remote=True,
        )
        mock_chat_json.return_value = {
            "fit_scores": {dotnet_job.fingerprint(): 10, qa_job.fingerprint(): 95}
        }

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "raw_jobs.json"
            path.write_text(
                json.dumps([dotnet_job.to_dict(), qa_job.to_dict()], indent=2),
                encoding="utf-8",
            )
            store = FakeStoreWithProfile(
                profile={
                    "skills": ["Java", "SQL", "Agile", "Selenium", "TestNG"],
                    "preferred_titles": ["Software Testing Engineer"],
                    "summary": "Software testing professional with Selenium automation experience.",
                }
            )
            app = _build_test_app(store, path)
            app.dependency_overrides[get_groq_config] = lambda: GroqConfig(api_key="fake-key")
            client = TestClient(app)

            resp = client.get("/api/jobs")
            self.assertEqual(resp.status_code, 200)
            jobs = resp.json()["jobs"]
            titles = [j["title"] for j in jobs]
            self.assertEqual(titles[0], "QA Automation Engineer")
            qa_result = next(j for j in jobs if j["title"] == "QA Automation Engineer")
            self.assertIn("AI fit score: 95/100", qa_result["reasons"])

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
