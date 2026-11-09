// POST /api/refresh (header x-pin): start a quick search now (GitHub Actions workflow_dispatch).
// Needs env GITHUB_TOKEN (fine-grained, Actions: write on the repo) and GITHUB_REPO ("owner/name").
// Until GitHub is connected it answers 503 with a friendly message.
const { sb, requirePin } = require("./_lib");

const MIN_GAP_MIN = 10;

module.exports = async (req, res) => {
  res.setHeader("Cache-Control", "no-store");
  if (req.method !== "POST") return res.status(405).json({ error: "Method not allowed" });
  if (!(await requirePin(req, res))) return;
  try {
    const { GITHUB_TOKEN, GITHUB_REPO } = process.env;
    if (!GITHUB_TOKEN || !GITHUB_REPO) {
      return res.status(503).json({ error: "Auto-search isn't connected yet. Jobs update on the regular schedule." });
    }
    const gh = (path, init = {}) => fetch(`https://api.github.com/repos/${GITHUB_REPO}${path}`, {
      ...init,
      headers: { Authorization: `Bearer ${GITHUB_TOKEN}`, Accept: "application/vnd.github+json", "User-Agent": "jobs-for-my-love" },
    });

    // Ask GitHub itself (a just-started run hasn't written to scrape_runs yet).
    const runs = await gh("/actions/workflows/scrape.yml/runs?per_page=5");
    if (runs.ok) {
      const list = (await runs.json()).workflow_runs || [];
      if (list.some((x) => x.status === "queued" || x.status === "in_progress" || x.status === "waiting")) {
        return res.status(429).json({ error: "A search is running right now. New jobs will appear in a few minutes 💛" });
      }
      const latest = list[0] ? (Date.now() - Date.parse(list[0].created_at)) / 60000 : Infinity;
      if (latest < MIN_GAP_MIN) {
        return res.status(429).json({ error: `A search ran ${Math.max(1, Math.round(latest))} min ago. Jobs are already fresh 💛` });
      }
    }
    const last = await sb("/scrape_runs?select=started_at&order=started_at.desc&limit=1");
    const mins = last[0] ? (Date.now() - Date.parse(last[0].started_at)) / 60000 : Infinity;
    if (mins < MIN_GAP_MIN) {
      return res.status(429).json({ error: `A search ran ${Math.max(1, Math.round(mins))} min ago. Jobs are already fresh 💛` });
    }
    const r = await gh("/actions/workflows/scrape.yml/dispatches", {
      method: "POST",
      body: JSON.stringify({ ref: "main", inputs: { mode: "quick", force: "true" } }),
    });
    if (r.status !== 204) return res.status(502).json({ error: `GitHub said ${r.status}` });
    return res.status(202).json({ ok: true, message: "Searching all job sites now. New jobs appear in about 2–3 minutes." });
  } catch (e) {
    return res.status(500).json({ error: String(e.message || e) });
  }
};
