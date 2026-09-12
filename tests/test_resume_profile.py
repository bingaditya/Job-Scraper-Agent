from __future__ import annotations

import unittest
from unittest.mock import patch

from job_hunter.config import GroqConfig
from job_hunter.resume_profile import extract_profile


class ResumeProfileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.groq_config = GroqConfig(api_key="fake-key")
        self.resume_text = (
            "Resume\n"
            "Professional Summary\n"
            "Backend engineer with 5 years of experience in Python services.\n"
            "Skills\n"
            "Python, SQL, Git, Docker\n"
        )

    @patch("job_hunter.resume_profile.chat_json")
    def test_groq_extraction_returns_structured_profile(self, mock_chat_json) -> None:
        mock_chat_json.return_value = {
            "skills": ["Python", "SQL", "Docker"],
            "preferred_titles": ["Backend Engineer", "Python Developer"],
            "experience_years": 5,
            "summary": "Backend engineer skilled in Python and Docker.",
        }
        profile = extract_profile(self.resume_text, self.groq_config)
        self.assertEqual(profile.mode, "groq")
        self.assertEqual(profile.skills, ["Python", "SQL", "Docker"])
        self.assertEqual(profile.preferred_titles, ["Backend Engineer", "Python Developer"])
        self.assertEqual(profile.experience_years, 5)

    @patch("job_hunter.resume_profile.chat_json")
    def test_falls_back_to_rules_when_groq_unavailable(self, mock_chat_json) -> None:
        mock_chat_json.return_value = None
        profile = extract_profile(self.resume_text, self.groq_config)
        self.assertEqual(profile.mode, "rules")
        self.assertEqual(profile.skills, ["Python", "SQL", "Git", "Docker"])
        self.assertIsNone(profile.experience_years)

    @patch("job_hunter.resume_profile.chat_json")
    def test_falls_back_when_groq_response_missing_skills_key(self, mock_chat_json) -> None:
        mock_chat_json.return_value = {"note": "malformed response"}
        profile = extract_profile(self.resume_text, self.groq_config)
        self.assertEqual(profile.mode, "rules")

    def test_rule_based_extract_with_no_skills_section(self) -> None:
        profile = extract_profile("Just a name and an objective statement.", GroqConfig())
        self.assertEqual(profile.mode, "rules")
        self.assertEqual(profile.skills, [])


if __name__ == "__main__":
    unittest.main()
