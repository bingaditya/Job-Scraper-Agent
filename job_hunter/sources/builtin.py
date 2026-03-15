from __future__ import annotations

import json

from bs4 import BeautifulSoup

from job_hunter.models import JobListing

from .base import JobSource


class BuiltInSource(JobSource):
    source_name = "builtin"
    search_url = "https://builtin.com/jobs"
    base_url = "https://builtin.com"

    def __init__(self, pages: int = 1, source_job_limit: int = 20) -> None:
        super().__init__(source_job_limit=source_job_limit)
        self.pages = pages

    def fetch_jobs(
        self,
        queries: list[str],
        keywords: list[str],
        locations: list[str],
    ) -> list[JobListing]:
        jobs: list[JobListing] = []
        seen_urls: set[str] = set()
        search_queries = self.build_search_queries(queries, keywords)

        for query in search_queries:
            for page_number in range(1, self.pages + 1):
                response = self.session.get(
                    self.search_url,
                    params={
                        "search": query,
                        "page": page_number,
                    },
                    timeout=30,
                )
                response.raise_for_status()
                soup = BeautifulSoup(response.text, "html.parser")
                for card in soup.select('[data-id="job-card"]'):
                    title_link = card.select_one('a[data-id="job-card-title"]')
                    company_node = card.select_one('a[data-id="company-title"]')
                    if title_link is None or company_node is None:
                        continue

                    url = self.absolute_url(self.base_url, title_link.get("href"))
                    if not url or url in seen_urls:
                        continue
                    seen_urls.add(url)

                    title = title_link.get_text(" ", strip=True)
                    company = company_node.get_text(" ", strip=True)
                    card_text = card.get_text(" ", strip=True)
                    location = self._extract_location(card)
                    description = self._fetch_description(url) or card_text
                    tags = self._extract_tags(card)
                    if not self.matches_keywords(
                        keywords,
                        title,
                        company,
                        location,
                        description,
                        " ".join(tags),
                    ):
                        continue

                    jobs.append(
                        JobListing(
                            source=self.source_name,
                            source_id=card.get("id", url.rsplit("/", 1)[-1]),
                            title=title,
                            company=company,
                            location=location,
                            url=url,
                            description=description,
                            tags=tags,
                            published_at=self._extract_published(card),
                            remote="remote" in location.lower(),
                        )
                    )
                    if len(jobs) >= self.source_job_limit:
                        return jobs
        return jobs

    def _fetch_description(self, url: str) -> str:
        response = self.session.get(url, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        for script in soup.select('script[type="application/ld+json"]'):
            try:
                payload = json.loads(script.get_text())
            except json.JSONDecodeError:
                continue
            graph = payload.get("@graph") if isinstance(payload, dict) else None
            entries = graph if isinstance(graph, list) else [payload]
            for entry in entries:
                if isinstance(entry, dict) and entry.get("@type") == "JobPosting":
                    return self.strip_html(entry.get("description"))
        return ""

    @staticmethod
    def _extract_location(card: BeautifulSoup) -> str:
        locations = []
        for node in card.select("svg[title='Location icon'], i.fa-location-dot"):
            parent = node.parent
            if parent is not None:
                locations.append(parent.get_text(" ", strip=True))
        if locations:
            return locations[0]
        text = card.get_text(" ", strip=True)
        for candidate in ["Remote", "Hybrid", "Hyderabad", "Bengaluru", "Pune", "India"]:
            if candidate.lower() in text.lower():
                return candidate
        return "Unknown"

    @staticmethod
    def _extract_tags(card: BeautifulSoup) -> list[str]:
        tags = [
            node.get_text(" ", strip=True)
            for node in card.select(".job-category a, [data-id='job-card'] .fs-xs")
        ]
        return JobSource.dedupe_terms(tags, limit=8)

    @staticmethod
    def _extract_published(card: BeautifulSoup) -> str | None:
        badge = card.select_one(".bg-gray-01")
        if badge is None:
            return None
        return badge.get_text(" ", strip=True)

