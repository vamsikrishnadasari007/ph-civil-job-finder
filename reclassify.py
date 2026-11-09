"""Re-apply the current filters (roles, area, male-only, experience, …) to every stored job.

Run after changing config.py / pipeline/filters.py so old jobs follow the new rules:
    python reclassify.py            # apply
    python reclassify.py --dry-run  # only show what would change
The nightly full run calls this automatically.
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from db import DB  # noqa: E402
from pipeline.filters import classify  # noqa: E402
from pipeline.model import Job  # noqa: E402

FIELDS = ("roles", "resume", "area", "hidden_reason", "experience")
KEEP = ("id", "platform", "platform_id", "title", "url", "dedupe_key")   # required columns for the upsert


def reclassify(db: DB, dry: bool = False, log=print) -> Counter:
    rows = db.select_all("postings", {"select": "*", "is_active": "is.true"})
    fields = Job.__dataclass_fields__
    changes, moves = [], Counter()
    for r in rows:
        j = classify(Job(**{k: v for k, v in r.items() if k in fields and k not in FIELDS}))
        new = {"roles": j.roles, "resume": j.resume, "area": j.area,
               "hidden_reason": j.hidden_reason or None, "experience": j.experience}
        if any(r.get(k) != v for k, v in new.items()):
            changes.append({**{k: r[k] for k in KEEP}, **new})
            moves[f"{r.get('hidden_reason') or 'SHOWN'} → {new['hidden_reason'] or 'SHOWN'}"] += 1
    if changes and not dry:
        db.upsert_postings(changes)
    log(f"reclassify: {len(rows)} jobs checked, {len(changes)} updated")
    for k, n in moves.most_common():
        if k.split(" → ")[0] != k.split(" → ")[1]:
            log(f"   {n:4d}  {k}")
    return moves


if __name__ == "__main__":
    reclassify(DB(), dry="--dry-run" in sys.argv)
