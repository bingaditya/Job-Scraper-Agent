from __future__ import annotations

import unittest
from unittest.mock import patch

from job_hunter.config import GroqConfig
from job_hunter.job_fit_ai import FitCandidate, rerank_by_fit


class JobFitAiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.groq_config = GroqConfig(api_key="fake-key")
        self.candidates = [
            FitCandidate(job_id="1", title="QA Engineer", company="Acme", description="Selenium."),
            FitCandidate(job_id="2", title=".NET Developer", company="Beta", description="C#."),
        ]

    @patch("job_hunter.job_fit_ai.chat_json")
    def test_returns_parsed_and_clamped_scores(self, mock_chat_json) -> None:
        mock_chat_json.return_value = {"fit_scores": {"1": 95, "2": -10}}
        scores = rerank_by_fit("Software tester", ["QA Engineer"], ["Selenium"], self.candidates, self.groq_config)
        self.assertEqual(scores, {"1": 95, "2": 0})

    @patch("job_hunter.job_fit_ai.chat_json")
    def test_returns_none_when_chat_json_fails(self, mock_chat_json) -> None:
        mock_chat_json.return_value = None
        scores = rerank_by_fit("Software tester", ["QA Engineer"], ["Selenium"], self.candidates, self.groq_config)
        self.assertIsNone(scores)

    @patch("job_hunter.job_fit_ai.chat_json")
    def test_returns_none_when_response_missing_fit_scores_key(self, mock_chat_json) -> None:
        mock_chat_json.return_value = {"note": "malformed"}
        scores = rerank_by_fit("Software tester", ["QA Engineer"], ["Selenium"], self.candidates, self.groq_config)
        self.assertIsNone(scores)

    def test_returns_none_with_no_candidates(self) -> None:
        scores = rerank_by_fit("Software tester", [], [], [], self.groq_config)
        self.assertIsNone(scores)


if __name__ == "__main__":
    unittest.main()
