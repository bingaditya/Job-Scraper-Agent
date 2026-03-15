from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha1
from typing import Any


@dataclass(slots=True)
class JobListing:
    source: str
    source_id: str
    title: str
    company: str
    location: str
    url: str
    description: str
    tags: list[str] = field(default_factory=list)
    published_at: str | None = None
    remote: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def fingerprint(self) -> str:
        identity = "|".join(
            [
                self.source,
                self.source_id,
                self.company.strip().lower(),
                self.title.strip().lower(),
                self.url.strip().lower(),
            ]
        )
        return sha1(identity.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["fingerprint"] = self.fingerprint()
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "JobListing":
        return cls(
            source=str(payload.get("source", "")),
            source_id=str(payload.get("source_id", "")),
            title=str(payload.get("title", "")),
            company=str(payload.get("company", "")),
            location=str(payload.get("location", "")),
            url=str(payload.get("url", "")),
            description=str(payload.get("description", "")),
            tags=[str(item) for item in payload.get("tags", [])],
            published_at=(
                str(payload["published_at"])
                if payload.get("published_at") not in {None, ""}
                else None
            ),
            remote=bool(payload.get("remote", False)),
            metadata=dict(payload.get("metadata", {})),
        )


@dataclass(slots=True)
class ResumeSuggestion:
    mode: str
    summary: str
    keywords_to_emphasize: list[str] = field(default_factory=list)
    missing_resume_keywords: list[str] = field(default_factory=list)
    bullet_suggestions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ResumeSuggestion":
        return cls(
            mode=str(payload.get("mode", "rules")),
            summary=str(payload.get("summary", "")),
            keywords_to_emphasize=[str(item) for item in payload.get("keywords_to_emphasize", [])],
            missing_resume_keywords=[
                str(item) for item in payload.get("missing_resume_keywords", [])
            ],
            bullet_suggestions=[str(item) for item in payload.get("bullet_suggestions", [])],
        )


@dataclass(slots=True)
class RankedJob:
    job: JobListing
    score: int
    reasons: list[str]
    matched_skills: list[str] = field(default_factory=list)
    resume_suggestion: ResumeSuggestion | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "score": self.score,
            "reasons": self.reasons,
            "matched_skills": self.matched_skills,
            "job": self.job.to_dict(),
        }
        if self.resume_suggestion is not None:
            payload["resume_suggestion"] = self.resume_suggestion.to_dict()
        return payload
