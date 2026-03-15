from __future__ import annotations

import unittest

from job_hunter.config import CandidateProfile, SearchConfig
from job_hunter.models import JobListing
from job_hunter.ranking import extract_required_years, job_matches_location, score_job


class RankingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.profile = CandidateProfile(
            name="Candidate",
            experience_years=4,
            skills=["Python", "Azure", "Snowflake"],
            preferred_titles=["Data Engineer"],
            preferred_locations=["Remote", "India"],
            remote_first=True,
            resume_path=None,
        )
        self.search = SearchConfig(
            keywords=["data engineer", "python"],
            min_score=45,
            top_n=25,
        )

    def test_extract_required_years(self) -> None:
        self.assertEqual(extract_required_years("Need 3+ years of Python experience"), 3)
        self.assertIsNone(extract_required_years("Strong engineering background required"))

    def test_strict_location_match_filters_non_india_jobs(self) -> None:
        india_only_profile = CandidateProfile(
            name="Candidate",
            experience_years=4,
            skills=["Python", "Azure", "Snowflake"],
            preferred_titles=["Data Engineer"],
            preferred_locations=["India", "Bengaluru"],
            remote_first=False,
            resume_path=None,
        )
        strict_search = SearchConfig(
            keywords=["data engineer", "python"],
            queries=["Data Engineer"],
            strict_location_match=True,
            min_score=45,
            top_n=25,
        )
        india_job = JobListing(
            source="demo",
            source_id="1",
            title="Data Engineer",
            company="Acme",
            location="Bengaluru, India",
            url="https://example.com/india-job",
            description="Python role in India",
            tags=["Python"],
            remote=False,
        )
        remote_job = JobListing(
            source="demo",
            source_id="2",
            title="Data Engineer",
            company="Acme",
            location="Remote",
            url="https://example.com/remote-job",
            description="Global remote role",
            tags=["Python"],
            remote=True,
        )

        self.assertTrue(job_matches_location(india_job, india_only_profile, strict_search))
        self.assertFalse(job_matches_location(remote_job, india_only_profile, strict_search))

    def test_score_rewards_skill_title_and_remote_fit(self) -> None:
        job = JobListing(
            source="demo",
            source_id="1",
            title="Senior Data Engineer",
            company="Acme",
            location="Remote",
            url="https://example.com/job",
            description="Python, Azure and Snowflake required with 4+ years experience.",
            tags=["Python"],
            remote=True,
        )

        score, reasons, matched_skills = score_job(job, self.profile, self.search)

        self.assertGreaterEqual(score, 70)
        self.assertIn("Python", matched_skills)
        self.assertTrue(any("Preferred title match" in reason for reason in reasons))


if __name__ == "__main__":
    unittest.main()
