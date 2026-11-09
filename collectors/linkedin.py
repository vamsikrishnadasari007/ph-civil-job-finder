"""LinkedIn — public guest job pages (no login).

LinkedIn rate-limits hard, so: slow pauses, a small time window on quick runs, and the full
description is opened ONLY for new postings that pass the cheap pre-filter. If LinkedIn blocks
us, we stop and keep what we already have.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from selectolax.lexbor import LexborHTMLParser as HTMLParser

import config
from collectors.http import RateLimited, client, get
from pipeline.filters import match_roles, prefilter_reason
from pipeline.model import Job, html_to_text

LIST = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
DETAIL = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{id}"
LOCATIONS = ["Metro Manila, Philippines", "Calabarzon, Philippines", "Central Luzon, Philippines"]
SLOW = (2.0, 4.0)
QUICK_WINDOW_S = 6 * 3600     # quick runs happen every 3 h; 6 h window gives overlap

_AGO = re.compile(r"(\d+)\s*(minute|hour|day|week|month)s?\s*ago", re.I)


def _posted(date_attr: str, ago_text: str) -> tuple[str, str]:
    m = _AGO.search(ago_text or "")
    if m and m.group(2).lower() in ("minute", "hour"):
        n = int(m.group(1))
        delta = timedelta(minutes=n) if m.group(2).lower() == "minute" else timedelta(hours=n)
        return (datetime.now(timezone.utc) - delta).replace(second=0, microsecond=0).isoformat(), "hour"
    if date_attr:
        return f"{date_attr}T00:00:00+00:00", "date"
    return "", "date"


def _parse_list(html: str) -> list[Job]:
    out = []
    for card in HTMLParser(html).css("div.base-card, div.job-search-card"):
        jid = card.attributes.get("data-entity-urn", "").rsplit(":", 1)[-1]
        t = card.css_first("h3.base-search-card__title")
        co = card.css_first("h4.base-search-card__subtitle")
        loc = card.css_first("span.job-search-card__location")
        link = card.css_first("a.base-card__full-link")
        tm = card.css_first("time")
        if not (jid and t and link):
            continue
        posted, prec = _posted(tm.attributes.get("datetime", "") if tm else "", tm.text(strip=True) if tm else "")
        sal = card.css_first("span.job-search-card__salary-info")
        out.append(Job(
            platform="LinkedIn", platform_id=jid, title=t.text(strip=True),
            company=co.text(strip=True) if co else "", location=loc.text(strip=True) if loc else "",
            url=link.attributes.get("href", "").split("?")[0], posted_at=posted, posted_precision=prec,
            salary=sal.text(strip=True) if sal else "",
        ))
    return out


def collect(mode: str = "full", known: dict | None = None, log=print) -> list[Job]:
    known = known or {}
    c = client()
    window = QUICK_WINDOW_S if mode == "quick" else config.DAYS_BACK * 86400
    pages = 2 if mode == "quick" else 3
    found: dict[str, Job] = {}
    blocked = False
    for kw in config.SEARCH_KEYWORDS_LIGHT:
        for loc in LOCATIONS:
            for page in range(pages):
                try:
                    r = get(c, LIST, params=dict(keywords=kw, location=loc, f_TPR=f"r{window}",
                                                 sortBy="DD", start=page * 10), pause=SLOW, tries=2)
                except RateLimited:
                    blocked = True
                    break
                batch = _parse_list(r.text)
                for j in batch:
                    found.setdefault(j.platform_id, j)
                if len(batch) < 10 or all(j.platform_id in known for j in batch):
                    break
            if blocked:
                break
        if blocked:
            break

    jobs = [j for j in found.values() if match_roles(j.title)]
    need = [j for j in jobs
            if not prefilter_reason(j) and not (known.get(j.platform_id) or {}).get("has_description")]
    log(f"  LinkedIn: {len(found)} postings, {len(jobs)} match her roles, {len(need)} new & worth opening"
        f"{' (search stopped early: rate-limited)' if blocked else ''}")

    for j in need:
        try:
            r = get(c, DETAIL.format(id=j.platform_id), pause=SLOW, tries=2)
        except RateLimited:
            log("  LinkedIn: rate-limited while opening jobs; the rest will be opened next run")
            break
        except Exception:
            continue
        node = HTMLParser(r.text).css_first("div.show-more-less-html__markup")
        if node:
            j.description = html_to_text(node.html)
    if blocked and not found:
        raise RuntimeError("rate-limited by LinkedIn before any results")
    return jobs
