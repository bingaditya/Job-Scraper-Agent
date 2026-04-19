from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from job_hunter.config import load_config
from job_hunter.models import JobListing, ResumeSuggestion
from job_hunter.resume_optimizer import ResumeOptimizer
from job_hunter.storage import (
    load_resume_application_state,
    write_resume_application_state,
)


class DashboardService:
    def __init__(
        self,
        profile_path: Path,
        database_dir: Path,
        dashboard_dir: Path,
        workspace_dir: Path | None = None,
    ) -> None:
        self.workspace_dir = workspace_dir or Path(__file__).resolve().parents[1]
        self.profile_path = self._resolve_path(profile_path)
        self.database_dir = self._resolve_path(database_dir)
        self.dashboard_dir = self._resolve_path(dashboard_dir)

    def health(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "profile_path": str(self.profile_path),
            "database_dir": str(self.database_dir),
            "dashboard_dir": str(self.dashboard_dir),
        }

    def get_resume_content(self) -> tuple[str, str]:
        config = load_config(self.profile_path)
        resume_path = self._resume_path(config.candidate.resume_path)
        if not resume_path.exists():
            raise FileNotFoundError("Resume file not found.")
        return resume_path.read_text(encoding="utf-8"), resume_path.name

    def get_resume_metadata(self) -> dict[str, Any]:
        config = load_config(self.profile_path)
        resume_path = self._resume_path(config.candidate.resume_path)
        return {
            "resume_path": str(resume_path),
            "exists": resume_path.exists(),
            "updated_at": (
                datetime.fromtimestamp(
                    resume_path.stat().st_mtime,
                    tz=UTC,
                ).isoformat()
                if resume_path.exists()
                else None
            ),
        }

    def tailor_resume(self, job_id: str) -> dict[str, Any]:
        ranked_job_payload = self._load_ranked_job(job_id)
        config = load_config(self.profile_path)
        resume_path = self._resume_path(config.candidate.resume_path)
        resume_path.parent.mkdir(parents=True, exist_ok=True)

        if resume_path.exists():
            current_resume = resume_path.read_text(encoding="utf-8")
        else:
            current_resume = "# Candidate Resume\n"

        optimizer = ResumeOptimizer(
            profile=config.candidate,
            ai_config=config.ai,
            resume_text=current_resume,
        )
        job = JobListing.from_dict(ranked_job_payload["job"])
        matched_skills = [str(item) for item in ranked_job_payload.get("matched_skills", [])]
        suggestion = self._load_resume_suggestion(ranked_job_payload, job_id)
        tailored_resume, resume_fit_score, applied_keywords = optimizer.apply_tailoring(
            job=job,
            matched_skills=matched_skills,
            suggestion=suggestion,
        )

        backup_path = self._backup_resume(resume_path, current_resume, job_id)
        resume_path.write_text(tailored_resume, encoding="utf-8")

        application_state = load_resume_application_state(
            self.database_dir / "resume_application_state.json"
        )
        applied_at = datetime.now(tz=UTC).isoformat()
        application_state[job_id] = {
            "job_id": job_id,
            "job_title": job.title,
            "company": job.company,
            "resume_fit_score": resume_fit_score,
            "applied_keywords": applied_keywords,
            "resume_path": str(resume_path),
            "backup_path": str(backup_path),
            "applied_at": applied_at,
        }
        write_resume_application_state(
            application_state,
            database_dir=self.database_dir,
            dashboard_dir=self.dashboard_dir,
        )

        return application_state[job_id]

    def _load_ranked_job(self, job_id: str) -> dict[str, Any]:
        jobs_path = self.database_dir / "jobs.json"
        if not jobs_path.exists():
            raise FileNotFoundError("database/jobs.json not found. Run the agent first.")

        ranked_jobs = json.loads(jobs_path.read_text(encoding="utf-8"))
        for payload in ranked_jobs:
            job_payload = payload.get("job", {})
            if str(job_payload.get("fingerprint", "")) == job_id:
                return payload
        raise KeyError(f"Job id {job_id} was not found in database/jobs.json.")

    def _load_resume_suggestion(
        self,
        ranked_job_payload: dict[str, Any],
        job_id: str,
    ) -> ResumeSuggestion | None:
        suggestion_payload = ranked_job_payload.get("resume_suggestion")
        if isinstance(suggestion_payload, dict):
            return ResumeSuggestion.from_dict(suggestion_payload)

        suggestions_path = self.database_dir / "resume_suggestions.json"
        if suggestions_path.exists():
            suggestions = json.loads(suggestions_path.read_text(encoding="utf-8"))
            for payload in suggestions:
                if str(payload.get("job_id", "")) == job_id and isinstance(
                    payload.get("resume_suggestion"),
                    dict,
                ):
                    return ResumeSuggestion.from_dict(payload["resume_suggestion"])
        return None

    def _backup_resume(
        self,
        resume_path: Path,
        current_resume: str,
        job_id: str,
    ) -> Path:
        backup_dir = resume_path.parent / "resume.backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(tz=UTC).strftime("%Y%m%d-%H%M%S")
        backup_path = backup_dir / f"{resume_path.stem}-{timestamp}-{job_id[:8]}{resume_path.suffix}"
        backup_path.write_text(current_resume, encoding="utf-8")
        return backup_path

    def _resume_path(self, configured_path: str | None) -> Path:
        return self._resolve_path(Path(configured_path or "assets/resume.md"))

    def _resolve_path(self, path: str | Path) -> Path:
        candidate = Path(path)
        if candidate.is_absolute():
            return candidate
        return (self.workspace_dir / candidate).resolve()

