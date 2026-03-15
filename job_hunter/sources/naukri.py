from __future__ import annotations

from job_hunter.models import JobListing

from .base import JobSource


class NaukriSource(JobSource):
    source_name = "naukri"

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
        seo_query = query.lower().replace(" ", "-")
        seo_location = location.lower().replace(" ", "-")
        response = self.session.get(
            f"https://www.naukri.com/{seo_query}-jobs-in-{seo_location}",
            timeout=30,
        )
        body = response.text.lower()
        if "access denied" in body or "recaptcha required" in body:
            raise RuntimeError("Naukri blocked automated access for this environment.")
        raise RuntimeError("Naukri search currently renders job data client-side and needs a hardened browser parser.")
