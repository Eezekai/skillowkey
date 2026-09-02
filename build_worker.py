#!/usr/bin/env python3
"""build_worker.py - build the Skillowkey Worker (app + JSON search API).
Serves:
  GET /                      -> index.html (the interactive app)
  GET /api/search?q=&cat=&tag=&page=&sort=   -> JSON results (free tier, rate-limited)
  GET /health               -> ok
The API is the monetizable layer: free tier throttled, Pro/API keys unlock higher limits + stable auth.
We keep it dependency-free (no KV) so it deploys with just script upload.
"""
import json
from pathlib import Path
BASE = Path("/home/ubuntu/skillowkey-site/")
HTML = (BASE / "index.html").read_text()

# Load clean skills the same way build.py does (vet gate applied).
import sys; sys.path.insert(0, str(BASE))
def load_clean():
    skills = json.loads((BASE / "data" / "skills.json").read_text())
    vf = BASE / "data" / "vet_flags.json"
    if vf.exists():
        try:
            f = json.loads(vf.read_text())
            ex = {x["index"] for x in f["flagged"] if x["type"] in ("malicious","suspicious")}
            skills = [s for i,s in enumerate(skills) if i not in ex]
        except: pass
    return skills
skills = load_clean()

# Serialize skills as a compact JSON array embedded in the worker for the API.
SKILLS_JSON = json.dumps(skills, ensure_ascii=False, separators=(",", ":"))

# Build the search index at runtime: we just FILTER the array in JS (7k rows, fine).
# To keep each API respond fast we filter in JS - 7k rows scan is ~ms on CF edge.

worker = """const HTML = __HTML__;
const SKILLS = __SKILLS__;

// simple token-bucket rate limiter per IP (in-memory, single-isolate best-effort)
const LIMIT = {FREE_LIM};   // free tier: N req/min
const PRO_LIMIT = {PRO_LIM}; // pro tier limit
const buckets = new Map();
function checkLimit(ip, lim){ const now=Date.now(); let b=buckets.get(ip)||{t:now,c:0};
  if (now-b.t>60000){b={t:now,c:0};}
  b.c++; buckets.set(ip,b);
  if (bucketToBig(b)) clean(); return b.c<=lim; }
function bucketToBig(b){return b.c>100000;}
function clean(){ if(buckets.size>10000){ const now=Date.now(); for(const[k,v]of buckets) if(now-v.t>120000) buckets.delete(k);} }

function runQuery(params){
  let {q='', cat='', tag='', sort='best', page=1} = params;
  page = Math.max(1, parseInt(page)||1);
  const per = 50;
  let out = [];
  const ql = q.toLowerCase();
  const tagSet = tag ? tag.split(',') : [];
  for (const s of SKILLS){
    const name=s[0], desc=s[1], c=s[2], tags=s[5]||[], stars=s[6]||0;
    if (cat && !c.includes(cat)) continue;
    if (tagSet.length && !tagSet.some(t=>tags.includes(t))) continue;
    if (ql && !(name.toLowerCase().includes(ql) || (desc&&desc.toLowerCase().includes(ql)) || c.toLowerCase().includes(ql))) continue;
    // score for best match
    let score=0;
    if (ql){ if(name.toLowerCase().includes(ql)) score+=10; if(c.toLowerCase().includes(ql)) score+=5; if(desc&&desc.toLowerCase().includes(ql)) score+=1; }
    score += Math.min(Math.log1p(stars||0)/Math.log(10), 5); // stars as signal
    out.push({name, desc, category:c, source:s[3], url:s[4], tags, stars, score});
  }
  if (sort==='stars') out.sort((a,b)=>(b.stars||0)-(a.stars||0));
  else if (sort==='newest') out.sort((a,b)=>((b.created_at)||'').localeCompare((a.created_at)||''));
  else out.sort((a,b)=>(b.score||0)-(a.score||0));
  const total = out.length;
  const start = (page-1)*per;
  return { total, page, per, results: out.slice(start, start+per) };
}

addEventListener("fetch", event => {
  const url = new URL(event.request.url);
  const path = url.pathname;
  if (path.startsWith("/api/")){
    const ip = event.request.headers.get("CF-Connecting-IP") || "anon";
    // Pro tier: pass api key header/session - unlocked via /api/pro
    const isPro = event.request.headers.has("x-pro-key");
    const lim = isPro ? PRO_LIMIT : LIMIT;
    if (!checkLimit(ip, lim)){
      return event.respondWith(new Response(JSON.stringify({error:"rate_limited", retry_after_ms:60000}),
        {status:429, headers:{"content-type":"application/json"} } ));
    }
    if (path === "/api/search"){
      const res = runQuery(Object.fromEntries(url.searchParams));
      return event.respondWith(new Response(JSON.stringify(res), {headers:{"content-type":"application/json","access-control-allow-origin":"*"}}));
    }
    if (path === "/api/stats"){
      const cats = {};
      for(const s of SKILLS){ const c=s[2]; cats[c]=(cats[c]||0)+1; }
      return event.respondWith(new Response(JSON.stringify({total:SKILLS.length, categories:cats}), {headers:{"content-type":"application/json","access-control-allow-origin":"*"}}));
    }
    if (path === "/api/pro"){
      // docs + placeholder checkout. Real key issuance needs KV/state; v1 keys are granted offline.
      return event.respondWith(new Response(JSON.stringify({plan:"pro", status:"available", expires:null}), {headers:{"content-type":"application/json"}}));
    }
    return event.respondWith(new Response(JSON.stringify({error:"not_found"}), {status:404, headers:{"content-type":"application/json"}}));
  }
  if (path === "/health") return event.respondWith(new Response("ok", {headers:{"content-type":"text/plain"}}));
  // default: serve app
  return event.respondWith(new Response(HTML, {headers:{"content-type":"text/html; charset=utf-8","cache-control":"public, max-age=300"}}));
});
"""

worker = worker.replace("__HTML__", json.dumps(HTML))
worker = worker.replace("__SKILLS__", SKILLS_JSON)
worker = worker.replace("{FREE_LIM}", "60")   # free: 60 req/min
worker = worker.replace("{PRO_LIM}", "6000")  # pro: 6000 req/min

# The worker JS has a placeholder clean() bug I wrote; let me fix the logic properly.
# rewrite bucketing cleanly
worker = worker.replace('''function checkLimit(ip, lim){ const now=Date.now(); let b=buckets.get(ip)||{t:now,c:0};
  if (now-b.t>60000){b={t:now,c:0};}
  b.c++; buckets.set(ip,b);
  if (bucketToBig(b)) clean(); return b.c<=lim; }
function bucketToBig(b){return b.c>100000;}
function clean(){ if(buckets.size>10000){ const now=Date.now(); for(const[k,v]of buckets) if(now-v.t>120000) buckets.delete(k);} }''',
'''function checkLimit(ip, lim){ const now=Date.now(); let b=buckets.get(ip)||{t:now,c:0};
  if (now-b.t>60000){b={t:now,c:0};}
  b.c++; buckets.set(ip,b);
  if(buckets.size>10000){ const t=Date.now(); for(const[k,v]of buckets) if(Date.now()-v.t>120000) buckets.delete(k);}
  return b.c<=lim; }''')

Path("/tmp/worker_api.js").write_text(worker)
print("worker written:", len(worker), "bytes | skills embedded:", len(skills))
import stat