#!/usr/bin/env python3
"""enrich3.py - fetch GitHub stars/update dates, robust to rate limits.
- Reads X-RateLimit-Remaining/Reset headers, sleeps precisely to the window reset.
- Writes cache after EVERY repo (killsafe, fully resumable).
- Logs progress unbuffered to /tmp/enrich3.log.
"""
import json, time, urllib.request, urllib.error, sys
from pathlib import Path
BASE = Path("/home/ubuntu/skillowkey-site")
OUT = BASE / "data" / "skills_meta.json"
LOG = open("/tmp/enrich3.log", "w", buffering=1)

def log(s):
    LOG.write(f"[{time.strftime('%H:%M:%S')}] {s}\n"); LOG.flush()

skills = json.loads((BASE / "data" / "skills.json").read_text())
origins = []
for s in skills:
    if s[4] and s[4] not in origins: origins.append(s[4])
meta = {}
if OUT.exists():
    try: meta = json.loads(OUT.read_text())
    except Exception: meta = {}
log(f"origins={len(origins)} cached={len(meta)}")
pending = [o for o in origins if o not in meta]

def repo_of(url):
    if "github.com/" not in url: return None
    p = url.split("github.com/")[1].split("/")
    return (p[0] + "/" + p[1]) if len(p) >= 2 else None

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "skillowkey-bot", "Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            hdrs = dict(r.headers)
            return json.loads(r.read()), hdrs
    except urllib.error.HTTPError as e:
        return {"_err": e.code}, dict(e.headers)
    except Exception as e:
        return {"_err": str(e)}, {}

for i, url in enumerate(pending):
    repo = repo_of(url)
    if not repo:
        meta[url] = {"stars": 0, "pushed_at": "", "created_at": "", "_skip": True}
        continue
    d, hdrs = fetch(f"https://api.github.com/repos/{repo}")
    if "_err" in d and d["_err"] in (403, 429):
        reset = int(hdrs.get("X-RateLimit-Reset") or 0)
        remaining = hdrs.get("X-RateLimit-Remaining", "?")
        if reset:
            wait = reset - int(time.time()) + 1
            if wait > 0 and wait < 3600:
                log(f"[{i}/{len(pending)}] {repo}: rate-limited (rem {remaining}), sleeping {wait}s to reset")
                time.sleep(wait)
                d, hdrs = fetch(f"https://api.github.com/repos/{repo}")
                if "_err" in d and d["_err"] in (403, 429):
                    meta[url] = {"stars": 0, "pushed_at": "", "created_at": "", "_err": d["_err"]}
                    OUT.write_text(json.dumps(meta)); continue
            else:
                # no usable reset header - store skip to avoid infinite loop
                meta[url] = {"stars": 0, "pushed_at": "", "created_at": "", "_err": d["_err"]}
                OUT.write_text(json.dumps(meta)); continue
    if "_err" in d:
        log(f"[{i}/{len(pending)}] {repo}: err {d['_err']}")
        meta[url] = {"stars": 0, "pushed_at": "", "created_at": "", "_err": d["_err"]}
    else:
        meta[url] = {"stars": d.get("stargazers_count", 0) or 0,
                     "pushed_at": d.get("pushed_at", ""),
                     "created_at": d.get("created_at", ""),
                     "topics": d.get("topics", [])}
        log(f"[{i}/{len(pending)}] {repo}: {meta[url]['stars']} stars pushed {meta[url]['pushed_at'][:10]}")
    OUT.write_text(json.dumps(meta))  # every repo
    time.sleep(1.0)

log(f"DONE cached={len(meta)} to {OUT}")
LOG.flush(); LOG.close()