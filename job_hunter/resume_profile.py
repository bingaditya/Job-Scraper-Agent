from __future__ import annotations

import io
from dataclasses import dataclass, field

from docx import Document

from job_hunter.config import GroqConfig
from job_hunter.groq_client import chat_json
from job_hunter.keyword_utils import find_skills_line_index

_SYSTEM_PROMPT = (
    "You extract a candidate's profile from resume text for job-matching purposes. "
    'Return a JSON object with keys: "skills" (array of strings, individual skills or '
    'technologies actually mentioned in the resume), "preferred_titles" (array of 1-3 '
    "job titles that best describe roles this person is qualified for, based on their "
    'actual experience), "experience_years" (integer, best estimate of total '
    'professional experience, or null if unclear), and "summary" (one sentence). Only '
    "include skills and titles that are genuinely supported by the resume text — do "
    "not guess skills that aren't mentioned."
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


def _rule_based_extract(resume_text: str) -> ExtractedProfile:
    lines = resume_text.splitlines()
    skills_index = find_skills_line_index(lines)
    skills: list[str] = []
    if skills_index is not None:
        skills = [item.strip() for item in lines[skills_index].split(",") if item.strip()]
    return ExtractedProfile(skills=skills, mode="rules")
