"""Kalibrr — public job-board JSON (gives exact post time and an address)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import config
from collectors.http import client, get
from pipeline.filters import match_roles
from pipeline.model import Job, html_to_text

SEARCH = "https://www.kalibrr.com/kjs/job_board/search"
PAGE = 100
MAX_OFFSET = 300


def _address(g: dict) -> str:
    a = (g or {}).get("address_components") or {}
    parts = [a.get("address_line_1"), a.get("address_line_2"), a.get("city"), a.get("region")]
    return ", ".join(p for p in parts if p)


def collect(mode: str = "full", known: dict | None = None, log=print) -> list[Job]:
    c = client(Accept="application/json")
    cutoff = datetime.now(timezone.utc) - timedelta(days=config.DAYS_BACK)
    max_offset = PAGE if mode == "quick" else MAX_OFFSET
    found: dict[str, Job] = {}
    for kw in config.SEARCH_KEYWORDS:
        for offset in range(0, max_offset, PAGE):
            r = get(c, SEARCH, params=dict(limit=PAGE, offset=offset, text=kw, country="Philippines"))
            batch = r.json().get("jobs") or []
            for it in batch:
                posted = it.get("activation_date") or it.get("created_at") or ""
                try:
                    if datetime.fromisoformat(posted) < cutoff:
                        continue
                except ValueError:
                    continue
                comp = it.get("company") or {}
                g = it.get("google_location") or {}
                a = g.get("address_components") or {}
                sal = ""
                if it.get("salary_shown") and it.get("base_salary"):
                    hi = it.get("maximum_salary")
                    sal = f"₱{int(it['base_salary']):,}" + (f" – ₱{int(hi):,}" if hi else "")
                    if it.get("salary_interval"):
                        sal += f" per {it['salary_interval']}"
                jid = str(it["id"])
                found.setdefault(jid, Job(
                    platform="Kalibrr", platform_id=jid, title=it.get("name", ""),
                    company=it.get("company_name") or comp.get("name", ""),
                    url=f"https://www.kalibrr.com/c/{comp.get('code', '')}/jobs/{jid}/{it.get('slug', '')}",
                    location=", ".join(p for p in [a.get("city"), a.get("region")] if p),
                    posted_at=datetime.fromisoformat(posted).astimezone(timezone.utc).isoformat(),
                    posted_precision="exact", salary=sal, work_type=it.get("tenure") or "",
                    description=html_to_text((it.get("description") or "") + "\n" + (it.get("qualifications") or "")),
                    address=_address(g),
                ))
            if len(batch) < PAGE:
                break
    jobs = [j for j in found.values() if match_roles(j.title)]
    log(f"  Kalibrr: {len(found)} postings, {len(jobs)} match her roles")
    return jobs
