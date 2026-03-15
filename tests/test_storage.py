from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from job_hunter.models import JobListing, RankedJob, ResumeSuggestion
from job_hunter.storage import (
    load_resume_application_state,
    load_seen_job_ids,
    write_outputs,
)


class StorageTests(unittest.TestCase):
    def test_write_outputs_persists_dashboard_and_state(self) -> None:
        job = JobListing(
            source="demo",
            source_id="1",
            title="Data Engineer",
            company="Acme",
            location="Remote",
            url="https://example.com/job",
            description="Python and Azure",
            tags=["Python", "Azure"],
            remote=True,
        )
        ranked_job = RankedJob(
            job=job,
            score=88,
            reasons=["Matched skills: Python, Azure"],
            matched_skills=["Python", "Azure"],
            resume_suggestion=ResumeSuggestion(
                mode="rules",
                summary="Emphasize Python and Azure.",
                keywords_to_emphasize=["Python", "Azure"],
                missing_resume_keywords=[],
                bullet_suggestions=["Rewrite one bullet with measurable outcomes."],
            ),
        )
        summary = {
            "generated_at": "2026-03-15T00:00:00+00:00",
            "shortlisted_jobs": 1,
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            database_dir = root / "database"
            dashboard_dir = root / "dashboard"
            seen_ids = {job.fingerprint()}

            write_outputs(
                ranked_jobs=[ranked_job],
                summary=summary,
                seen_job_ids=seen_ids,
                database_dir=database_dir,
                dashboard_dir=dashboard_dir,
            )

            stored_jobs = json.loads((database_dir / "jobs.json").read_text(encoding="utf-8"))
            stored_summary = json.loads((dashboard_dir / "summary.json").read_text(encoding="utf-8"))
            stored_suggestions = json.loads(
                (dashboard_dir / "resume_suggestions.json").read_text(encoding="utf-8")
            )
            self.assertEqual(len(stored_jobs), 1)
            self.assertEqual(stored_summary["shortlisted_jobs"], 1)
            self.assertEqual(len(stored_suggestions), 1)
            self.assertEqual(load_seen_job_ids(database_dir / "state.json"), seen_ids)
            self.assertEqual(
                load_resume_application_state(database_dir / "resume_application_state.json"),
                {},
            )



if __name__ == "__main__":
    unittest.main()
