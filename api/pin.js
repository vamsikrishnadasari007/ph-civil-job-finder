// POST /api/pin (header x-pin): check the PIN once so the page can remember it.
const { requirePin } = require("./_lib");

module.exports = async (req, res) => {
  res.setHeader("Cache-Control", "no-store");
  if (req.method !== "POST") return res.status(405).json({ error: "Method not allowed" });
  if (!(await requirePin(req, res))) return;
  res.status(200).json({ ok: true });
};
