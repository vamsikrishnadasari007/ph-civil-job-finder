"""JobStreet PH — public search API (SEEK v5) + GraphQL for the full job description.

quick: nationwide keyword search, last 1 day, newest first (≈13 requests).
full : keyword × area search over the last 14 days (fills gaps, lets old jobs expire).
Full descriptions are fetched only for NEW postings that pass the cheap pre-filter.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import config
from collectors.http import client, get, post
from pipeline.filters import match_roles, prefilter_reason
from pipeline.model import Job, html_to_text

SEARCH = "https://ph.jobstreet.com/api/jobsearch/v5/search"
GRAPHQL = "https://ph.jobstreet.com/graphql"
DETAILS_QUERY = """query jobDetails($jobId: ID!, $locale: Locale!, $timezone: Timezone!) {
  jobDetails(id: $jobId) { job { id content(platform: WEB) isExpired
    listedAt { dateTimeUtc label(context: JOB_POSTED, length: SHORT, timezone: $timezone, locale: $locale) } } } }"""


def _search(c, keyword: str, where: str | None, days: int, max_pages: int, known: dict) -> list[dict]:
    out = []
    for page in range(1, max_pages + 1):
        params = dict(siteKey="PH-Main", sourcesystem="houston", keywords=keyword, page=page, pageSize=100,
                      locale="en-PH", dateRange=days, sortmode="ListedDate")
        if where:
            params["where"] = where
        data = get(c, SEARCH, params=params).json().get("data") or []
        out.extend(data)
        # Newest first: once a whole page is already known, older pages are too.
        if len(data) < 100 or all(str(d["id"]) in known for d in data):
            break
    return out


def _details(c, job_id: str) -> dict:
    r = post(c, GRAPHQL, json=dict(
        operationName="jobDetails", query=DETAILS_QUERY,
        variables=dict(jobId=job_id, locale="en-PH", timezone="Asia/Manila"),
    ), pause=(0.2, 0.6))
    return ((r.json().get("data") or {}).get("jobDetails") or {}).get("job") or {}


def collect(mode: str = "full", known: dict | None = None, log=print) -> list[Job]:
    known = known or {}
    c = client(**{"seek-request-brand": "jobstreet", "seek-request-country": "PH"})
    raw: dict[str, dict] = {}
    if mode == "quick":
        for kw in config.SEARCH_KEYWORDS:
            for it in _search(c, kw, None, days=1, max_pages=3, known=known):
                raw.setdefault(str(it["id"]), it)
    else:
        for kw in config.SEARCH_KEYWORDS:
            for where in config.SEARCH_LOCATIONS:
                for it in _search(c, kw, where, days=config.DAYS_BACK, max_pages=4, known={}):
                    raw.setdefault(str(it["id"]), it)
    log(f"  JobStreet: {len(raw)} postings in search results")

    jobs = []
    for jid, it in raw.items():
        if not match_roles(it.get("title", "")):
            continue
        jobs.append(Job(
            platform="JobStreet", platform_id=jid, title=it.get("title", ""),
            company=(it.get("advertiser") or {}).get("description", "") or it.get("companyName", ""),
            url=f"https://ph.jobstreet.com/job/{jid}",
            location=", ".join(l.get("label", "") for l in it.get("locations") or []),
            posted_at=it.get("listingDate", ""), posted_precision="exact",
            salary=it.get("salaryLabel", ""), work_type=", ".join(it.get("workTypes") or []),
            description=it.get("teaser", ""),
        ))

    need = [j for j in jobs
            if not prefilter_reason(j) and not (known.get(j.platform_id) or {}).get("has_description")]
    log(f"  JobStreet: {len(jobs)} match her roles; {len(need)} new & worth opening")

    def fill(j: Job):
        try:
            d = _details(c, j.platform_id)
            if d.get("isExpired"):
                j.title = ""
            elif d.get("content"):
                j.description = html_to_text(d["content"])
        except Exception as e:
            log(f"    details failed for {j.platform_id}: {e}")
        return j

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(fill, need))
    return [j for j in jobs if j.title]
