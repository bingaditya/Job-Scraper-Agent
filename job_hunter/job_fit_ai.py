from __future__ import annotations

from dataclasses import dataclass

from job_hunter.config import GroqConfig
from job_hunter.groq_client import chat_json

_DESCRIPTION_SNIPPET_LENGTH = 220

_SYSTEM_PROMPT = (
    "You judge whether job postings genuinely match a candidate's actual profession, not "
    "just shared buzzwords or tools. You will be given the candidate's profile (summary, "
    "preferred titles, skills) and a list of job postings, each with an id. For every job id "
    "given, decide how well the job matches the candidate's actual occupation and role "
    "family — not just whether a tool or keyword happens to appear in both. Score 80-100 "
    "only when the job is clearly the same occupation as the candidate's real experience. "
    "Score below 30 when the job is a different occupation that merely shares a generic tool "
    "or buzzword the candidate mentioned in passing (for example: a software tester's resume "
    "mentioning a programming language does not make a developer role in that language a "
    "good fit). Return a JSON object with a single key \"fit_scores\" mapping every given job "
    "id (as a string) to an integer 0-100. Include every id you were given, in any order."
)


@dataclass(slots=True)
class FitCandidate:
    job_id: str
    title: str
    company: str
    description: str


def rerank_by_fit(
    summary: str,
    preferred_titles: list[str],
    skills: list[str],
    candidates: list[FitCandidate],
    groq_config: GroqConfig,
) -> dict[str, int] | None:
    """Ask an LLM how well each candidate job actually fits the candidate's occupation.

    Returns a map of job_id -> fit score (0-100), or None on any failure (missing key,
    network error, malformed response) so callers can fall back to keyword-only scoring.
    """
    if not candidates:
        return None

    profile_lines = [
        f"Summary: {summary or 'N/A'}",
        f"Preferred titles: {', '.join(preferred_titles) or 'N/A'}",
        f"Skills: {', '.join(skills) or 'N/A'}",
        "",
        "Jobs:",
    ]
    for candidate in candidates:
        snippet = candidate.description[:_DESCRIPTION_SNIPPET_LENGTH].replace("\n", " ")
        profile_lines.append(
            f"- id: {candidate.job_id} | title: {candidate.title} | company: "
            f"{candidate.company} | description: {snippet}"
        )
    user_prompt = "\n".join(profile_lines)

    result = chat_json(_SYSTEM_PROMPT, user_prompt, groq_config, timeout=20)
    if result is None:
        return None

    raw_scores = result.get("fit_scores")
    if not isinstance(raw_scores, dict):
        return None

    scores: dict[str, int] = {}
    for job_id, value in raw_scores.items():
        if isinstance(value, (int, float)):
            scores[str(job_id)] = max(0, min(100, int(value)))
    return scores or None
