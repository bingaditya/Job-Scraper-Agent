from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from supabase import Client, create_client

from job_hunter.config import StorageConfig
from job_hunter.models import ResumeSuggestion
from job_hunter.resume_profile import ExtractedProfile

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

_TABLE = "resume_versions"
_PROFILE_TABLE = "candidate_profiles"


class ResumeNotFoundError(Exception):
    pass


@dataclass(slots=True)
class ResumeStore:
    client: Client
    bucket: str

    @classmethod
    def from_config(cls, storage: StorageConfig) -> "ResumeStore":
        if not storage.supabase_url or not storage.supabase_secret_key:
            raise RuntimeError(
                "Supabase is not configured: set SUPABASE_URL and SUPABASE_SECRET_KEY."
            )
        client = create_client(storage.supabase_url, storage.supabase_secret_key)
        return cls(client=client, bucket=storage.resume_bucket)

    def list_versions(self, user_id: str) -> list[dict[str, Any]]:
        response = (
            self.client.table(_TABLE)
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )
        return response.data or []

    def get_version(self, user_id: str, version_id: str) -> dict[str, Any]:
        response = (
            self.client.table(_TABLE)
            .select("*")
            .eq("user_id", user_id)
            .eq("id", version_id)
            .limit(1)
            .execute()
        )
        rows = response.data or []
        if not rows:
            raise ResumeNotFoundError(f"Resume version {version_id} was not found.")
        return rows[0]

    def get_current_version(self, user_id: str) -> dict[str, Any] | None:
        response = (
            self.client.table(_TABLE)
            .select("*")
            .eq("user_id", user_id)
            .eq("is_current", True)
            .limit(1)
            .execute()
        )
        rows = response.data or []
        return rows[0] if rows else None

    def download_bytes(self, user_id: str, version_id: str) -> tuple[bytes, dict[str, Any]]:
        version = self.get_version(user_id, version_id)
        data = self.client.storage.from_(self.bucket).download(version["storage_path"])
        return data, version

    def create_upload_version(
        self,
        user_id: str,
        file_bytes: bytes,
        original_filename: str,
    ) -> dict[str, Any]:
        return self._insert_new_current_version(
            user_id=user_id,
            file_bytes=file_bytes,
            original_filename=original_filename,
            source="upload",
            parent_version_id=None,
            job_title=None,
            job_description=None,
            job_id=None,
            tailoring_mode=None,
            suggestion=None,
        )

    def create_tailored_version(
        self,
        user_id: str,
        source_version: dict[str, Any],
        file_bytes: bytes,
        job_title: str,
        job_description: str,
        job_id: str | None,
        tailoring_mode: str,
        suggestion: ResumeSuggestion,
        fit_score: int,
    ) -> dict[str, Any]:
        return self._insert_new_current_version(
            user_id=user_id,
            file_bytes=file_bytes,
            original_filename=source_version["original_filename"],
            source="ai_tailored",
            parent_version_id=source_version["id"],
            job_title=job_title,
            job_description=job_description,
            job_id=job_id,
            tailoring_mode=tailoring_mode,
            suggestion=suggestion,
            fit_score=fit_score,
        )

    def _insert_new_current_version(
        self,
        user_id: str,
        file_bytes: bytes,
        original_filename: str,
        source: str,
        parent_version_id: str | None,
        job_title: str | None,
        job_description: str | None,
        job_id: str | None,
        tailoring_mode: str | None,
        suggestion: ResumeSuggestion | None,
        fit_score: int | None = None,
    ) -> dict[str, Any]:
        existing = self.list_versions(user_id)
        next_version_number = max((row["version_number"] for row in existing), default=0) + 1
        current_row = next((row for row in existing if row["is_current"]), None)

        storage_path = f"{user_id}/{uuid.uuid4().hex}.docx"
        self.client.storage.from_(self.bucket).upload(
            storage_path,
            file_bytes,
            {"content-type": DOCX_MIME},
        )

        if current_row is not None:
            self.client.table(_TABLE).update({"is_current": False}).eq(
                "id", current_row["id"]
            ).execute()

        payload: dict[str, Any] = {
            "user_id": user_id,
            "version_number": next_version_number,
            "is_current": True,
            "source": source,
            "parent_version_id": parent_version_id,
            "storage_path": storage_path,
            "original_filename": original_filename,
            "file_size_bytes": len(file_bytes),
            "mime_type": DOCX_MIME,
            "job_title": job_title,
            "job_description": job_description,
            "job_id": job_id,
            "tailoring_mode": tailoring_mode,
        }
        if suggestion is not None:
            payload["tailoring_summary"] = suggestion.summary
            payload["keywords_emphasized"] = suggestion.keywords_to_emphasize
            payload["missing_keywords"] = suggestion.missing_resume_keywords
            payload["fit_score"] = fit_score

        response = self.client.table(_TABLE).insert(payload).execute()
        return response.data[0]

    def get_candidate_profile(self, user_id: str) -> dict[str, Any] | None:
        response = (
            self.client.table(_PROFILE_TABLE)
            .select("*")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        rows = response.data or []
        return rows[0] if rows else None

    def upsert_candidate_profile(
        self,
        user_id: str,
        profile: ExtractedProfile,
        source_version_id: str,
    ) -> dict[str, Any]:
        payload = {
            "user_id": user_id,
            "skills": profile.skills,
            "preferred_titles": profile.preferred_titles,
            "experience_years": profile.experience_years,
            "summary": profile.summary,
            "source_version_id": source_version_id,
            "extraction_mode": profile.mode,
        }
        response = (
            self.client.table(_PROFILE_TABLE).upsert(payload, on_conflict="user_id").execute()
        )
        return response.data[0]
