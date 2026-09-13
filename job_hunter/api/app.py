from __future__ import annotations

import os
from pathlib import Path

import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from job_hunter.api.routes_jobs import router as jobs_router
from job_hunter.api.routes_resume import router as resume_router
from job_hunter.config import load_config
from job_hunter.resume_store import ResumeStore

_SENTRY_DSN = os.environ.get("SENTRY_DSN")
if _SENTRY_DSN:
    sentry_sdk.init(dsn=_SENTRY_DSN, traces_sample_rate=0.1)


def create_app() -> FastAPI:
    app = FastAPI(title="AI Job Hunter — Resume API")

    profile_path = Path(os.environ.get("PROFILE_PATH", "config/profile.json"))
    config = load_config(profile_path)
    app.state.config = config
    app.state.resume_store = ResumeStore.from_config(config.storage)
    app.state.raw_jobs_path = Path(os.environ.get("RAW_JOBS_PATH", "database/raw_jobs.json"))

    allowed_origins = [
        origin.strip()
        for origin in os.environ.get("ALLOWED_ORIGINS", "*").split(",")
        if origin.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(resume_router)
    app.include_router(jobs_router)
    return app


app = create_app()
