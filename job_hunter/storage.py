from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from job_hunter.models import RankedJob


def load_seen_job_ids(state_path: Path) -> set[str]:
    if not state_path.exists():
        return set()
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    return set(payload.get("seen_job_ids", []))


def load_resume_application_state(state_path: Path) -> dict[str, Any]:
    if not state_path.exists():
        return {}
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return {}
    return payload


def write_resume_application_state(
    state: dict[str, Any],
    database_dir: Path,
    dashboard_dir: Path,
) -> None:
    database_dir.mkdir(parents=True, exist_ok=True)
    dashboard_dir.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(state, indent=2)
    (database_dir / "resume_application_state.json").write_text(
        serialized,
        encoding="utf-8",
    )
    (dashboard_dir / "resume_application_state.json").write_text(
        serialized,
        encoding="utf-8",
    )


def write_outputs(
    ranked_jobs: list[RankedJob],
    summary: dict[str, Any],
    seen_job_ids: set[str],
    database_dir: Path,
    dashboard_dir: Path,
    dashboard_api_url: str | None = None,
) -> None:
    database_dir.mkdir(parents=True, exist_ok=True)
    dashboard_dir.mkdir(parents=True, exist_ok=True)

    jobs_payload = [job.to_dict() for job in ranked_jobs]
    suggestions_payload = [
        {
            "job_id": job.job.fingerprint(),
            "title": job.job.title,
            "company": job.job.company,
            "resume_suggestion": (
                job.resume_suggestion.to_dict() if job.resume_suggestion is not None else None
            ),
        }
        for job in ranked_jobs
        if job.resume_suggestion is not None
    ]

    (database_dir / "jobs.json").write_text(
        json.dumps(jobs_payload, indent=2),
        encoding="utf-8",
    )
    (database_dir / "summary.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )
    (database_dir / "resume_suggestions.json").write_text(
        json.dumps(suggestions_payload, indent=2),
        encoding="utf-8",
    )
    (database_dir / "state.json").write_text(
        json.dumps({"seen_job_ids": sorted(seen_job_ids)}, indent=2),
        encoding="utf-8",
    )

    (dashboard_dir / "jobs.json").write_text(
        json.dumps(jobs_payload, indent=2),
        encoding="utf-8",
    )
    (dashboard_dir / "summary.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )
    (dashboard_dir / "resume_suggestions.json").write_text(
        json.dumps(suggestions_payload, indent=2),
        encoding="utf-8",
    )

    application_state_path = database_dir / "resume_application_state.json"
    application_state = load_resume_application_state(application_state_path)
    write_resume_application_state(
        application_state,
        database_dir=database_dir,
        dashboard_dir=dashboard_dir,
    )

    (dashboard_dir / "api_config.json").write_text(
        json.dumps({"api_url": dashboard_api_url or ""}, indent=2),
        encoding="utf-8",
    )
