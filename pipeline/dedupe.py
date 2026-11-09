"""Merge the same job posted on several platforms into one entry (keeping every link)."""
from __future__ import annotations

import re
from datetime import datetime

from pipeline.model import Job

# Order of preference for which copy becomes the "main" card (richest data first).
PLATFORM_RANK = {"JobStreet": 0, "Kalibrr": 1, "Indeed": 2, "LinkedIn": 3}

_CO_NOISE = re.compile(
    r"\b(inc|incorporated|corp|corporation|co|company|ltd|limited|phils?|philippines|opc|"
    r"construction|development|builders?|and|the|enterprises?|group)\b|[^a-z0-9 ]",
    re.I,
)
_TITLE_NOISE = re.compile(r"\(.*?\)|[^a-z0-9 ]|\b(urgent|hiring|needed|wanted|immediate)\b", re.I)


def _norm(s: str, noise: re.Pattern) -> str:
    return " ".join(noise.sub(" ", (s or "").lower()).split())


def dedupe_key(j: Job) -> str:
    """Same company + same title (noise words removed) = the same job, whatever the platform."""
    return f"{_norm(j.company, _CO_NOISE)}|{_norm(j.title, _TITLE_NOISE)}"


_key = dedupe_key


def _ts(j: Job) -> float:
    try:
        return datetime.fromisoformat(j.posted_at.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def dedupe(jobs: list[Job]) -> list[Job]:
    # Same platform + same id → exact duplicate (from overlapping keyword searches).
    by_id: dict[tuple, Job] = {}
    for j in jobs:
        k = (j.platform, j.platform_id)
        if k not in by_id or len(j.description) > len(by_id[k].description):
            by_id[k] = j

    groups: dict[str, list[Job]] = {}
    for j in by_id.values():
        groups.setdefault(_key(j), []).append(j)

    out = []
    for group in groups.values():
        group.sort(key=lambda j: (PLATFORM_RANK.get(j.platform, 9), -_ts(j)))
        main = group[0]
        for other in group[1:]:
            # Only merge postings within 5 days of each other (same company may re-post later).
            if abs(_ts(main) - _ts(other)) > 5 * 86400:
                out.append(other)
                continue
            main.also_on.append({"platform": other.platform, "url": other.url})
            main.address = main.address or other.address
            main.salary = main.salary or other.salary
            if len(other.description) > len(main.description):
                main.description = other.description
        out.append(main)
    return out
