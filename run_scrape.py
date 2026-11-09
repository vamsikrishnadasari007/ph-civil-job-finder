"""Collect jobs and save them to Supabase (schema `jobfinder`).

    python run_scrape.py --mode quick            # every 30 min: only new postings, per-site cadence
    python run_scrape.py --mode full             # nightly: 14-day sweep, expire old jobs
    python run_scrape.py --mode quick --force    # ignore cadence (run every site now)
    python run_scrape.py --only jobstreet,kalibrr
    python run_scrape.py --dry-run               # collect + filter, print, write nothing

A site that fails or is blocked never stops the others; the failure is logged in scrape_runs
and shown on the website.
"""
from __future__ import annotations

import argparse
import sys
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config  # noqa: E402
from collectors import indeed, jobstreet, kalibrr, linkedin  # noqa: E402
from pipeline import extract  # noqa: E402
from pipeline.dedupe import dedupe_key  # noqa: E402
from pipeline.filters import classify  # noqa: E402
from pipeline.model import Job  # noqa: E402

COLLECTORS = {"JobStreet": jobstreet, "Kalibrr": kalibrr, "Indeed": indeed, "LinkedIn": linkedin}
# Minutes between quick runs per site (GitHub's scheduler fires every 30 min).
CADENCE_MIN = {"JobStreet": 30, "Kalibrr": 30, "Indeed": 60, "LinkedIn": 180}
SLACK_MIN = 8          # scheduler jitter: a site due "in 5 minutes" still runs now
EXPIRE_AFTER_DAYS = 3  # full sweep: not seen for this long → no longer listed
PURGE_AFTER_DAYS = 30


def to_row(j: Job, now: str) -> dict:
    return {
        "id": f"{j.platform.lower()}:{j.platform_id}", "platform": j.platform, "platform_id": j.platform_id,
        "title": j.title, "company": j.company, "url": j.url, "location": j.location, "area": j.area,
        "address": j.address, "salary": j.salary, "work_type": j.work_type, "company_url": j.company_url,
        "description": j.description, "posted_at": j.posted_at or None, "posted_precision": j.posted_precision,
        "roles": j.roles, "resume": j.resume, "emails": j.emails, "phones": j.phones, "experience": j.experience,
        "hidden_reason": j.hidden_reason or None, "dedupe_key": dedupe_key(j),
        "last_seen": now, "is_active": True, "updated_at": now,
    }


def enrich(j: Job) -> Job:
    j.emails = extract.emails(f"{j.description}\n{j.address}")
    j.phones = extract.phones(j.description)
    j.address = j.address or extract.address(j.description)
    return classify(j)


def run_source(name, mod, mode, db, dry) -> dict:
    t0 = time.time()
    run_id = None if dry else db.start_run(name, mode)
    try:
        known = {} if dry else db.known(name)
        collected = mod.collect(mode=mode, known=known, log=lambda m: print(m, flush=True))
        # The same posting can come back from several keyword searches: keep one (fullest text).
        unique: dict[str, Job] = {}
        for j in collected:
            if j.platform_id not in unique or len(j.description) > len(unique[j.platform_id].description):
                unique[j.platform_id] = j
        jobs = list(unique.values())
        now = datetime.now(timezone.utc).isoformat()
        upserts, touch = [], []
        for j in jobs:
            k = known.get(j.platform_id)
            if k and k.get("has_description") and len(j.description) <= 200:
                touch.append(k["id"])          # already stored with full text → just "still listed"
            else:
                upserts.append(to_row(enrich(j), now))
        new = sum(1 for j in jobs if j.platform_id not in known)
        reasons = Counter(r["hidden_reason"] or "SHOWN" for r in upserts)
        if not dry:
            db.upsert_postings(upserts)
            db.touch(touch)
            if mode == "full":
                db.expire(name, datetime.now(timezone.utc) - timedelta(days=EXPIRE_AFTER_DAYS))
            db.finish_run(run_id, ok=True, fetched=len(jobs), new=new)
        print(f"[{name}] ok in {time.time() - t0:.0f}s: {len(jobs)} role matches, {new} new, "
              f"{len(upserts)} saved, {len(touch)} unchanged; {dict(reasons)}", flush=True)
        return dict(ok=True, new=new)
    except Exception as e:
        print(f"[{name}] FAILED after {time.time() - t0:.0f}s: {type(e).__name__}: {e}", flush=True)
        if run_id is not None:
            db.finish_run(run_id, ok=False, error=f"{type(e).__name__}: {e}")
        return dict(ok=False, new=0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["quick", "full"], default="quick")
    ap.add_argument("--only", default="", help="comma-separated site names")
    ap.add_argument("--force", action="store_true", help="ignore per-site cadence")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    db = None
    if not a.dry_run:
        from db import DB
        db = DB()
    only = {s.strip().lower() for s in a.only.split(",") if s.strip()}
    last_ok = db.last_ok() if (db and a.mode == "quick" and not a.force) else {}
    now = datetime.now(timezone.utc)

    results = {}
    for name, mod in COLLECTORS.items():
        if only and name.lower() not in only:
            continue
        due_at = last_ok.get(name, datetime.min.replace(tzinfo=timezone.utc)) + \
            timedelta(minutes=CADENCE_MIN[name] - SLACK_MIN)
        if a.mode == "quick" and not a.force and now < due_at:
            print(f"[{name}] skipped: next quick run due {due_at:%H:%M} UTC")
            continue
        print(f"[{name}] {a.mode} run…", flush=True)
        results[name] = run_source(name, mod, a.mode, db, a.dry_run)

    if db:
        db.set_meta("config", {
            "roles": {k: v["resume"] for k, v in config.ROLES.items()},
            "areas": list(config.AREAS),
            "links": [{"name": n, "url": u} for n, u in config.EXTRA_LINKS],
        })
        if a.mode == "full":
            db.purge(PURGE_AFTER_DAYS)
            from reclassify import reclassify
            reclassify(db)          # apply any filter changes to jobs saved earlier
    print("Summary:", results)
    # Exit non-zero only if every site that ran failed (so the scheduler flags a real outage).
    if results and not any(r["ok"] for r in results.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
