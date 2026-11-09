// Shared helpers for the Vercel API routes. The Supabase service-role key only ever lives
// here (server side); the browser never sees it.
const crypto = require("crypto");

const SCHEMA = "jobfinder";

function env(name) {
  const v = process.env[name];
  if (!v) throw new Error(`Missing env var ${name}`);
  return v;
}

async function sb(path, { method = "GET", body, headers = {} } = {}) {
  const url = env("SUPABASE_URL").replace(/\/$/, "") + "/rest/v1" + path;
  const key = env("SUPABASE_SERVICE_ROLE_KEY");
  const r = await fetch(url, {
    method,
    headers: {
      apikey: key,
      Authorization: `Bearer ${key}`,
      "Accept-Profile": SCHEMA,
      "Content-Profile": SCHEMA,
      "Content-Type": "application/json",
      ...headers,
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`Supabase ${r.status}: ${(await r.text()).slice(0, 300)}`);
  const text = await r.text();
  return text ? JSON.parse(text) : null;
}

// Fetch every row (PostgREST returns at most 1000 per request).
async function sbAll(path) {
  const out = [];
  for (let start = 0; ; start += 1000) {
    const rows = await sb(path, { headers: { Range: `${start}-${start + 999}` } });
    out.push(...rows);
    if (rows.length < 1000) return out;
  }
}

function pinOk(req) {
  const given = String(req.headers["x-pin"] || "");
  const want = String(process.env.APP_PIN || "");
  if (!want || given.length !== want.length) return false;
  return crypto.timingSafeEqual(Buffer.from(given), Buffer.from(want));
}

async function requirePin(req, res) {
  if (pinOk(req)) return true;
  await new Promise((r) => setTimeout(r, 800)); // slow down guessing
  res.status(401).json({ error: "Wrong PIN" });
  return false;
}

function readBody(req) {
  if (req.body && typeof req.body === "object") return req.body;
  try { return JSON.parse(req.body || "{}"); } catch { return {}; }
}

module.exports = { sb, sbAll, requirePin, pinOk, readBody };
