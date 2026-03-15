from __future__ import annotations

from job_hunter.models import JobListing

from .base import JobSource


class IndeedSource(JobSource):
    source_name = "indeed"
    search_url = "https://in.indeed.com/jobs"

    def __init__(self, source_job_limit: int = 20) -> None:
        super().__init__(source_job_limit=source_job_limit)

    def fetch_jobs(
        self,
        queries: list[str],
        keywords: list[str],
        locations: list[str],
    ) -> list[JobListing]:
        query = self.build_search_queries(queries, keywords)[0]
        location = self.build_search_locations(locations)[0]
        response = self.session.get(
            self.search_url,
            params={"q": query, "l": location},
            timeout=30,
        )
        if response.status_code == 403 or "Security Check" in response.text:
            raise RuntimeError("Indeed blocked automated requests with a security check (403).")
        raise RuntimeError("Indeed page shape changed and parser is not implemented for the new markup.")

