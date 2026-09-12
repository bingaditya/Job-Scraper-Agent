from __future__ import annotations

import re

_SKILLS_HEADING_PATTERN = re.compile(r"skills|expertise|technologies|technical", re.IGNORECASE)


def looks_like_skill_list(text: str) -> bool:
    items = [item.strip() for item in text.split(",")]
    return len(items) >= 3 and all(0 < len(item) <= 40 for item in items)


def find_skills_line_index(lines: list[str]) -> int | None:
    """Heuristically locate a skills/technologies list among plain text lines.

    Looks for either a short heading (e.g. "Skills") followed by the next
    non-empty line, or a line that itself reads like a comma-separated list
    of short items.
    """
    for index, raw_line in enumerate(lines):
        text = raw_line.strip()
        if not text:
            continue
        if _SKILLS_HEADING_PATTERN.search(text) and len(text) < 60:
            for next_index in range(index + 1, len(lines)):
                if lines[next_index].strip():
                    return next_index
        elif len(text) < 300 and looks_like_skill_list(text):
            return index
    return None


def present_keywords(text: str, keywords: list[str]) -> list[str]:
    lowered = text.lower()
    return [keyword for keyword in keywords if keyword.lower() in lowered]


def fit_score(text: str, keywords: list[str]) -> int:
    if not keywords:
        return 100
    matched = len(present_keywords(text, keywords))
    return int(round((matched / len(keywords)) * 100))
