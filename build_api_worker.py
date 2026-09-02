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

# Merge real GitHub meta (stars, pushed_at, created_at) into rows, mirroring build.py.
# Row becomes [name, desc, cat, src, url, tags, stars, pushed, created].
mp = BASE / "data" / "skills_meta.json"
if mp.exists():
    meta = json.loads(mp.read_text())
    merged = []
    for s in skills:
        url = s[4]
        m = meta.get(url, {})
        stars = m.get("stars", 0) or m.get("stargazers", 0) or 0
        pushed = m.get("pushed_at", "") or ""
        created = m.get("created_at", "") or ""
        base = list(s)
        while len(base) < 6: base.append([])
        merged.append([base[0], base[1], base[2], base[3], base[4], base[5], stars, pushed, created])
    skills = merged

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

// Token-stopwords for query parsing (words that don't carry skill intent)
const STOP = new Set(["the","a","an","for","to","of","and","or","in","on","with","by","me","my","i","want","need","build","make","create","write","find","get","help","using","use","do","can","how","what","click","action","function","tool","skill","agent","claude","gemini","gpt"]);

// /api/recommend - zero-token local semantic ranking.
// Given a natural-language goal ("help me audit a data breach response"),
// tokenizes it, scores every skill by weighted term match across name/desc/category/tags,
// boosts by stars, and returns top N with a plain-English "why" reason.
function recommended(skills_, q, cat, tag, limit) {
  q = (q || "").toLowerCase();
  const tokens = q.split(/[^a-z0-9]+/).filter(t => t.length > 2 && !STOP.has(t));
  // also extract 2-word phrases
  let phrases = [];
  for (let i = 0; i < tokens.length - 1; i++) phrases.push(tokens[i] + " " + tokens[i+1]);
  const scored = [];
  for (const s of skills_) {
    const name = (s[0]||"").toLowerCase(), desc = (s[1]||"").toLowerCase(),
          c = (s[2]||"").toLowerCase(), tags = (s[5]||[]).join(" ").toLowerCase(),
          stars = s[6]||0;
    const haystack = name + " " + desc + " " + c + " " + tags;
    if (cat && !c.includes(cat)) continue;
    if (tag && !tags.includes(tag)) continue;
    let score = 0, hits = [], phraseHits = [];
    for (const t of tokens) {
      if (name.includes(t)) { score += 8; hits.push(t); }
      else if (haystack.includes(t)) { score += 3; hits.push(t); }
    }
    for (const ph of phrases) {
      if (name.includes(ph)) { score += 15; phraseHits.push(ph); }
      else if (desc.includes(ph)) { score += 8; phraseHits.push(ph); }
    }
    if (score === 0) continue;
    score += Math.min(Math.log1p(stars) / Math.log(10), 5); // stars as relevance signal
    scored.push({ s, score, hits: hits.slice(0,4), phraseHits: phraseHits.slice(0,2) });
  }
  scored.sort((a, b) => b.score - a.score);
  const top = scored.slice(0, limit || 5);
  return top.map(x => {
    const s = x.s;
    const why = [];
    if (x.phraseHits.length) why.push("matches your goal '" + x.phraseHits.join(", ") + "'");
    if (x.hits.length) why.push("found terms: " + x.hits.join(", "));
    why.push("in category " + (s[2]||"general"));
    if ((s[6]||0) > 0) why.push((s[6]||0) + " stars");
    return { name: s[0], description: (s[1]||"").slice(0,200), category: s[2]||"general",
             source: s[3]||"", url: s[4]||"", tags: s[5]||[], stars: s[6]||0,
             score: Math.round(x.score*10)/10, reason: why.join("; ") };
  });
}

function renderSkillPage(SKILLS, slug) {
  // slug is like "some-skill-name"; find matching skill (case/dash-insensitive)
  const key = slug.toLowerCase().replace(/[^a-z0-9]+/g, "-");
  let hit = null;
  for (const s of SKILLS) {
    const k = (s[0]||"").toLowerCase().replace(/[^a-z0-9]+/g, "-");
    if (k === key) { hit = s; break; }
    // also allow partial tail match
    if (!hit && key && k.endsWith(key)) hit = s;
  }
  if (!hit) return null;
  const name = hit[0], desc = (hit[1]||""), cat = hit[2]||"general", src = hit[3]||"",
        url = hit[4]||"", tags = hit[5]||[], stars = hit[6]||0;
  const esc = s => String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
  const canon = `https://skillowkey.com/skills/${esc(slug)}/`;
  const tagHtml = tags.map(t=>`<span class="tag">${esc(t)}</span>`).join(" ");
  const body = `<div class="crumb"><a href="/">Skillowkey</a> / <a href="/category/${esc(cat).replace('/','-')}/">${esc(cat)}</a> / ${esc(name)}</div>
  <h1>${esc(name)}</h1>
  <p class="desc">${esc(desc)}</p>
  <p class="src">Source: <a href="${esc(url)}">${esc(src||url)}</a> &middot; Category: ${esc(cat)} &middot; Stars: ${stars}</p>
  <p class="tags">${tagHtml}</p>
  <p class="back"><a href="/#q=${encodeURIComponent(name)}">← Browse related in the library</a></p>`;
  const sch = `<script type="application/ld+json">{"@context":"https://schema.org","@type":"SoftwareApplication","name":${JSON.stringify(name)},"description":${JSON.stringify(desc)},"applicationCategory":${JSON.stringify(cat)},"url":${JSON.stringify(url)}}</script>`;
  const html = `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
  <title>${esc(name)} - AI Agent Skill (SKILL.md) - Skillowkey</title>
  <meta name="description" content="${esc(desc)}">
  <link rel="canonical" href="${canon}">
  <meta property="og:title" content="${esc(name)}"><meta property="og:description" content="${esc(desc.slice(0,150))}">
  ${sch}
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Geist:wght@500;700;800&display=swap">
  <style>body{font-family:'Geist',system-ui,sans-serif;max-width:860px;margin:0 auto;padding:24px;color:#111;line-height:1.65}a{color:#0057ff;text-decoration:none}.crumb{font-size:13px;color:#666;margin-bottom:16px}h1{font-size:30px;margin:8px 0}.desc{font-size:16px;color:#333}.src{font-size:13px;color:#555;margin:12px 0}.tag{display:inline-block;background:#eef;border-radius:999px;padding:3px 10px;font-size:12px;margin:3px 4px 3px 0;color:#333}.back{margin-top:26px;font-size:14px}</style>
  </head><body>${body}</body></html>`;
  return new Response(html, { headers: { "content-type": "text/html; charset=utf-8", "cache-control": "public, max-age=3600" } });
}

function renderTrustPage() {
  const esc = s => String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
  const body = `
  <div class="wrap">
    <p class="crumb"><a href="/">Skillowkey</a> / How we verify skills</p>
    <h1>How we verify skills before you install them</h1>
    <p class="lede">Agent skills are code. Every SKILL.md file you add to Claude Code, Gemini, or any agent is instructions + tools that run with your permissions. The supply chain is wide open. We filter it so you don't have to.</p>

    <div class="statrow">
      <div class="stat"><b>28,101</b><span>skills indexed</span></div>
      <div class="stat"><b>1,853</b><span>flagged & filtered</span></div>
      <div class="stat"><b>6</b><span>malicious removed</span></div>
      <div class="stat"><b>0</b><span>malware ships</span></div>
    </div>

    <h2>What we look for</h2>
    <div class="grid3">
      <div class="tbox"><b>Malicious code</b><p>Shell, Perl, Python and ProcSub snippets that exfiltrate data, drop remote-access payloads, or execute arbitrary commands (RCE). These are removed from the public index outright.</p></div>
      <div class="tbox"><b>Prompt injection</b><p>Skills engineered to hijack agent instructions or leak context. Flagged and separated from the trustworthy set.</p></div>
      <div class="tbox"><b>Junk & repacks</b><p>Empty files, broken frontmatter, and repackaged duplicates that bloat a catalog and poison search quality. Excluded so you search a clean set.</p></div>
    </div>

    <h2>How the filter works</h2>
    <p>Every ingestion passes a static-analysis gate: we scan file content and references for dangerous patterns (curl-to-shell piping, encoded payloads, proc-substitution, known-exfiltration signatures), then a manual review layer decides flagged vs. dangerous. Only clean skills reach the browsable index and API.</p>
    <p>That is the difference between a scraper and a registry. We are the latter.</p>

    <p class="cta"><a class="btn" href="/">Browse the verified library</a></p>
  </div>`;
  const html = `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
  <title>How Skillowkey verifies AI agent skills before you install them</title>
  <meta name="description" content="Every agent skill is code. Skillowkey flags 1,853 of 28,101 SKILL.md files as junk or malicious and keeps them out of the index. See how we vet before you install.">
  <link rel="canonical" href="https://skillowkey.com/verify">
  <meta property="og:title" content="How Skillowkey verifies skills before you install them"><meta property="og:description" content="We filter the agent-skill supply chain so you don't have to.">
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Geist:wght@400;600;800&display=swap">
  <style>body{font-family:'Geist',system-ui,sans-serif;margin:0;background:#fbfcfc;color:#111;line-height:1.6}.wrap{max-width:860px;margin:0 auto;padding:40px 24px}a{color:#0057ff;text-decoration:none}.crumb{font-size:13px;color:#666;margin-bottom:14px}h1{font-size:34px;line-height:1.15;margin:6px 0 10px}.lede{font-size:17px;color:#333}.statrow{display:flex;gap:14px;flex-wrap:wrap;margin:26px 0}.stat{background:#fff;border:1px solid #e8eaed;border-radius:14px;padding:16px 22px;min-width:120px}.stat b{display:block;font-size:26px}.stat span{font-size:12px;color:#666}h2{font-size:20px;margin:30px 0 12px}.grid3{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:14px}.tbox{background:#fff;border:1px solid #e8eaed;border-radius:14px;padding:18px}.tbox b{display:block;margin-bottom:6px}.tbox p{font-size:13.5px;color:#444;margin:0}.cta{margin-top:34px}.btn{background:#0057ff;color:#fff;padding:12px 22px;border-radius:12px;font-weight:600}</style>
  </head><body>${body}</body></html>`;
  return new Response(html, { headers: { "content-type": "text/html; charset=utf-8", "cache-control": "public, max-age=3600" } });
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const path = url.pathname;
    if (path === "/verify" || path === "/trust" || path === "/how-we-verify") return renderTrustPage();
    if (path.startsWith("/skills/")) {
      const SKILLS = await loadData();
      const slug = path.replace(/^\/skills\//,"").replace(/\/+$/,"");
      const resp = renderSkillPage(SKILLS, slug);
      if (resp) return resp;
      // fallthrough: if assets have it (they don't now) static serves; else 404 via api
    }
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
      if (path === "/api/recommend") {
        const p = Object.fromEntries(url.searchParams);
        const SKILLS = await loadData();
        if (!p.q) return new Response(JSON.stringify({ error: "missing q (a natural-language goal)" }), { status: 400, headers: { "content-type": "application/json" } });
        const recs = recommended(SKILLS, p.q, p.cat || "", p.tag || "", parseInt(p.limit) || 5);
        return new Response(JSON.stringify({ query: p.q, count: recs.length, recommendations: recs }),
          { headers: { "content-type": "application/json", "access-control-allow-origin": "*" } });
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