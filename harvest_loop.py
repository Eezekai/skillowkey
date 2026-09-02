#!/usr/bin/env python3
"""harvest_loop.py - Autonomous continuous skill harvester for Skillowkey.

DISCOVERY -> DOWNLOAD -> INGEST -> TRACK, on a loop.

Sources (highest-value first):
  1. GitHub search: repos with topic:claude-skills / agent-skills / SKILL.md, sorted by recently updated => finds NEW repos forever
  2. Watchlist: known expert/org skill publishers (Anthropic, OpenAI, etc.)
  3. Awesome-list follow: repos tracked in awesome-claude-code-style lists

Mechanics:
  - Every repo: git clone (shallow) -> find *_SKILL.md / SKILL.md files -> parse frontmatter
  - Dedupe by (repo, skill-name) against data/skills.json
  - Rate-limit aware: reads X-RateLimit headers, sleeps on reset
  - Persists a seen-scan log so it resumes where it left off and doesn't re-clone

Usage (background):  python3 harvest_loop.py [--discover-only N] [--once]
Env: GITHUB_TOKEN from git remote (auto-detected)
"""
import json, os, re, subprocess, time, sys, urllib.request, urllib.error, pathlib
from pathlib import Path

BASE = pathlib.Path("/home/ubuntu/skillowkey-site")
DATA = BASE / "data" / "skills.json"
STATE = BASE / "data" / "harvest_state.json"
SCRATCH = pathlib.Path("/tmp/skillharvest_live")
SCRATCH.mkdir(exist_ok=True)
LOG = open("/tmp/harvest_loop.log", "w", buffering=1)

def log(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    LOG.write(f"[{time.strftime('%H:%M:%S')}] {s}\n"); LOG.flush()

# --- auth token from git remote ---
def get_token():
    r = subprocess.run(["git","-C",str(BASE),"remote","-v"], capture_output=True, text=True)
    m = re.search(r"x-access-token[:=]([A-Za-z0-9_]+)", r.stdout)
    return m.group(1) if m else os.environ.get("GITHUB_TOKEN","")

TOKEN = get_token()
HDRS = {"Accept":"application/vnd.github+json"}
if TOKEN: HDRS["Authorization"] = f"Bearer {TOKEN}"
log("token:", "yes" if TOKEN else "NO (anonymous, 60/hr limit)")

def api_get(url, retries=3):
    for a in range(retries):
        req = urllib.request.Request(url, headers=HDRS)
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            rem = e.headers.get("X-RateLimit-Remaining")
            if e.code in (403, 429):
                reset = int(e.headers.get("X-RateLimit-Reset") or 0)
                wait = reset - int(time.time()) + 1 if reset else 60
                log("rate-limited, sleeping", wait, "s")
                time.sleep(wait)
                continue
            return {"_err": e.code}
        except Exception as e:
            time.sleep(4); 
            if a == retries-1: return {"_err": str(e)}
    return {"_err":"fail"}

def load_state():
    if STATE.exists():
        try: return json.loads(STATE.read_text())
        except: return {}
    return {"scanned": [], "ongoing": {}}
def save_state(st):
    STATE.write_text(json.dumps(st))

# --- discovery ---
def discover_repos(sort="updated", per_page=30, page=1, query="topic:claude-skills OR filename:SKILL.md"):
    d = api_get(f"https://api.github.com/search/repositories?q={urllib.parse.quote(query)}&sort={sort}&order=desc&per_page={per_page}&page={page}")
    if "_err" in d or "items" not in d: return []
    return d["items"]

WATCHLIST = [
    "anthropics/skills","anthropics/claude-code","openai/skills","microsoft/skills",
    "cloudflare/skills","vercel-labs/skills","vercel-labs/ai-sdk","composiohq/composio",
    "huggingface/skills","obra/superpowers","trailofbits/skills","flutter/skills",
    "firecrawl/firecrawl","browserbase/skills","qdrant/skills","getsentry/skills",
    "replicate/skills","fal-ai-community/skills","cognition-labs/skills","anysphere/skills",
]

from urllib.parse import quote, quote_plus
def discover_watchlist():
    out=[]
    for repo in WATCHLIST:
        d = api_get(f"https://api.github.com/repos/{repo}")
        if "_err" not in d:
            out.append(d)
    return out

# --- download ---
def clone_repo(full_name, into):
    target = into / full_name.replace("/","__")
    if target.exists(): return target
    subprocess.run(["git","clone","--depth","1","-q",f"https://github.com/{full_name}.git", str(target)],
                   capture_output=True, timeout=120)
    return target if target.exists() else None

# --- ingest ---
def parse_skill(path):
    txt = path.read_text(errors="ignore")
    m = re.match(r"^---\s*\n(.*?)\n---", txt, re.S)
    fm={}
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k,v=line.split(":",1); fm[k.strip().lower()]=v.strip().strip('"')
    name=fm.get("name") or path.stem.replace("_SKILL","").replace("_"," ").strip()
    desc=fm.get("description") or ""
    desc=re.sub(r"\s+"," ",desc).strip()[:160]
    tg=[]
    if "tags" in fm: tg=[t.strip() for t in fm["tags"].split(",") if t.strip()]
    return name,desc,tg

def categorize(name,desc):
    d=(name+desc).lower()
    rules=[(["python","typescript","sdk","api","codex","coder","npm","javascript","go ",".net"],"coding/dev"),
           (["security","threat","auth","vuln","audit","malware","secure"],"security"),
           (["market","seo","content","social","email","ads","brand","cmo","growth"],"market/product"),
           (["financ","tax","account","budget","cfo","invoice"],"finance/account"),
           (["design","ui","ux","figma","frontend","image","creative","video","slide"],"design/creative"),
           (["data","ml","ai","model","pipeline","analytics","dataset"],"data/ai"),
           (["music","audio","podcast"],"music/video"),
           (["legal","law","contract","compliance"],"legal"),
           (["write","research","summar","doc"],"writing/edu"),
           (["ops","automation","deploy","ci","workflow","monitor","cloud","admin"],"ops/automation")]
    for tg,cat in rules:
        if any(t in d for t in tg): return cat
    return "general"

def ingest_repo(full_name, repo_dir, site, names, src_url=None):
    src_url = src_url or f"https://github.com/{full_name}"
    files=[]
    for pat in ("**/*_SKILL.md","**/SKILL.md","**/*_SKILL.MD","**/SKILL.MD"):
        files += list(repo_dir.glob(pat))
    files=sorted(set(files))
    added=0
    for f in files:
        name,desc,tg=parse_skill(f)
        if not name or name.lower() in names: continue
        cat=categorize(name,desc)
        site.append([name,desc,cat,full_name,src_url,tg if tg else [cat.split("/")[0]],0,"",""])
        names.add(name.lower()); added+=1
    return added

# --- main loop ---
def run_cycle(site, names, st, mode="discover"):
    new_repos=[]
    # 1. watchlist first (highest value)
    if mode in ("discover","watch"):
        wl=discover_watchlist()
        for d in wl:
            fn=d["full_name"]
            if fn not in st["scanned"]:
                new_repos.append((fn, d.get("stargazers_count",0)))
        log(f"watchlist: {len(wl)} repos, {len([r for r in new_repos if r[0] in {x['full_name'] for x in wl}])} new to scan")
    # 2. search discovery
    for page in (1,2):
        items=discover_repos(page=page)
        for it in items:
            fn=it["full_name"]
            if fn not in st["scanned"] and fn not in [r[0] for r in new_repos]:
                new_repos.append((fn, it.get("stargazers_count",0)))
        if mode=="once": break
    log(f"discovery: {len(new_repos)} new repos to harvest")
    t_added=0
    new_scanned=0
    for fn,stars in new_repos:
        target=clone_repo(fn, SCRATCH)
        if target:
            a=ingest_repo(fn,target,site,names)
            if a: 
                t_added+=a
                log(f"  {fn}: +{a} skills")
            st["scanned"].append(fn)
            new_scanned+=1
        # commit incrementally
        save_state(st)
        time.sleep(0.8)
    return t_added, new_scanned

if __name__=="__main__":
    once = "--once" in sys.argv
    mode = "--discover-only" in sys.argv and "discover" or "discover"
    site = json.loads(DATA.read_text())
    names = {x[0].lower() for x in site}
    st = load_state()
    log(f"start: {len(site)} skills, {len(names)} names, scanned {len(st['scanned'])} repos")
    cycles = 1 if once else 0
    while cycles==1 or (not once):
        try:
            t,ns = run_cycle(site, names, st, mode)
            DATA.write_text(json.dumps(site, ensure_ascii=False))
            log(f"cycle done: +{t} skills, +{ns} repos scanned. total {len(site)}")
            save_state(st)
        except Exception as e:
            log("ERROR in cycle:", e)
            DATA.write_text(json.dumps(site, ensure_ascii=False))
        if once: break
        # wait between cycles (search API 30/hr => every ~2 min for 1 discovery, but be gentle)
        log("sleeping 120s before next discovery cycle")
        time.sleep(120)
    log("done")