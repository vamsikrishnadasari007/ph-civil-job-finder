"""Indeed Philippines — via the python-jobspy library."""
from __future__ import annotations

import math
import time
from datetime import datetime, timezone

import config
from pipeline.model import Job


def _s(v) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return ""
    return str(v).strip()


def _salary(row) -> str:
    lo, hi, cur, per = row.get("min_amount"), row.get("max_amount"), _s(row.get("currency")), _s(row.get("interval"))
    try:
        lo = None if lo is None or math.isnan(lo) else int(lo)
        hi = None if hi is None or math.isnan(hi) else int(hi)
    except TypeError:
        return ""
    if not lo and not hi:
        return ""
    sym = "₱" if cur in ("", "PHP") else f"{cur} "
    rng = f"{sym}{lo:,} – {sym}{hi:,}" if lo and hi and lo != hi else f"{sym}{(lo or hi):,}"
    return f"{rng} per {per}" if per else rng


def collect(mode: str = "full", known: dict | None = None, log=print) -> list[Job]:
    from jobspy import scrape_jobs

    # Indeed returns descriptions inside its search results, so there are no extra requests.
    hours = 3 if mode == "quick" else config.DAYS_BACK * 24      # quick runs are hourly
    wanted = 30 if mode == "quick" else 100
    jobs: list[Job] = []
    failures = 0
    for kw in config.SEARCH_KEYWORDS_LIGHT:
        try:
            df = scrape_jobs(
                site_name=["indeed"], search_term=kw, location="Metro Manila", distance=50,
                results_wanted=wanted, hours_old=hours, country_indeed="philippines",
                description_format="markdown", verbose=0,
            )
        except Exception as e:
            log(f"  Indeed '{kw}' failed: {e}")
            failures += 1
            continue
        for row in df.to_dict("records"):
            posted = row.get("date_posted")
            if hasattr(posted, "isoformat"):
                posted = datetime(posted.year, posted.month, posted.day, tzinfo=timezone.utc).isoformat()
            else:
                posted = ""
            jobs.append(Job(
                platform="Indeed", platform_id=_s(row.get("id")), title=_s(row.get("title")),
                company=_s(row.get("company")), url=_s(row.get("job_url")),
                location=_s(row.get("location")).replace(", P00", ""),
                posted_at=posted, posted_precision="date", salary=_salary(row),
                work_type=_s(row.get("job_type")), description=_s(row.get("description")),
                address=_s(row.get("company_addresses")), company_url=_s(row.get("company_url_direct")),
            ))
        time.sleep(2)
    if failures == len(config.SEARCH_KEYWORDS_LIGHT):
        raise RuntimeError("every Indeed search failed (probably blocked)")
    from pipeline.filters import match_roles
    jobs = [j for j in jobs if match_roles(j.title)]
    log(f"  Indeed: {len(jobs)} postings match her roles")
    return jobs
