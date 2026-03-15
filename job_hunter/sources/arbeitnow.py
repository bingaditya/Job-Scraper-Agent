from __future__ import annotations

from job_hunter.models import JobListing

from .base import JobSource


class ArbeitnowSource(JobSource):
    source_name = "arbeitnow"
    api_url = "https://www.arbeitnow.com/api/job-board-api"

    def __init__(self, max_pages: int = 2, source_job_limit: int = 20) -> None:
        super().__init__(source_job_limit=source_job_limit)
        self.max_pages = max_pages

    def fetch_jobs(
        self,
        queries: list[str],
        keywords: list[str],
        locations: list[str],
    ) -> list[JobListing]:
        jobs: list[JobListing] = []
        for page in range(1, self.max_pages + 1):
            response = self.session.get(
                self.api_url,
                params={"page": page},
                timeout=30,
            )
            response.raise_for_status()
            payload = response.json()
            for item in payload.get("data", []):
                description = self.strip_html(item.get("description"))
                tags = [str(tag) for tag in item.get("tags", [])]
                title = item.get("title", "")
                company = item.get("company_name", "")
                location = item.get("location", "Remote")
                if not self.matches_keywords(
                    keywords or queries,
                    title,
                    company,
                    description,
                    location,
                    " ".join(tags),
                ):
                    continue

                jobs.append(
                    JobListing(
                        source=self.source_name,
                        source_id=str(item.get("slug") or item.get("id") or title),
                        title=title,
                        company=company,
                        location=location,
                        url=item.get("url", ""),
                        description=description,
                        tags=tags,
                        published_at=self.normalize_timestamp(item.get("created_at")),
                        remote=bool(item.get("remote")),
                        metadata={
                            "job_types": item.get("job_types", []),
                            "raw_location": item.get("location"),
                        },
                    )
                )
                if len(jobs) >= self.source_job_limit:
                    return jobs
        return jobs
