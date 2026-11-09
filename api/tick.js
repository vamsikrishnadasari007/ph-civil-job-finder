// POST /api/tick: called by the Supabase timer (pg_cron) every 30 min, and nightly with ?mode=full.
// Starts the GitHub scrape workflow. Protected by CRON_SECRET (Authorization: Bearer <secret>).
// GitHub's own cron is unreliable for new repos, so this is the dependable trigger; the
// scraper's per-site cadence means an extra or overlapping run costs almost nothing.
const crypto = require("crypto");

function authorized(req) {
  const want = process.env.CRON_SECRET || "";
  const got = String(req.headers.authorization || "").replace(/^Bearer\s+/i, "");
  return want.length > 0 && got.length === want.length && crypto.timingSafeEqual(Buffer.from(got), Buffer.from(want));
}

module.exports = async (req, res) => {
  res.setHeader("Cache-Control", "no-store");
  if (req.method !== "POST") return res.status(405).json({ error: "Method not allowed" });
  if (!authorized(req)) return res.status(401).json({ error: "Unauthorized" });

  const { GITHUB_TOKEN, GITHUB_REPO } = process.env;
  if (!GITHUB_TOKEN || !GITHUB_REPO) return res.status(503).json({ error: "GitHub not configured" });
  const mode = (req.query && req.query.mode) === "full" ? "full" : "quick";
  const gh = (path, init = {}) => fetch(`https://api.github.com/repos/${GITHUB_REPO}${path}`, {
    ...init,
    headers: { Authorization: `Bearer ${GITHUB_TOKEN}`, Accept: "application/vnd.github+json", "User-Agent": "jobs-for-my-love" },
  });
  try {
    // Don't stack quick runs: skip if one is already queued or running. A full run always goes.
    if (mode === "quick") {
      const runs = await gh("/actions/workflows/scrape.yml/runs?per_page=5");
      if (runs.ok) {
        const busy = ((await runs.json()).workflow_runs || [])
          .some((x) => ["queued", "in_progress", "waiting", "pending"].includes(x.status));
        if (busy) return res.status(200).json({ ok: true, skipped: "a run is already in progress" });
      }
    }
    const r = await gh("/actions/workflows/scrape.yml/dispatches", {
      method: "POST",
      body: JSON.stringify({ ref: "main", inputs: { mode, force: "false" } }),
    });
    if (r.status !== 204) return res.status(502).json({ error: `GitHub said ${r.status}` });
    return res.status(202).json({ ok: true, started: mode });
  } catch (e) {
    return res.status(500).json({ error: String(e.message || e) });
  }
};
