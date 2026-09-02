#!/usr/bin/env python3
"""build_api_worker.py - build the Skillowkey API worker with 28k skills EMBEDDED.
The interactive app (index.html) + data/skills.json + SEO pages are Cloudflare
static assets. This worker handles /api/* and /health. It carries the full
skill dataset gzipped+base64 (2.2MB, under 3MB limit) and decodes lazily via
DecompressionStream - so it never needs to self-fetch assets.
"""
import json, gzip, base64
from pathlib import Path
BASE = Path(__file__).parent

# Build embedded dataset: exclude malicious only (keep suspicious = legit security)
skills = json.loads((BASE / "data" / "skills.json").read_text())
vf = BASE / "data" / "vet_flags.json"
if vf.exists():
    try:
        f = json.loads(vf.read_text())
        ex = {x["index"] for x in f["flagged"] if x["type"] == "malicious"}
        skills = [s for i, s in enumerate(skills) if i not in ex]
    except Exception:
        pass

raw = json.dumps(skills, ensure_ascii=False, separators=(",", ":")).encode()
gz = gzip.compress(raw, 9)
B64 = base64.b64encode(gz).decode()

worker = """// Skillowkey API worker. Full dataset embedded (gzip+base64) -> decoded lazily.
const DATA_B64 = "__B64__";
let DATA = null;
let DATA_LOADING = null;

async function loadData() {
  if (DATA) return DATA;
  if (DATA_LOADING) return DATA_LOADING;
  DATA_LOADING = (async () => {
    try {
      const bin = Uint8Array.from(atob(DATA_B64), c => c.charCodeAt(0));
      const ds = new DecompressionStream('gzip');
      const stream = new Blob([bin]).stream().pipeThrough(ds);
      const text = await new Response(stream).text();
      DATA = JSON.parse(text);
    } finally { DATA_LOADING = null; }
    return DATA;
  })();
  return DATA_LOADING;
}

const FREE_LIMIT = 60, PRO_LIMIT = 6000;
const buckets = new Map();
function checkLimit(ip, lim) {
  const now = Date.now(), key = ip + lim;
  let b = buckets.get(key) || { t: now, c: 0 };
  if (now - b.t > 60000) { b = { t: now, c: 0 }; }
  b.c++; buckets.set(key, b);
  if (buckets.size > 10000) { for (const [k, v] of buckets) if (Date.now() - v.t > 120000) buckets.delete(k); }
  return b.c <= lim;
}

function runQuery(SKILLS, p) {
  const q = (p.q || "").toLowerCase(), cat = p.cat || "", tag = p.tag || "";
  const sort = p.sort || "best";
  let page = Math.max(1, parseInt(p.page) || 1), per = 50;
  let out = [];
  for (const s of SKILLS) {
    const name = s[0] || "", desc = s[1] || "", c = s[2] || "", tags = s[5] || [], stars = s[6] || 0;
    if (cat && !c.includes(cat)) continue;
    if (tag && !tags.includes(tag)) continue;
    if (q && !(name.toLowerCase().includes(q) || desc.toLowerCase().includes(q) || c.toLowerCase().includes(q))) continue;
    let score = 0;
    if (q) { if (name.toLowerCase().includes(q)) score += 10; if (c.toLowerCase().includes(q)) score += 5; if (desc.toLowerCase().includes(q)) score += 1; }
    score += Math.min(Math.log1p(stars || 0) / Math.log(10), 5);
    out.push({ name, desc, category: c, source: s[3], url: s[4], tags, stars, score });
  }
  if (sort === "stars") out.sort((a, b) => (b.stars || 0) - (a.stars || 0));
  else out.sort((a, b) => (b.score || 0) - (a.score || 0));
  const total = out.length, start = (page - 1) * per;
  return { total, page, per, results: out.slice(start, start + per) };
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const path = url.pathname;
    if (path.startsWith("/api/")) {
      const ip = request.headers.get("CF-Connecting-IP") || "anon";
      const isPro = request.headers.has("x-pro-key");
      const lim = isPro ? PRO_LIMIT : FREE_LIMIT;
      if (!checkLimit(ip, lim))
        return new Response(JSON.stringify({ error: "rate_limited", retry_after_ms: 60000 }),
          { status: 429, headers: { "content-type": "application/json" } });
      if (path === "/api/search") {
        const SKILLS = await loadData();
        const res = runQuery(SKILLS, Object.fromEntries(url.searchParams));
        return new Response(JSON.stringify(res), { headers: { "content-type": "application/json", "access-control-allow-origin": "*" } });
      }
      if (path === "/api/stats") {
        const SKILLS = await loadData();
        const cats = {};
        for (const s of SKILLS) { const c = s[2] || "general"; cats[c] = (cats[c] || 0) + 1; }
        return new Response(JSON.stringify({ total: SKILLS.length, categories: cats }),
          { headers: { "content-type": "application/json", "access-control-allow-origin": "*" } });
      }
      if (path === "/api/pro")
        return new Response(JSON.stringify({ plan: "pro", status: "available" }),
          { headers: { "content-type": "application/json" } });
      return new Response(JSON.stringify({ error: "not_found" }), { status: 404, headers: { "content-type": "application/json" } });
    }
    if (path === "/health") return new Response("ok", { headers: { "content-type": "text/plain" } });
    return new Response("Skillowkey", { status: 200 });
  }
};
"""
worker = worker.replace("__B64__", B64)
OUT = BASE / "api_worker.js"
OUT.write_text(worker)
print("api_worker.js:", len(worker), "bytes (under 3MB:", len(worker) < 3_000_000, "| embedded:", len(skills), "skills)")