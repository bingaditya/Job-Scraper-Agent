from __future__ import annotations

from job_hunter.models import JobListing

from .base import JobSource


class RemoteOKSource(JobSource):
    source_name = "remoteok"
    api_url = "https://remoteok.com/api"

    def fetch_jobs(
        self,
        queries: list[str],
        keywords: list[str],
        locations: list[str],
    ) -> list[JobListing]:
        response = self.session.get(self.api_url, timeout=30)
        response.raise_for_status()
        payload = response.json()

        jobs: list[JobListing] = []
        for item in payload:
            if not isinstance(item, dict) or not item.get("id"):
                continue

            title = item.get("position") or item.get("title") or ""
            company = item.get("company") or ""
            description = self.strip_html(item.get("description"))
            location = item.get("location") or "Remote"
            tags = [str(tag) for tag in item.get("tags", [])]
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
                    source_id=str(item["id"]),
                    title=title,
                    company=company,
                    location=location,
                    url=item.get("url", ""),
                    description=description,
                    tags=tags,
                    published_at=self.normalize_timestamp(item.get("date"))
                    or self.normalize_timestamp(item.get("epoch")),
                    remote=True,
                    metadata={
                        "salary_min": item.get("salary_min"),
                        "salary_max": item.get("salary_max"),
                    },
                )
            )
            if len(jobs) >= self.source_job_limit:
                return jobs
        return jobs
