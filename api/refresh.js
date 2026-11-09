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
    const last = await sb("/scrape_runs?select=started_at&order=started_at.desc&limit=1");
    const mins = last[0] ? (Date.now() - Date.parse(last[0].started_at)) / 60000 : Infinity;
    if (mins < MIN_GAP_MIN) {
      return res.status(429).json({ error: `A search ran ${Math.round(mins)} min ago. New jobs are already on the way 💛` });
    }
    const r = await fetch(`https://api.github.com/repos/${GITHUB_REPO}/actions/workflows/scrape.yml/dispatches`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${GITHUB_TOKEN}`,
        Accept: "application/vnd.github+json",
        "User-Agent": "jobs-for-my-love",
      },
      body: JSON.stringify({ ref: "main", inputs: { mode: "quick", force: "true" } }),
    });
    if (r.status !== 204) return res.status(502).json({ error: `GitHub said ${r.status}` });
    return res.status(202).json({ ok: true, message: "Searching all job sites now. New jobs appear in about 2–3 minutes." });
  } catch (e) {
    return res.status(500).json({ error: String(e.message || e) });
  }
};
