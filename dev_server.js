// Local stand-in for Vercel: serves site/ and runs api/*.js with the same (req, res) shape.
//   node dev_server.js     → http://localhost:4321
const http = require("http");
const fs = require("fs");
const path = require("path");

for (const line of fs.readFileSync(path.join(__dirname, ".env.local"), "utf8").split(/\r?\n/)) {
  const m = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$/);
  if (m && !process.env[m[1]]) process.env[m[1]] = m[2].replace(/^["']|["']$/g, "");
}

const TYPES = { ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".css": "text/css", ".json": "application/json" };
const PORT = process.env.PORT || 4321;

http.createServer(async (req, res) => {
  const url = new URL(req.url, "http://x");
  res.status = (c) => { res.statusCode = c; return res; };
  res.json = (o) => { res.setHeader("Content-Type", "application/json"); res.end(JSON.stringify(o)); };

  if (url.pathname.startsWith("/api/")) {
    const file = path.join(__dirname, "api", path.basename(url.pathname) + ".js");
    if (!fs.existsSync(file) || path.basename(file).startsWith("_")) return res.status(404).json({ error: "not found" });
    let body = "";
    for await (const chunk of req) body += chunk;
    req.body = body;
    req.query = Object.fromEntries(url.searchParams);
    delete require.cache[require.resolve(file)];
    return require(file)(req, res);
  }
  const rel = url.pathname === "/" ? "index.html" : url.pathname.slice(1);
  const file = path.join(__dirname, "site", path.normalize(rel));
  if (!file.startsWith(path.join(__dirname, "site")) || !fs.existsSync(file)) { res.statusCode = 404; return res.end("not found"); }
  res.setHeader("Content-Type", TYPES[path.extname(file)] || "application/octet-stream");
  fs.createReadStream(file).pipe(res);
}).listen(PORT, () => console.log(`Jobs for My Love running at http://localhost:${PORT}`));
