# Jobs for My Love 💛

Entry-level civil engineering jobs in Metro Manila and nearby: Site Engineer, Cost Estimator, Assistant QS,
Office Engineer, Project Engineer, Cost Control Engineer. Collected from JobStreet, Indeed, LinkedIn and Kalibrr
and stored in Supabase. A phone-friendly site on Vercel shows them with filters, Saved/Applied marks and an
Excel download.

## Filters applied automatically
- **Male only / male required / male preferred** ads are removed. "Male or female" and female-only ads stay.
- Senior roles, overseas jobs, other disciplines (electrical, mechanical, IT…), and places outside
  Metro Manila, Cavite, Laguna, Rizal, Bulacan, Pampanga and Batangas are removed.
- The same job on several sites becomes one card with every link.
- Recruiter emails, phones and office address are pulled from the description when present.

## How it runs
```
scheduler ─┬─ every 30 min: run_scrape.py --mode quick   (JobStreet+Kalibrr 30 min, Indeed 1 h, LinkedIn 3 h)
           └─ 2 AM Manila : run_scrape.py --mode full    (14-day sweep, expire + purge)
                 │  cheap pre-filters first → full description only for NEW jobs that pass
                 ▼
     Supabase schema `jobfinder` (postings, job_status, scrape_runs, meta + views feed/hidden/…)
                 ▼
     Vercel: site/ + api/jobs · api/status · api/pin · api/refresh   (service key stays server-side)
```

## One-time setup
1. **Supabase → SQL Editor:** run `supabase/schema.sql` (only creates the `jobfinder` schema; it doesn't touch JARVIS tables).
2. **Supabase → Project Settings → Data API → Exposed schemas:** add `jobfinder`.
3. **Vercel:** new project from this folder. Env vars: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `APP_PIN`.
   Optional for "Search now": `GITHUB_TOKEN`, `GITHUB_REPO`.
4. **Scheduler** (GitHub Actions, `.github/workflows/scrape.yml`): repo secrets `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`.

## Local use
```
python -m venv .venv && .venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m pytest -q tests                  # 57 filter tests
.venv\Scripts\python run_scrape.py --mode full            # first fill
.venv\Scripts\python run_scrape.py --mode quick           # what the scheduler runs
.venv\Scripts\python run_scrape.py --dry-run --only jobstreet
node dev_server.js                                        # http://localhost:4321 (site + API)
```
Secrets for local runs are read from `.env.local` (gitignored): `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `APP_PIN`.

## Where to change things
`config.py` holds roles, title patterns, keywords, areas, the male-only patterns, the seniority threshold and the extra links.
Add a test in `tests/test_filters.py` for every filter change.
