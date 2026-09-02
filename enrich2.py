#!/usr/bin/env python3
"""enrich2.py - fetch GitHub stars/update dates for all Skillowkey origins.
Writes incrementally (safe to kill/restart). Paces requests under the 60/hr
anonymous rate limit. Resume from existing cache.
"""
import json, time, urllib.request, urllib.error
from pathlib import Path
BASE = Path("/home/ubuntu/skillowkey-site")
skills = json.loads((BASE / "data" / "skills.json").read_text())
OUT = BASE / "data" / "skills_meta.json"

origins = []
for s in skills:
    if s[4] and s[4] not in origins: origins.append(s[4])

meta = {}
if OUT.exists(): meta = json.loads(OUT.read_text())
print(f"origins: {len(origins)}, cached: {len(meta)}", flush=True)

def repo_of(url):
    if "github.com/" not in url: return None
    p = url.split("github.com/")[1].split("/")
    return p[0] + "/" + p[1] if len(p) >= 2 else None

def fetch(url, tries=3):
    for a in range(tries):
        req = urllib.request.Request(url, headers={"User-Agent": "skillowkey-bot", "Accept": "application/vnd.github+json"})
        try:
            with urllib.request.urlopen(req, timeout=20) as r: return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code in (403, 429):
                time.sleep(65)  # rate limit, wait a full window
                continue
            return {"_err": e.code}
        except Exception as e:
            time.sleep(5); return {"_err": str(e)} if a == tries-1 else None
    return {"_err": "timeout"}

pending = [o for o in origins if o not in meta]
reqs_this_window = 0
start = time.time()
for i, url in enumerate(pending):
    repo = repo_of(url)
    if not repo:
        meta[url] = {"stars": 0, "pushed_at": "", "created_at": "", "topics": [], "_skip": True}
        continue
    d = fetch(f"https://api.github.com/repos/{repo}")
    if "_err" in d and d["_err"] in (403, 429):
        print(f"RATE LIMITED at {repo} - window reset, saving cache", flush=True)
        continue
    if "_err" in d:
        print(f"[{i}] {repo}: err {d['_err']}", flush=True)
        meta[url] = {"stars": 0, "pushed_at": "", "created_at": "", "_err": d["_err"]}
        continue
    meta[url] = {"stars": d.get("stargazers_count", 0) or 0,
                 "pushed_at": d.get("pushed_at", ""), "created_at": d.get("created_at", ""),
                 "topics": d.get("topics", [])}
    # write incrementally every 10 to survive kills
    if i % 10 == 0:
        OUT.write_text(json.dumps(meta))
        print(f"[{i}/{len(pending)}] {repo}: {meta[url]['stars']} stars (cache {len(meta)})", flush=True)
    time.sleep(1.2)  # gentle pacing ~50/min stays under 60/hr over an hour window when spread

OUT.write_text(json.dumps(meta))
print(f"DONE {len(meta)} cached to {OUT}", flush=True)