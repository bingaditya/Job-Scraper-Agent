from __future__ import annotations

import requests
from bs4 import BeautifulSoup

from job_hunter.models import JobListing

from .base import JobSource


class LinkedInSource(JobSource):
    source_name = "linkedin"
    search_url = "https://www.linkedin.com/jobs/search/"

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
        detail_fetch_enabled = True
        search_queries = self.build_search_queries(queries, keywords)
        search_locations = self.build_search_locations(locations)

        for query in search_queries:
            for location in search_locations:
                for page_number in range(self.pages):
                    response = self.session.get(
                        self.search_url,
                        params={
                            "keywords": query,
                            "location": location,
                            "start": page_number * 25,
                        },
                        timeout=30,
                    )
                    response.raise_for_status()
                    soup = BeautifulSoup(response.text, "html.parser")
                    cards = soup.select(".base-search-card")
                    for card in cards:
                        link = card.select_one("a.base-card__full-link")
                        title_node = card.select_one("h3.base-search-card__title")
                        company_node = card.select_one("h4.base-search-card__subtitle")
                        location_node = card.select_one(".job-search-card__location")
                        time_node = card.select_one("time")
                        if link is None or title_node is None or company_node is None:
                            continue

                        url = link.get("href", "").split("?")[0]
                        if not url or url in seen_urls:
                            continue
                        seen_urls.add(url)

                        card_text = card.get_text(" ", strip=True)
                        description = card_text
                        if detail_fetch_enabled:
                            try:
                                description = self._fetch_description(url) or card_text
                            except requests.RequestException:
                                detail_fetch_enabled = False
                                description = card_text
                        title = title_node.get_text(" ", strip=True)
                        company = company_node.get_text(" ", strip=True)
                        job_location = (
                            location_node.get_text(" ", strip=True)
                            if location_node is not None
                            else location
                        )
                        tags = self._extract_tags(description)
                        if not self.matches_keywords(
                            keywords,
                            title,
                            company,
                            job_location,
                            description,
                            " ".join(tags),
                        ):
                            continue

                        jobs.append(
                            JobListing(
                                source=self.source_name,
                                source_id=url.rstrip("/").rsplit("-", 1)[-1],
                                title=title,
                                company=company,
                                location=job_location,
                                url=url,
                                description=description,
                                tags=tags,
                                published_at=(
                                    self.normalize_timestamp(time_node.get("datetime"))
                                    if time_node is not None
                                    else None
                                ),
                                remote="remote" in job_location.lower(),
                            )
                        )
                        if len(jobs) >= self.source_job_limit:
                            return jobs
        return jobs

    def _fetch_description(self, url: str) -> str:
        response = self.session.get(url, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        description_node = soup.select_one(".show-more-less-html__markup")
        if description_node is None:
            description_node = soup.select_one(".description__text")
        if description_node is None:
            return ""
        return description_node.get_text(" ", strip=True)

    @staticmethod
    def _extract_tags(description: str) -> list[str]:
        canonical_tags = [
            "python",
            "azure",
            "sql",
            "pyspark",
            "snowflake",
            ".net",
            "c#",
            "fastapi",
            "javascript",
            "ci/cd",
            "datadog",
        ]
        text = description.lower()
        return [tag for tag in canonical_tags if tag in text]
