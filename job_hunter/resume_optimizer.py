from __future__ import annotations

import json
import re
from pathlib import Path

import requests

from job_hunter.config import AIConfig, CandidateProfile
from job_hunter.models import JobListing, ResumeSuggestion


class ResumeOptimizer:
    def __init__(
        self,
        profile: CandidateProfile,
        ai_config: AIConfig,
        resume_text: str,
    ) -> None:
        self.profile = profile
        self.ai_config = ai_config
        self.resume_text = resume_text

    @classmethod
    def from_profile(
        cls,
        profile: CandidateProfile,
        ai_config: AIConfig,
    ) -> "ResumeOptimizer":
        resume_text = ""
        if profile.resume_path:
            resume_file = Path(profile.resume_path)
            if resume_file.exists():
                resume_text = resume_file.read_text(encoding="utf-8")
        return cls(profile=profile, ai_config=ai_config, resume_text=resume_text)

    def tailor(self, job: JobListing, matched_skills: list[str]) -> ResumeSuggestion:
        if self.ai_config.ollama_model:
            ai_suggestion = self._tailor_with_ollama(job, matched_skills)
            if ai_suggestion is not None:
                return ai_suggestion
        return self._rule_based_tailoring(job, matched_skills)

    def apply_tailoring(
        self,
        job: JobListing,
        matched_skills: list[str],
        suggestion: ResumeSuggestion | None = None,
    ) -> tuple[str, int, list[str]]:
        suggestion = suggestion or self.tailor(job, matched_skills)
        tailored_resume = None
        if self.ai_config.ollama_model:
            tailored_resume = self._rewrite_resume_with_ollama(job, suggestion)
        if tailored_resume is None:
            tailored_resume = self._apply_rule_based_resume(job, suggestion)

        tailored_resume = self._with_tailoring_comment(tailored_resume, job, suggestion)
        tailored_resume = self._upsert_section(
            tailored_resume,
            heading="## Professional Summary",
            body_lines=self._build_professional_summary(job, suggestion),
            insert_before="## Area of Expertise",
        )
        tailored_resume = self._ensure_expertise_keywords(
            tailored_resume,
            suggestion.keywords_to_emphasize,
        )

        fit_score = self.resume_fit_score(
            tailored_resume,
            suggestion.keywords_to_emphasize,
        )
        applied_keywords = self._present_keywords(
            tailored_resume,
            suggestion.keywords_to_emphasize,
        )
        self.resume_text = tailored_resume
        return tailored_resume, fit_score, applied_keywords

    def _rule_based_tailoring(
        self,
        job: JobListing,
        matched_skills: list[str],
    ) -> ResumeSuggestion:
        emphasized = matched_skills[:5] or self.profile.skills[:3]
        missing_keywords = [
            skill
            for skill in emphasized
            if skill.lower() not in self.resume_text.lower()
        ]
        summary = (
            f"Target {job.title} at {job.company} by foregrounding "
            f"{', '.join(emphasized)} and mirroring the role language without adding new claims."
        )
        bullet_suggestions = [
            (
                f"Rewrite one impact bullet to connect {skill} to a measurable delivery,"
                " such as data pipelines, platform automation, or analytics outcomes."
            )
            for skill in emphasized[:3]
        ]
        if not bullet_suggestions:
            bullet_suggestions.append(
                "Add a role-specific bullet that links an existing project to the team's core stack."
            )

        return ResumeSuggestion(
            mode="rules",
            summary=summary,
            keywords_to_emphasize=emphasized,
            missing_resume_keywords=missing_keywords,
            bullet_suggestions=bullet_suggestions,
        )

    def _tailor_with_ollama(
        self,
        job: JobListing,
        matched_skills: list[str],
    ) -> ResumeSuggestion | None:
        prompt = (
            "You are tailoring a resume without inventing experience. "
            "Return strict JSON with keys summary, keywords_to_emphasize, "
            "missing_resume_keywords, bullet_suggestions.\n\n"
            f"Candidate skills: {', '.join(self.profile.skills)}\n"
            f"Current resume:\n{self.resume_text[:5000]}\n\n"
            f"Job title: {job.title}\n"
            f"Company: {job.company}\n"
            f"Job description:\n{job.description[:5000]}\n\n"
            f"Matched skills: {', '.join(matched_skills)}"
        )
        try:
            response = requests.post(
                f"{self.ai_config.ollama_base_url.rstrip('/')}/api/generate",
                json={
                    "model": self.ai_config.ollama_model,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                },
                timeout=60,
            )
            response.raise_for_status()
            payload = response.json()
            parsed = json.loads(payload.get("response", "{}"))
        except (requests.RequestException, json.JSONDecodeError, TypeError, ValueError):
            return None

        summary = str(parsed.get("summary") or "").strip()
        if not summary:
            return None

        return ResumeSuggestion(
            mode="ollama",
            summary=summary,
            keywords_to_emphasize=[str(item) for item in parsed.get("keywords_to_emphasize", [])],
            missing_resume_keywords=[str(item) for item in parsed.get("missing_resume_keywords", [])],
            bullet_suggestions=[str(item) for item in parsed.get("bullet_suggestions", [])],
        )

    def _rewrite_resume_with_ollama(
        self,
        job: JobListing,
        suggestion: ResumeSuggestion,
    ) -> str | None:
        prompt = (
            "Rewrite this markdown resume for the target role. "
            "Do not invent experience, companies, dates, certifications, or measurable outcomes. "
            "You may improve wording, summary, and skill emphasis. "
            "Return markdown only.\n\n"
            f"Target job title: {job.title}\n"
            f"Company: {job.company}\n"
            f"Keywords to emphasize: {', '.join(suggestion.keywords_to_emphasize)}\n"
            f"Tailoring summary: {suggestion.summary}\n\n"
            f"Current resume markdown:\n{self.resume_text[:12000]}"
        )
        try:
            response = requests.post(
                f"{self.ai_config.ollama_base_url.rstrip('/')}/api/generate",
                json={
                    "model": self.ai_config.ollama_model,
                    "prompt": prompt,
                    "stream": False,
                },
                timeout=90,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError, TypeError):
            return None

        rewritten = str(payload.get("response") or "").strip()
        if not rewritten:
            return None
        return rewritten if rewritten.endswith("\n") else f"{rewritten}\n"

    def _apply_rule_based_resume(
        self,
        job: JobListing,
        suggestion: ResumeSuggestion,
    ) -> str:
        resume_text = self.resume_text.strip()
        if not resume_text:
            resume_text = "# Candidate Resume\n"
        return self._upsert_section(
            resume_text,
            heading="## Professional Summary",
            body_lines=self._build_professional_summary(job, suggestion),
            insert_before="## Area of Expertise",
        )

    def _build_professional_summary(
        self,
        job: JobListing,
        suggestion: ResumeSuggestion,
    ) -> list[str]:
        keywords = suggestion.keywords_to_emphasize or self.profile.skills[:5]
        keywords_phrase = ", ".join(keywords[:5])
        return [
            (
                f"Software engineer with hands-on experience in {keywords_phrase}, delivering "
                "APIs, data workflows, automation, and cloud-backed production systems."
            ),
            (
                f"Resume targeted for {job.title} opportunities with emphasis on skills already "
                "backed by prior projects, tooling, and enterprise delivery work."
            ),
        ]

    def resume_fit_score(self, resume_text: str, keywords: list[str]) -> int:
        if not keywords:
            return 100
        matched = len(self._present_keywords(resume_text, keywords))
        return int(round((matched / len(keywords)) * 100))

    @staticmethod
    def _present_keywords(resume_text: str, keywords: list[str]) -> list[str]:
        lowered_resume = resume_text.lower()
        return [keyword for keyword in keywords if keyword.lower() in lowered_resume]

    def _with_tailoring_comment(
        self,
        resume_text: str,
        job: JobListing,
        suggestion: ResumeSuggestion,
    ) -> str:
        lines = [
            line
            for line in resume_text.splitlines()
            if not line.strip().startswith("<!-- Tailored for ")
        ]
        comment = (
            f"<!-- Tailored for {job.title} at {job.company}; "
            f"keywords: {', '.join(suggestion.keywords_to_emphasize)} -->"
        )
        normalized = [comment]
        if lines and lines[0].strip():
            normalized.append("")
        normalized.extend(lines)
        return "\n".join(normalized).rstrip() + "\n"

    def _ensure_expertise_keywords(self, resume_text: str, keywords: list[str]) -> str:
        heading = "## Area of Expertise"
        lines = resume_text.splitlines()
        start, end = self._find_section(lines, heading)
        existing_items: list[str] = []
        if start is not None and end is not None:
            existing_items = [
                line.rstrip()
                for line in lines[start + 1 : end]
                if line.strip()
            ]

        normalized_existing = {
            re.sub(r"^\s*-\s*", "", line).strip().lower()
            for line in existing_items
        }
        additions = [
            f"- {keyword}"
            for keyword in keywords
            if keyword.strip().lower() not in normalized_existing
        ]
        body_lines = existing_items + additions
        if not body_lines:
            body_lines = [f"- {keyword}" for keyword in keywords]

        return self._upsert_section(
            resume_text,
            heading=heading,
            body_lines=body_lines,
            insert_before="## Professional Experience",
        )

    @staticmethod
    def _find_section(lines: list[str], heading: str) -> tuple[int | None, int | None]:
        start = None
        for index, line in enumerate(lines):
            if line.strip() == heading:
                start = index
                break
        if start is None:
            return None, None
        end = len(lines)
        for index in range(start + 1, len(lines)):
            if lines[index].startswith("## "):
                end = index
                break
        return start, end

    @classmethod
    def _upsert_section(
        cls,
        resume_text: str,
        heading: str,
        body_lines: list[str],
        insert_before: str | None = None,
    ) -> str:
        lines = resume_text.splitlines()
        start, end = cls._find_section(lines, heading)
        block = [heading, ""] + body_lines + [""]

        if start is not None and end is not None:
            updated_lines = lines[:start] + block + lines[end:]
        else:
            insertion_index = len(lines)
            if insert_before is not None:
                for index, line in enumerate(lines):
                    if line.strip() == insert_before:
                        insertion_index = index
                        break
            prefix = lines[:insertion_index]
            suffix = lines[insertion_index:]
            if prefix and prefix[-1].strip():
                prefix.append("")
            updated_lines = prefix + block + suffix

        return "\n".join(updated_lines).rstrip() + "\n"
