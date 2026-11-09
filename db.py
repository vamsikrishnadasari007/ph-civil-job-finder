"""Supabase (PostgREST) access for the scraper. Everything lives in the `jobfinder` schema.

Needs env vars SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY (locally: jobfinder/.env.local).
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

SCHEMA = "jobfinder"
CHUNK = 200


def load_env(path: Path = Path(__file__).resolve().parent / ".env.local") -> None:
    """Minimal .env reader (no dependency). Real env vars win."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


class DB:
    def __init__(self):
        load_env()
        url, key = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        if not url or not key:
            raise SystemExit("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY are not set")
        self.c = httpx.Client(
            base_url=url.rstrip("/") + "/rest/v1",
            headers={"apikey": key, "Authorization": f"Bearer {key}",
                     "Accept-Profile": SCHEMA, "Content-Profile": SCHEMA},
            timeout=60,
        )

    # ---------------- low level ----------------
    def _check(self, r: httpx.Response) -> httpx.Response:
        if r.status_code >= 400:
            raise RuntimeError(f"Supabase {r.status_code}: {r.text[:300]}")
        return r

    def select_all(self, table: str, params: dict) -> list[dict]:
        out, start = [], 0
        while True:
            r = self._check(self.c.get(f"/{table}", params=params,
                                       headers={"Range": f"{start}-{start + 999}"}))
            rows = r.json()
            out.extend(rows)
            if len(rows) < 1000:
                return out
            start += 1000

    # ---------------- postings ----------------
    def known(self, platform: str) -> dict[str, dict]:
        """platform_id → {id, has_description, first_seen} for this platform's recent postings."""
        since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        rows = self.select_all("postings", {
            "select": "id,platform_id,first_seen,has_description",
            "platform": f"eq.{platform}", "last_seen": f"gte.{since}",
        })
        return {r["platform_id"]: r for r in rows}

    def upsert_postings(self, rows: list[dict]) -> None:
        # PostgREST bulk upsert needs identical keys in every row, so group by key set.
        groups: dict[tuple, list[dict]] = {}
        for r in rows:
            groups.setdefault(tuple(sorted(r)), []).append(r)
        for group in groups.values():
            for i in range(0, len(group), CHUNK):
                self._check(self.c.post(
                    "/postings", params={"on_conflict": "id"}, json=group[i:i + CHUNK],
                    headers={"Prefer": "resolution=merge-duplicates,return=minimal"},
                ))

    def touch(self, ids: list[str]) -> None:
        """Mark postings as still listed (seen again in this run)."""
        now = datetime.now(timezone.utc).isoformat()
        for i in range(0, len(ids), 100):
            part = ",".join(f'"{x}"' for x in ids[i:i + 100])
            self._check(self.c.patch("/postings", params={"id": f"in.({part})"},
                                     json={"last_seen": now, "is_active": True},
                                     headers={"Prefer": "return=minimal"}))

    def expire(self, platform: str, not_seen_since: datetime) -> None:
        """After a full sweep: postings the site no longer lists become inactive."""
        self._check(self.c.patch("/postings", params={
            "platform": f"eq.{platform}", "last_seen": f"lt.{not_seen_since.isoformat()}", "is_active": "is.true",
        }, json={"is_active": False}, headers={"Prefer": "return=minimal"}))

    def purge(self, older_than_days: int) -> None:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=older_than_days)).isoformat()
        self._check(self.c.delete("/postings", params={"posted_at": f"lt.{cutoff}"},
                                  headers={"Prefer": "return=minimal"}))

    # ---------------- runs ----------------
    def last_ok(self) -> dict[str, datetime]:
        rows = self.select_all("source_status", {"select": "source,last_ok_at"})
        return {r["source"]: datetime.fromisoformat(r["last_ok_at"]) for r in rows if r["last_ok_at"]}

    def start_run(self, source: str, mode: str) -> int:
        r = self._check(self.c.post("/scrape_runs", json={"source": source, "mode": mode},
                                    headers={"Prefer": "return=representation"}))
        return r.json()[0]["id"]

    def finish_run(self, run_id: int, *, ok: bool, fetched: int = 0, new: int = 0, error: str = "") -> None:
        self._check(self.c.patch("/scrape_runs", params={"id": f"eq.{run_id}"}, json={
            "ok": ok, "fetched": fetched, "new_count": new, "error": error[:500],
            "finished_at": datetime.now(timezone.utc).isoformat(),
        }, headers={"Prefer": "return=minimal"}))

    # ---------------- meta ----------------
    def set_meta(self, key: str, value) -> None:
        self._check(self.c.post("/meta", params={"on_conflict": "key"},
                                json={"key": key, "value": value,
                                      "updated_at": datetime.now(timezone.utc).isoformat()},
                                headers={"Prefer": "resolution=merge-duplicates,return=minimal"}))
