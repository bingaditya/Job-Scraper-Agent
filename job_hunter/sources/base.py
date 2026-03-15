from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime

import requests
from bs4 import BeautifulSoup

from job_hunter.models import JobListing


class JobSource(ABC):
    source_name: str

    def __init__(self, source_job_limit: int = 20) -> None:
        self.source_job_limit = source_job_limit
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                )
            }
        )

    @abstractmethod
    def fetch_jobs(
        self,
        queries: list[str],
        keywords: list[str],
        locations: list[str],
    ) -> list[JobListing]:
        raise NotImplementedError

    @staticmethod
    def strip_html(value: str | None) -> str:
        if not value:
            return ""
        return BeautifulSoup(value, "html.parser").get_text(" ", strip=True)

    @staticmethod
    def matches_keywords(keywords: list[str], *fields: str) -> bool:
        if not keywords:
            return True
        haystack = " ".join(field for field in fields if field).lower()
        return any(keyword.lower() in haystack for keyword in keywords)

    @staticmethod
    def epoch_to_iso(value: int | float | None) -> str | None:
        if value is None:
            return None
        return datetime.fromtimestamp(float(value), tz=UTC).isoformat()

    @classmethod
    def normalize_timestamp(cls, value: object) -> str | None:
        if value is None or value == "":
            return None
        if isinstance(value, (int, float)):
            return cls.epoch_to_iso(value)
        return str(value)

    @staticmethod
    def dedupe_terms(values: list[str], limit: int | None = None) -> list[str]:
        results: list[str] = []
        seen: set[str] = set()
        for value in values:
            normalized = value.strip()
            if not normalized:
                continue
            key = normalized.lower()
            if key in seen:
                continue
            seen.add(key)
            results.append(normalized)
            if limit is not None and len(results) >= limit:
                break
        return results

    @classmethod
    def build_search_queries(cls, queries: list[str], keywords: list[str]) -> list[str]:
        search_queries = cls.dedupe_terms(queries or keywords, limit=3)
        return search_queries or ["software engineer"]

    @classmethod
    def build_search_locations(cls, locations: list[str]) -> list[str]:
        cleaned = cls.dedupe_terms(
            [
                location
                for location in locations
                if location.strip().lower() not in {"hybrid", "onsite"}
            ],
            limit=2,
        )
        return cleaned or ["Remote"]

    @staticmethod
    def absolute_url(base: str, value: str | None) -> str:
        if not value:
            return ""
        if value.startswith("http://") or value.startswith("https://"):
            return value
        return f"{base.rstrip('/')}/{value.lstrip('/')}"
