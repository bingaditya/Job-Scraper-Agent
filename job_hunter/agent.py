from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from job_hunter.config import AppConfig
from job_hunter.models import JobListing, RankedJob
from job_hunter.notifications import TelegramNotifier
from job_hunter.ranking import job_matches_location, score_job
from job_hunter.resume_optimizer import ResumeOptimizer
from job_hunter.sources import build_sources
from job_hunter.storage import load_seen_job_ids, write_outputs


class JobHunterAgent:
    def __init__(
        self,
        config: AppConfig,
        database_dir: Path,
        dashboard_dir: Path,
    ) -> None:
        self.config = config
        self.database_dir = database_dir
        self.dashboard_dir = dashboard_dir

    def run(self) -> dict[str, Any]:
        raw_jobs: list[JobListing] = []
        source_stats: list[dict[str, Any]] = []

        for source in build_sources(self.config.sources):
            try:
                jobs = source.fetch_jobs(
                    queries=self.config.search.queries,
                    keywords=self.config.search.keywords,
                    locations=self.config.candidate.preferred_locations,
                )
                raw_jobs.extend(jobs)
                source_stats.append(
                    {
                        "source": source.source_name,
                        "status": "ok",
                        "jobs_fetched": len(jobs),
                    }
                )
            except Exception as exc:
                source_stats.append(
                    {
                        "source": source.source_name,
                        "status": "error",
                        "error": str(exc),
                    }
                )

        if not any(item["status"] == "ok" for item in source_stats):
            raise RuntimeError("All configured job sources failed; no output was written.")

        deduped_jobs = self._deduplicate(raw_jobs)
        ranked_jobs = self._rank(deduped_jobs)
        notifier = TelegramNotifier(self.config.notifications)

        seen_job_ids = load_seen_job_ids(self.database_dir / "state.json")
        new_ranked_jobs = [
            job for job in ranked_jobs if job.job.fingerprint() not in seen_job_ids
        ]
        notifications_sent = notifier.notify(new_ranked_jobs)
        all_seen_job_ids = seen_job_ids | {job.job.fingerprint() for job in ranked_jobs}

        summary = {
            "generated_at": datetime.now(tz=UTC).isoformat(),
            "candidate": self.config.candidate.name,
            "raw_jobs": len(raw_jobs),
            "deduplicated_jobs": len(deduped_jobs),
            "shortlisted_jobs": len(ranked_jobs),
            "new_jobs": len(new_ranked_jobs),
            "notifications_sent": notifications_sent,
            "score_threshold": self.config.search.min_score,
            "top_sources": Counter(job.job.source for job in ranked_jobs).most_common(),
            "source_stats": source_stats,
        }
        write_outputs(
            ranked_jobs=ranked_jobs,
            summary=summary,
            seen_job_ids=all_seen_job_ids,
            database_dir=self.database_dir,
            dashboard_dir=self.dashboard_dir,
        )
        return summary

    def _rank(self, jobs: list[JobListing]) -> list[RankedJob]:
        optimizer = ResumeOptimizer.from_profile(
            profile=self.config.candidate,
            ai_config=self.config.ai,
        )
        ranked: list[RankedJob] = []
        for job in jobs:
            if not job_matches_location(
                job=job,
                profile=self.config.candidate,
                search=self.config.search,
            ):
                continue
            score, reasons, matched_skills = score_job(
                job=job,
                profile=self.config.candidate,
                search=self.config.search,
            )
            if score < self.config.search.min_score:
                continue

            ranked_job = RankedJob(
                job=job,
                score=score,
                reasons=reasons,
                matched_skills=matched_skills,
            )
            ranked.append(ranked_job)

        ranked.sort(
            key=lambda item: (
                -item.score,
                -self._published_sort_key(item.job.published_at),
                item.job.company.lower(),
                item.job.title.lower(),
            )
        )
        ranked = ranked[: self.config.search.top_n]
        for ranked_job in ranked[: self.config.ai.max_tailored_jobs]:
            ranked_job.resume_suggestion = optimizer.tailor(
                ranked_job.job,
                ranked_job.matched_skills,
            )
        return ranked

    @staticmethod
    def _deduplicate(jobs: list[JobListing]) -> list[JobListing]:
        deduped: list[JobListing] = []
        seen: set[str] = set()
        for job in jobs:
            key = job.url.strip().lower() or job.fingerprint()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(job)
        return deduped

    @staticmethod
    def _published_sort_key(value: str | None) -> float:
        if not value:
            return 0.0
        normalized = value.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(normalized).timestamp()
        except ValueError:
            return 0.0
