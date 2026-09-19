from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, Query, Request

from job_hunter.api.schemas import JobMatchesResponse, JobMatchOut
from job_hunter.auth import AuthUser, get_current_user
from job_hunter.config import CandidateProfile, GroqConfig, SearchConfig
from job_hunter.job_fit_ai import FitCandidate, rerank_by_fit
from job_hunter.models import JobListing
from job_hunter.ranking import job_matches_location, score_job
from job_hunter.resume_store import ResumeStore
from job_hunter.sources import ArbeitnowSource, RemoteOKSource
from job_hunter.sources.base import JobSource

router = APIRouter(prefix="/api")

DEFAULT_MIN_SCORE = 20
DEFAULT_TOP_N = 25

# These two are real JSON APIs (fast, no rate-limit/ban risk), so it's safe to
# call them live on every request with the requesting user's own resume terms.
# The HTML-scraped sources (LinkedIn/BuiltIn/Himalayas) stay on the shared,
# periodic crawl only - see raw_jobs_path.
LIVE_QUERY_JOB_LIMIT = 15

# How many of the top keyword-scored matches get sent to the AI fit reranker.
# Bounds prompt size/cost to one batched call regardless of how many jobs matched.
AI_RERANK_CANDIDATE_LIMIT = 30


def get_resume_store(request: Request) -> ResumeStore:
    return request.app.state.resume_store


def get_groq_config(request: Request) -> GroqConfig:
    return request.app.state.config.groq


def get_raw_jobs_path(request: Request) -> Path:
    return getattr(request.app.state, "raw_jobs_path", Path("database/raw_jobs.json"))


def get_live_sources(request: Request) -> list[JobSource]:
    configured = getattr(request.app.state, "live_job_sources", None)
    if configured is not None:
        return configured
    return [
        ArbeitnowSource(source_job_limit=LIVE_QUERY_JOB_LIMIT),
        RemoteOKSource(source_job_limit=LIVE_QUERY_JOB_LIMIT),
    ]


def _load_raw_jobs(path: Path) -> list[JobListing]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [JobListing.from_dict(item) for item in payload]


def _fetch_live_jobs(
    sources: list[JobSource],
    queries: list[str],
    keywords: list[str],
) -> list[JobListing]:
    jobs: list[JobListing] = []
    for source in sources:
        try:
            jobs.extend(
                source.fetch_jobs(queries=queries, keywords=keywords, locations=[])
            )
        except Exception:
            # A slow/unavailable live source must never break the response -
            # the shared, periodically-crawled pool is always the fallback.
            continue
    return jobs


def _dedupe_jobs(jobs: list[JobListing]) -> list[JobListing]:
    deduped: list[JobListing] = []
    seen: set[str] = set()
    for job in jobs:
        key = job.url.strip().lower() or job.fingerprint()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(job)
    return deduped


@router.get("/jobs", response_model=JobMatchesResponse)
def list_job_matches(
    current_user: AuthUser = Depends(get_current_user),
    store: ResumeStore = Depends(get_resume_store),
    raw_jobs_path: Path = Depends(get_raw_jobs_path),
    live_sources: list[JobSource] = Depends(get_live_sources),
    groq_config: GroqConfig = Depends(get_groq_config),
    min_score: int = Query(DEFAULT_MIN_SCORE, ge=0, le=100),
    top_n: int = Query(DEFAULT_TOP_N, ge=1, le=100),
) -> JobMatchesResponse:
    profile_row = store.get_candidate_profile(current_user.id)
    if not profile_row or not profile_row.get("skills"):
        return JobMatchesResponse(
            jobs=[],
            message="Upload a resume first to see personalized job matches.",
        )

    skills = profile_row.get("skills") or []
    preferred_titles = profile_row.get("preferred_titles") or []
    summary = profile_row.get("summary") or ""

    candidate_profile = CandidateProfile(
        name="",
        experience_years=profile_row.get("experience_years") or 0,
        skills=skills,
        preferred_titles=preferred_titles,
        preferred_locations=[],
        remote_first=True,
    )
    search_config = SearchConfig(
        keywords=preferred_titles,
        min_score=min_score,
        top_n=top_n,
    )

    live_jobs = _fetch_live_jobs(
        live_sources,
        queries=preferred_titles,
        keywords=JobSource.dedupe_terms([*preferred_titles, *skills]),
    )
    all_jobs = _dedupe_jobs([*live_jobs, *_load_raw_jobs(raw_jobs_path)])

    matches: list[JobMatchOut] = []
    for job in all_jobs:
        if not job_matches_location(job=job, profile=candidate_profile, search=search_config):
            continue
        score, reasons, matched_skills = score_job(
            job=job, profile=candidate_profile, search=search_config
        )
        if score < search_config.min_score:
            continue
        matches.append(
            JobMatchOut(
                job_id=job.fingerprint(),
                title=job.title,
                company=job.company,
                location=job.location,
                url=job.url,
                source=job.source,
                remote=job.remote,
                description=job.description,
                score=score,
                reasons=reasons,
                matched_skills=matched_skills,
            )
        )

    matches = _apply_ai_fit_rerank(
        matches, summary=summary, preferred_titles=preferred_titles, skills=skills,
        groq_config=groq_config, min_score=search_config.min_score,
    )

    matches.sort(key=lambda match: -match.score)
    return JobMatchesResponse(jobs=matches[:search_config.top_n], message=None)


def _apply_ai_fit_rerank(
    matches: list[JobMatchOut],
    summary: str,
    preferred_titles: list[str],
    skills: list[str],
    groq_config: GroqConfig,
    min_score: int,
) -> list[JobMatchOut]:
    """Blend an AI occupation-fit judgment into keyword scores for the top candidates.

    Keyword overlap alone can't tell "uses this tool" from "does this job" (e.g. a tester's
    resume mentioning a language shouldn't rank a Developer role for that language highly).
    Falls back to the unmodified keyword-based matches on any AI failure.
    """
    if not matches:
        return matches

    top_candidates = sorted(matches, key=lambda match: -match.score)[:AI_RERANK_CANDIDATE_LIMIT]
    fit_candidates = [
        FitCandidate(
            job_id=match.job_id,
            title=match.title,
            company=match.company,
            description=match.description,
        )
        for match in top_candidates
    ]
    fit_scores = rerank_by_fit(summary, preferred_titles, skills, fit_candidates, groq_config)
    if not fit_scores:
        return matches

    reranked_ids = {match.job_id for match in top_candidates}
    blended: list[JobMatchOut] = []
    for match in matches:
        if match.job_id in reranked_ids and match.job_id in fit_scores:
            ai_score = fit_scores[match.job_id]
            final_score = round(0.35 * match.score + 0.65 * ai_score)
            match = match.model_copy(
                update={
                    "score": final_score,
                    "reasons": [*match.reasons, f"AI fit score: {ai_score}/100"],
                }
            )
        if match.score >= min_score:
            blended.append(match)
    return blended
