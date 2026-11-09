// GET  /api/status: her Saved / Applied marks (never cached).
// POST /api/status: { key, saved?, applied? } with header x-pin. Updates one mark.
const { sb, requirePin, readBody } = require("./_lib");

module.exports = async (req, res) => {
  res.setHeader("Cache-Control", "no-store");
  try {
    if (req.method === "GET") {
      const rows = await sb("/job_status?select=dedupe_key,saved,applied,applied_at&or=(saved.is.true,applied.is.true)");
      return res.status(200).json(Object.fromEntries(rows.map((r) => [r.dedupe_key, r])));
    }
    if (req.method !== "POST") return res.status(405).json({ error: "Method not allowed" });
    if (!(await requirePin(req, res))) return;

    const { key, saved, applied } = readBody(req);
    if (!key || typeof key !== "string" || key.length > 500) return res.status(400).json({ error: "Bad key" });
    const row = { dedupe_key: key, updated_at: new Date().toISOString() };
    if (typeof saved === "boolean") row.saved = saved;
    if (typeof applied === "boolean") {
      row.applied = applied;
      row.applied_at = applied ? new Date().toISOString() : null;
    }
    const out = await sb("/job_status?on_conflict=dedupe_key", {
      method: "POST", body: row,
      headers: { Prefer: "resolution=merge-duplicates,return=representation" },
    });
    return res.status(200).json(out[0]);
  } catch (e) {
    return res.status(500).json({ error: String(e.message || e) });
  }
};
