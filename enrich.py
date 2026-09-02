#!/usr/bin/env python3
"""Enrich Skillowkey data with real GitHub metadata (stars, pushed_at, topics).
Fetches repo info for each unique origin, respecting anonymous rate limit (60/hr).
Writes data/skills_meta.json = {url: {stars, pushed_at, topics, archived}}.
Runs in background; guard against rate limits with backoff.
"""
import json, time, urllib.request, urllib.error
from pathlib import Path

BASE = Path("/home/ubuntu/skillowkey-site")
REPO_FILE = BASE / "data" / "skills.json"
OUT = BASE / "data" / "skills_meta.json"

skills = json.loads(REPO_FILE.read_text())
origins = []
for s in skills:
    u = s[4]
    if u and u not in origins:
        origins.append(u)
print(f"Total unique origins: {len(origins)}", flush=True)

# load existing cache to resume
meta = {}
if OUT.exists():
    meta = json.loads(OUT.read_text())
    print(f"Resuming with {len(meta)} cached", flush=True)

def repo_of(url):
    # https://github.com/owner/repo  -> owner/repo
    if "github.com/" not in url: return None
    parts = url.split("github.com/")[1].split("/")
    if len(parts) >= 2:
        return parts[0] + "/" + parts[1]
    return None

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "skillowkey-bot", "Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"_err": e.code}
    except Exception as e:
        return {"_err": str(e)}

pending = [o for o in origins if o not in meta]
print(f"To fetch ({len(pending)}):", flush=True)
for i, url in enumerate(pending):
    repo = repo_of(url)
    if not repo:
        meta[url] = {"stars": 0, "pushed_at": "", "topics": [], "archived": False, "_skip": True}
        continue
    d = fetch(f"https://api.github.com/repos/{repo}")
    if "_err" in d:
        print(f"[{i}/{len(pending)}] {repo}: ERR {d['_err']}", flush=True)
        if d["_err"] == 403 or d["_err"] == 429:
            print("Rate limited - waiting 60s", flush=True)
            time.sleep(60)
            d = fetch(f"https://api.github.com/repos/{repo}")
            if "_err" in d:
                meta[url] = {"stars": 0, "pushed_at": "", "topics": [], "archived": None, "_err": d["_err"]}
                continue
        else:
            meta[url] = {"stars": 0, "pushed_at": "", "topics": [], "archived": None, "_err": d["_err"]}
            continue
    meta[url] = {
        "stars": d.get("stargazers_count", 0),
        "pushed_at": d.get("pushed_at", ""),
        "created_at": d.get("created_at", ""),
        "updated_at": d.get("updated_at", ""),
        "topics": d.get("topics", []),
        "archived": d.get("archived", False),
        "fork": d.get("fork", False),
        "desc": d.get("description", ""),
    }
    print(f"[{i}/{len(pending)}] {repo}: {meta[url]['stars']} stars, pushed {meta[url]['pushed_at'][:10]}", flush=True)

OUT.write_text(json.dumps(meta))
print(f"\nDONE. Wrote {len(meta)} entries to {OUT}", flush=True)