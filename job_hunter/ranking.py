from __future__ import annotations

import re

from job_hunter.config import CandidateProfile, SearchConfig
from job_hunter.models import JobListing


def job_matches_location(
    job: JobListing,
    profile: CandidateProfile,
    search: SearchConfig,
) -> bool:
    if not search.strict_location_match:
        return True

    haystack = " ".join([job.location, job.description, " ".join(job.tags)]).lower()
    return any(location.lower() in haystack for location in profile.preferred_locations)


def score_job(
    job: JobListing,
    profile: CandidateProfile,
    search: SearchConfig,
) -> tuple[int, list[str], list[str]]:
    score = 0
    reasons: list[str] = []
    matched_skills: list[str] = []

    text = " ".join([job.title, job.description, job.location, " ".join(job.tags)]).lower()
    title_text = job.title.lower()
    location_text = job.location.lower()

    for skill in profile.skills:
        if skill.lower() in text:
            matched_skills.append(skill)
            score += 12

    if matched_skills:
        reasons.append(f"Matched skills: {', '.join(matched_skills[:5])}")

    title_hits = [title for title in profile.preferred_titles if title.lower() in title_text]
    if title_hits:
        score += 20
        reasons.append(f"Preferred title match: {title_hits[0]}")

    keyword_hits = [keyword for keyword in search.keywords if keyword.lower() in text]
    if keyword_hits:
        score += min(10, len(keyword_hits) * 4)
        reasons.append(f"Search keyword hit: {keyword_hits[0]}")

    if job.remote and profile.remote_first:
        score += 10
        reasons.append("Remote-friendly job")
    else:
        location_hits = [
            location
            for location in profile.preferred_locations
            if location.lower() in location_text
        ]
        if location_hits:
            score += 10
            reasons.append(f"Preferred location: {location_hits[0]}")

    required_years = extract_required_years(job.description)
    if required_years is None:
        score += 8
        reasons.append("Experience requirement not strict")
    elif profile.experience_years + 1 >= required_years:
        score += 12
        reasons.append(f"Experience fit around {required_years}+ years")
    else:
        penalty = min(20, (required_years - profile.experience_years) * 5)
        score -= penalty
        reasons.append(f"Role asks for {required_years}+ years")

    return max(0, min(score, 100)), reasons, matched_skills


def extract_required_years(description: str) -> int | None:
    matches = re.findall(r"(\d+)\+?\s+years", description.lower())
    if not matches:
        return None
    return min(int(value) for value in matches)
