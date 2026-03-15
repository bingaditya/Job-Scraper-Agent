from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from job_hunter.dashboard_service import DashboardService


class DashboardServiceTests(unittest.TestCase):
    def test_tailor_resume_writes_resume_and_application_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "config").mkdir()
            (root / "database").mkdir()
            (root / "dashboard").mkdir()
            (root / "assets").mkdir()

            resume_path = root / "assets" / "resume.md"
            resume_path.write_text(
                "# Candidate Resume\n\n## Area of Expertise\n\n- Python\n\n",
                encoding="utf-8",
            )

            profile = {
                "candidate": {
                    "name": "Candidate",
                    "experience_years": 4,
                    "skills": ["Python", "Azure", ".Net"],
                    "preferred_titles": [".Net Developer"],
                    "preferred_locations": ["India", "Noida"],
                    "remote_first": False,
                    "resume_path": str(resume_path),
                },
                "search": {
                    "queries": [".Net Developer"],
                    "keywords": ["Python", "Azure", ".Net"],
                    "strict_location_match": True,
                    "min_score": 45,
                    "top_n": 25,
                },
                "sources": {"enabled": []},
                "notifications": {"telegram_enabled": False},
                "ai": {"ollama_model": ""},
            }
            (root / "config" / "profile.json").write_text(
                json.dumps(profile, indent=2),
                encoding="utf-8",
            )

            jobs_payload = [
                {
                    "score": 82,
                    "reasons": ["Preferred title match: .Net Developer"],
                    "matched_skills": ["Python", "Azure", ".Net"],
                    "job": {
                        "source": "demo",
                        "source_id": "1",
                        "title": ".Net Developer",
                        "company": "Acme",
                        "location": "Noida, India",
                        "url": "https://example.com/job",
                        "description": "Need Python, Azure and .Net experience.",
                        "tags": ["Python", "Azure", ".Net"],
                        "published_at": None,
                        "remote": False,
                        "metadata": {},
                        "fingerprint": "job-123",
                    },
                    "resume_suggestion": {
                        "mode": "rules",
                        "summary": "Emphasize Python, Azure and .Net.",
                        "keywords_to_emphasize": ["Python", "Azure", ".Net"],
                        "missing_resume_keywords": ["Azure", ".Net"],
                        "bullet_suggestions": ["Align summary to backend and cloud work."],
                    },
                }
            ]
            (root / "database" / "jobs.json").write_text(
                json.dumps(jobs_payload, indent=2),
                encoding="utf-8",
            )
            (root / "database" / "resume_suggestions.json").write_text("[]", encoding="utf-8")

            service = DashboardService(
                profile_path=root / "config" / "profile.json",
                database_dir=root / "database",
                dashboard_dir=root / "dashboard",
                workspace_dir=root,
            )

            result = service.tailor_resume("job-123")

            updated_resume = resume_path.read_text(encoding="utf-8")
            stored_state = json.loads(
                (root / "database" / "resume_application_state.json").read_text(encoding="utf-8")
            )

            self.assertEqual(result["resume_fit_score"], 100)
            self.assertIn("## Professional Summary", updated_resume)
            self.assertIn("- Azure", updated_resume)
            self.assertIn("job-123", stored_state)
            self.assertTrue(Path(result["backup_path"]).exists())


if __name__ == "__main__":
    unittest.main()

