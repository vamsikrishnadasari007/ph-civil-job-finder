// GET /api/jobs: everything the page needs in one response (cached at Vercel's edge for 60 s).
const { sb, sbAll } = require("./_lib");

module.exports = async (req, res) => {
  try {
    const [jobs, hidden, counts, sources, meta] = await Promise.all([
      sbAll("/feed?select=*&order=posted_at.desc.nullslast"),
      sbAll("/hidden?select=*&order=posted_at.desc.nullslast"),
      sb("/hidden_counts?select=*"),
      sb("/source_status?select=*"),
      sb("/meta?key=eq.config&select=value"),
    ]);
    const cfg = (meta[0] && meta[0].value) || { roles: {}, areas: [], links: [] };
    const okTimes = sources.map((s) => s.last_ok_at).filter(Boolean).sort();
    res.setHeader("Cache-Control", "public, s-maxage=60, stale-while-revalidate=600");
    res.status(200).json({
      generated_at: okTimes[okTimes.length - 1] || null,
      sources: Object.fromEntries(sources.map((s) => [s.source, {
        ok: s.ok !== false, at: s.last_ok_at, running: s.finished_at == null, error: s.error || "",
      }])),
      hidden_counts: Object.fromEntries(counts.map((c) => [c.hidden_reason, c.n])),
      roles: cfg.roles,
      areas: cfg.areas,
      links: cfg.links,
      jobs,
      hidden: hidden.map((h) => ({ ...h, roles: h.roles || [] })),
    });
  } catch (e) {
    res.status(500).json({ error: String(e.message || e) });
  }
};
