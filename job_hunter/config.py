from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class CandidateProfile:
    name: str
    experience_years: int
    skills: list[str]
    preferred_titles: list[str]
    preferred_locations: list[str]
    remote_first: bool
    resume_path: str | None = None


@dataclass(slots=True)
class SearchConfig:
    keywords: list[str]
    queries: list[str] = field(default_factory=list)
    strict_location_match: bool = False
    min_score: int = 45
    top_n: int = 25


@dataclass(slots=True)
class SourceConfig:
    enabled: list[str] = field(
        default_factory=lambda: [
            "arbeitnow",
            "remoteok",
            "linkedin",
            "builtin",
            "himalayas",
        ]
    )
    arbeitnow_pages: int = 2
    linkedin_pages: int = 1
    builtin_pages: int = 1
    himalayas_pages: int = 1
    source_job_limit: int = 20


@dataclass(slots=True)
class NotificationConfig:
    telegram_enabled: bool = False
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None


@dataclass(slots=True)
class AIConfig:
    ollama_model: str | None = None
    ollama_base_url: str = "http://127.0.0.1:11434"
    max_tailored_jobs: int = 5


@dataclass(slots=True)
class AppConfig:
    candidate: CandidateProfile
    search: SearchConfig
    sources: SourceConfig
    notifications: NotificationConfig
    ai: AIConfig


def load_config(path: Path) -> AppConfig:
    with path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)

    notifications = raw.get("notifications", {})
    ai = raw.get("ai", {})

    bot_token = os.getenv("TELEGRAM_BOT_TOKEN") or notifications.get("telegram_bot_token")
    chat_id = os.getenv("TELEGRAM_CHAT_ID") or notifications.get("telegram_chat_id")
    ollama_model = os.getenv("OLLAMA_MODEL") or ai.get("ollama_model")
    ollama_base_url = os.getenv("OLLAMA_BASE_URL") or ai.get(
        "ollama_base_url",
        "http://127.0.0.1:11434",
    )

    return AppConfig(
        candidate=CandidateProfile(**raw["candidate"]),
        search=SearchConfig(**raw["search"]),
        sources=SourceConfig(**raw.get("sources", {})),
        notifications=NotificationConfig(
            telegram_enabled=notifications.get("telegram_enabled", False),
            telegram_bot_token=bot_token,
            telegram_chat_id=chat_id,
        ),
        ai=AIConfig(
            ollama_model=ollama_model,
            ollama_base_url=ollama_base_url,
            max_tailored_jobs=ai.get("max_tailored_jobs", 5),
        ),
    )
