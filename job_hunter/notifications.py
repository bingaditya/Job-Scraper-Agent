from __future__ import annotations

import requests

from job_hunter.config import NotificationConfig
from job_hunter.models import RankedJob


class TelegramNotifier:
    def __init__(self, config: NotificationConfig) -> None:
        self.enabled = (
            config.telegram_enabled
            and bool(config.telegram_bot_token)
            and bool(config.telegram_chat_id)
        )
        self.bot_token = config.telegram_bot_token or ""
        self.chat_id = config.telegram_chat_id or ""

    def notify(self, jobs: list[RankedJob]) -> int:
        if not self.enabled:
            return 0

        sent = 0
        for ranked_job in jobs:
            message = self._format_message(ranked_job)
            response = requests.post(
                f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
                json={
                    "chat_id": self.chat_id,
                    "text": message,
                    "disable_web_page_preview": False,
                },
                timeout=30,
            )
            response.raise_for_status()
            sent += 1
        return sent

    @staticmethod
    def _format_message(ranked_job: RankedJob) -> str:
        job = ranked_job.job
        lines = [
            f"New job match: {job.title} at {job.company}",
            f"Score: {ranked_job.score}/100",
            f"Location: {job.location}",
            f"Source: {job.source}",
            f"Apply: {job.url}",
        ]
        if ranked_job.reasons:
            lines.append(f"Why it matched: {ranked_job.reasons[0]}")
        return "\n".join(lines)

