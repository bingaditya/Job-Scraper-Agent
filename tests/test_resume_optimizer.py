from __future__ import annotations

import unittest

from job_hunter.config import AIConfig, CandidateProfile
from job_hunter.models import JobListing, ResumeSuggestion
from job_hunter.resume_optimizer import ResumeOptimizer


class ResumeOptimizerTests(unittest.TestCase):
    def test_rule_based_tailoring_surfaces_missing_keywords(self) -> None:
        profile = CandidateProfile(
            name="Candidate",
            experience_years=4,
            skills=["Python", "Azure", "Snowflake"],
            preferred_titles=["Data Engineer"],
            preferred_locations=["Remote"],
            remote_first=True,
            resume_path=None,
        )
        optimizer = ResumeOptimizer(
            profile=profile,
            ai_config=AIConfig(ollama_model=None),
            resume_text="Experience with Python and SQL.",
        )
        job = JobListing(
            source="demo",
            source_id="1",
            title="Data Engineer",
            company="Acme",
            location="Remote",
            url="https://example.com/job",
            description="Need Azure and Snowflake delivery experience.",
            tags=["Azure", "Snowflake"],
            remote=True,
        )

        suggestion = optimizer.tailor(job, ["Azure", "Snowflake"])

        self.assertEqual(suggestion.mode, "rules")
        self.assertIn("Azure", suggestion.missing_resume_keywords)
        self.assertGreaterEqual(len(suggestion.bullet_suggestions), 1)

    def test_apply_tailoring_updates_summary_and_keyword_coverage(self) -> None:
        profile = CandidateProfile(
            name="Candidate",
            experience_years=4,
            skills=["Python", "Azure", "Snowflake", ".Net"],
            preferred_titles=["Data Engineer"],
            preferred_locations=["India"],
            remote_first=False,
            resume_path=None,
        )
        optimizer = ResumeOptimizer(
            profile=profile,
            ai_config=AIConfig(ollama_model=None),
            resume_text=(
                "# Candidate Resume\n\n"
                "## Area of Expertise\n\n"
                "- Python\n"
                "- Azure\n\n"
                "## Professional Experience\n\n"
                "- Built internal tools.\n"
            ),
        )
        job = JobListing(
            source="demo",
            source_id="2",
            title=".Net Developer",
            company="Acme",
            location="Noida, India",
            url="https://example.com/job",
            description="Need Azure, Python and .Net experience.",
            tags=["Azure", ".Net"],
            remote=False,
        )
        suggestion = ResumeSuggestion(
            mode="rules",
            summary="Emphasize Azure, Python and .Net.",
            keywords_to_emphasize=["Azure", "Python", ".Net"],
            missing_resume_keywords=[".Net"],
            bullet_suggestions=["Align summary with backend delivery."],
        )

        tailored_resume, fit_score, applied_keywords = optimizer.apply_tailoring(
            job=job,
            matched_skills=["Azure", "Python", ".Net"],
            suggestion=suggestion,
        )

        self.assertIn("## Professional Summary", tailored_resume)
        self.assertIn("- .Net", tailored_resume)
        self.assertEqual(fit_score, 100)
        self.assertIn(".Net", applied_keywords)


if __name__ == "__main__":
    unittest.main()
