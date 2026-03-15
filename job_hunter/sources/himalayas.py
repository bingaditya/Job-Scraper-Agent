from __future__ import annotations

from bs4 import BeautifulSoup

from job_hunter.models import JobListing

from .base import JobSource


class HimalayasSource(JobSource):
    source_name = "himalayas"
    search_url = "https://himalayas.app/jobs"
    base_url = "https://himalayas.app"

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
                    params={"query": query, "page": page_number},
                    timeout=30,
                )
                response.raise_for_status()
                soup = BeautifulSoup(response.text, "html.parser")
                for article in soup.select("article"):
                    title_link = article.select_one('a[href*="/jobs/"]')
                    company_link = article.select_one('a[href^="/companies/"]:not([href*="/jobs/"])')
                    if title_link is None or company_link is None:
                        continue

                    title = title_link.get_text(" ", strip=True)
                    company = company_link.get_text(" ", strip=True)
                    url = self.absolute_url(self.base_url, title_link.get("href"))
                    if not title or not company or not url or url in seen_urls:
                        continue
                    seen_urls.add(url)

                    article_text = article.get_text(" ", strip=True)
                    location = self._extract_location(article_text, locations)
                    published_at = self._extract_published(article)
                    if not self.matches_keywords(
                        keywords,
                        title,
                        company,
                        location,
                        article_text,
                    ):
                        continue

                    jobs.append(
                        JobListing(
                            source=self.source_name,
                            source_id=url.rstrip("/").split("/")[-1].split("?")[0],
                            title=title,
                            company=company,
                            location=location,
                            url=url,
                            description=article_text,
                            tags=self._extract_tags(article_text),
                            published_at=published_at,
                            remote=True,
                        )
                    )
                    if len(jobs) >= self.source_job_limit:
                        return jobs
        return jobs

    @staticmethod
    def _extract_location(article_text: str, preferred_locations: list[str]) -> str:
        lowered = article_text.lower()
        for candidate in ["Remote", "Worldwide", "India", "United States", "United Kingdom"]:
            if candidate.lower() in lowered:
                return candidate
        for preferred_location in preferred_locations:
            if preferred_location.lower() in lowered:
                return preferred_location
        return "Remote"

    @staticmethod
    def _extract_published(article: BeautifulSoup) -> str | None:
        time_node = article.select_one("time")
        if time_node is None:
            return None
        return time_node.get_text(" ", strip=True)

    @staticmethod
    def _extract_tags(article_text: str) -> list[str]:
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
            "remote",
            "contractor",
        ]
        lowered = article_text.lower()
        return [tag for tag in canonical_tags if tag in lowered]

