from __future__ import annotations

import io
from dataclasses import dataclass, field

from docx import Document

from job_hunter.config import GroqConfig
from job_hunter.groq_client import chat_json
from job_hunter.keyword_utils import find_skills_line_index, looks_like_skill_list

_SYSTEM_PROMPT = (
    "You extract a candidate's profile from resume text for job-matching purposes. "
    'Return a JSON object with keys: "skills" (array of strings, individual skills or '
    'technologies actually mentioned in the resume), "preferred_titles" (array of 1-3 '
    "job titles that best describe roles this person is qualified for), "
    '"experience_years" (integer, best estimate of total professional experience, or '
    'null if unclear), and "summary" (one sentence). Only include skills and titles '
    "that are genuinely supported by the resume text — do not guess skills that aren't "
    "mentioned. IMPORTANT for preferred_titles and summary: they must reflect the "
    "candidate's dominant, demonstrated occupation — the role in their actual job "
    "title(s), repeated section headers, and where most of their hands-on experience "
    "lies — never a different occupation just because a technology or tool for that "
    "occupation is mentioned in passing (e.g. listed as 'familiar with' or used only in "
    "one small project). A tool mentioned only in passing belongs in skills, not in "
    "preferred_titles. For example, a Software Testing / QA Engineer whose resume "
    "mentions being familiar with a programming language is still a Software Testing "
    "/ QA Engineer, not a developer in that language."
)


@dataclass(slots=True)
class ExtractedProfile:
    skills: list[str] = field(default_factory=list)
    preferred_titles: list[str] = field(default_factory=list)
    experience_years: int | None = None
    summary: str = ""
    mode: str = "rules"


def docx_to_text(docx_bytes: bytes) -> str:
    document = Document(io.BytesIO(docx_bytes))
    return "\n".join(p.text for p in document.paragraphs if p.text.strip())


def extract_profile(resume_text: str, groq_config: GroqConfig) -> ExtractedProfile:
    result = chat_json(_SYSTEM_PROMPT, resume_text[:8000], groq_config)
    if result is not None:
        skills = result.get("skills")
        if isinstance(skills, list) and all(isinstance(item, str) for item in skills):
            experience_years = result.get("experience_years")
            return ExtractedProfile(
                skills=[item.strip() for item in skills if item.strip()],
                preferred_titles=[
                    str(item).strip()
                    for item in result.get("preferred_titles", [])
                    if str(item).strip()
                ],
                experience_years=(
                    int(experience_years)
                    if isinstance(experience_years, (int, float))
                    else None
                ),
                summary=str(result.get("summary") or "").strip(),
                mode="groq",
            )
    return _rule_based_extract(resume_text)


_TITLE_GUESS_MAX_LINES = 5
_TITLE_GUESS_MAX_LENGTH = 60
_TITLE_GUESS_HEADER_DENYLIST = {
    "summary",
    "professional summary",
    "career objective",
    "objective",
    "profile",
    "about me",
    "contact",
    "contact information",
    "personal details",
    "technical skills",
    "skills",
    "education",
    "experience",
    "work experience",
    "project experience",
}


def _guess_headline_title(lines: list[str]) -> list[str]:
    """Best-effort title guess for the no-AI fallback path.

    Resumes very commonly put the candidate's headline role on one of the first few
    lines (right under their name). Skips lines that look like contact info (an "@" or
    mostly digits, e.g. a phone number) or a generic resume section header rather than
    an actual job title.
    """
    checked = 0
    for raw_line in lines:
        text = raw_line.strip()
        if not text:
            continue
        checked += 1
        if checked > _TITLE_GUESS_MAX_LINES:
            break
        if len(text) > _TITLE_GUESS_MAX_LENGTH or "@" in text:
            continue
        if text.lower() in _TITLE_GUESS_HEADER_DENYLIST:
            continue
        if looks_like_skill_list(text):
            continue
        digit_count = sum(character.isdigit() for character in text)
        if digit_count > len(text) / 4:
            continue
        if checked == 1:
            # First non-empty line is almost always the candidate's name, not a title.
            continue
        return [text]
    return []


def _rule_based_extract(resume_text: str) -> ExtractedProfile:
    lines = resume_text.splitlines()
    skills_index = find_skills_line_index(lines)
    skills: list[str] = []
    if skills_index is not None:
        skills = [item.strip() for item in lines[skills_index].split(",") if item.strip()]
    preferred_titles = _guess_headline_title(lines)
    return ExtractedProfile(skills=skills, preferred_titles=preferred_titles, mode="rules")
