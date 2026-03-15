from __future__ import annotations

from job_hunter.config import SourceConfig

from .arbeitnow import ArbeitnowSource
from .base import JobSource
from .builtin import BuiltInSource
from .himalayas import HimalayasSource
from .indeed import IndeedSource
from .linkedin import LinkedInSource
from .naukri import NaukriSource
from .remoteok import RemoteOKSource


def build_sources(config: SourceConfig) -> list[JobSource]:
    sources: list[JobSource] = []
    enabled = {name.lower() for name in config.enabled}

    if "arbeitnow" in enabled:
        sources.append(
            ArbeitnowSource(
                max_pages=config.arbeitnow_pages,
                source_job_limit=config.source_job_limit,
            )
        )
    if "remoteok" in enabled:
        sources.append(RemoteOKSource(source_job_limit=config.source_job_limit))
    if "linkedin" in enabled:
        sources.append(
            LinkedInSource(
                pages=config.linkedin_pages,
                source_job_limit=config.source_job_limit,
            )
        )
    if "builtin" in enabled:
        sources.append(
            BuiltInSource(
                pages=config.builtin_pages,
                source_job_limit=config.source_job_limit,
            )
        )
    if "himalayas" in enabled:
        sources.append(
            HimalayasSource(
                pages=config.himalayas_pages,
                source_job_limit=config.source_job_limit,
            )
        )
    if "indeed" in enabled:
        sources.append(IndeedSource(source_job_limit=config.source_job_limit))
    if "naukri" in enabled:
        sources.append(NaukriSource(source_job_limit=config.source_job_limit))

    return sources
