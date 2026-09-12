from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ConfigOut(BaseModel):
    supabase_url: str
    supabase_publishable_key: str


class ResumeVersionOut(BaseModel):
    id: str
    version_number: int
    is_current: bool
    source: str
    original_filename: str
    job_title: str | None = None
    tailoring_mode: str | None = None
    fit_score: int | None = None
    created_at: str

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "ResumeVersionOut":
        return cls(
            id=str(row["id"]),
            version_number=row["version_number"],
            is_current=row["is_current"],
            source=row["source"],
            original_filename=row["original_filename"],
            job_title=row.get("job_title"),
            tailoring_mode=row.get("tailoring_mode"),
            fit_score=row.get("fit_score"),
            created_at=str(row["created_at"]),
        )


class TailorRequest(BaseModel):
    source_version_id: str | None = None
    job_title: str
    job_description: str
    job_id: str | None = None
    skills: list[str] = []


class TailorResponse(BaseModel):
    changed: bool
    version: ResumeVersionOut | None = None
    suggestion: dict[str, Any] | None = None


class JobMatchOut(BaseModel):
    job_id: str
    title: str
    company: str
    location: str
    url: str
    source: str
    remote: bool
    description: str
    score: int
    reasons: list[str]
    matched_skills: list[str]


class JobMatchesResponse(BaseModel):
    jobs: list[JobMatchOut]
    message: str | None = None
