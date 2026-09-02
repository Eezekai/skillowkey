#!/usr/bin/env python3
"""harvest_gitrepos.py - Clone + ingest a discovered repo list into Skillowkey
Loops /tmp/new_repos.json (full names), clones shallow, extracts SKILL.md files.
"""
import json, re, time, pathlib, subprocess, sys
from pathlib import Path
BASE = pathlib.Path("/home/ubuntu/skillowkey-site")
DATA = BASE / "data" / "skills.json"
SCRATCH = pathlib.Path("/tmp/skillharvest_more")
SCRATCH.mkdir(exist_ok=True)

site = json.loads(DATA.read_text())
names = {x[0].lower() for x in site}
srcs = set(x[4].lower().rstrip("/") for x in site)

def parse_skill(path):
    if not path.is_file():  # guard: broken symlink / dir-only node in glob
        return None, "", []
    txt = path.read_text(errors="ignore")
    m = re.match(r"^---\s*\n(.*?)\n---", txt, re.S)
    fm={}
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k,v=line.split(":",1); fm[k.strip().lower()]=v.strip().strip('"')
    name=fm.get("name") or path.stem.replace("_SKILL","").replace("_"," ").strip()
    desc=fm.get("description") or fm.get("title") or ""
    desc=re.sub(r"\s+"," ",desc).strip()[:160]
    tg=[]
    if "tags" in fm: tg=[t.strip() for t in fm["tags"].split(",") if t.strip()]
    if "category" in fm and fm["category"].strip() not in tg: tg.append(fm["category"].strip())
    return name,desc,tg

def categorize(name,desc):
    d=(name+desc).lower()
    RULES=[("agreement",["contract","legal","law","clause","compliance","regulation","nda","licens","policy","dispute","agreement","terms","jurisdiction","audit","governance","risk","insurance","privacy","gdpr","ethic"]),
           ("seo",["seo","backlink","keyword","serp","search engine","meta description","page rank","google search","index","rank","traffic","organic"]),
           ("api",["api","sdk","endpoint","graphql","integration","webhook","mcp","client","api key","interface","rest","federat","oauth","authentication","serialize","request","response"]),
           ("transactional",["sale","sell","checkout","payment","invoice","order","commerce","shopify","ecommerce","billing","pricing","revenue","cart","crm","lead","conversion","subscription","purchase","marketplace","wallet","pay","financ","accounting","tax","budget"]),
           ("automation",["automation","automate","workflow","pipeline","orchestrat","batch","cron","deploy","bot","repetitiv","process","ci","cd","devops","schedul","continuous"]),
           ("drafting",["draft","resume","cover letter","memo","report","proposal","essay","document","outline","summar","research","note","blueprint","writing","write","content plan","article","presentation","slide"]),
           ("content",["content","blog","social","email","newsletter","marketing","brand","youtube","video","podcast","image","creative","copywriter","story","caption","design","ui","ux","photo","growth","campaign"]),
           ("tools",["tool","utility","cli","command-line","manager","helper","convert","formatter","linter","scraper","extract","monitor","debug","test","fetch","cleanup","code","programming","python","javascript","typescript","frontend","backend","database","sql","server","cloud","terraform","k8s","docker","linux","security","vulnerab","password","malware","encrypt","network","app","application","software","system","data","model","engineer","build","develop","implement","analy","metric","setup","install","config","agent"])]
    for tg,cat in RULES:
        if any(t in d for t in tg): return cat
    return "general"

def ingest_repo(fn, repo_dir):
    src_url = f"https://github.com/{fn}"
    kl = src_url.lower()
    files=[]
    for pat in ("**/*_SKILL.md","**/SKILL.md","**/*_SKILL.MD","**/SKILL.MD","**/skills/**/*.md"):
        files += list(repo_dir.glob(pat))
    files=sorted(set(files))
    added=0
    for f in files:
        name,desc,tg=parse_skill(f)
        if not name or name.lower() in names: continue
        if not desc: continue
        cat=categorize(name,desc)
        tg=[t for t in tg if t]
        site.append([name,desc,cat,fn,src_url,tg if tg else [cat.split("/")[0]],0,"",""])
        names.add(name.lower()); added+=1
    return added

repos = json.loads(Path("/tmp/new_repos.json").read_text())
skip = set()
# skip repos we already have as source
already = {x[4].lower().rstrip("/").replace("https://github.com/","") for x in site}
candidates = []
for fn in repos:
    fnl = fn.lower().rstrip("/")
    if fnl in already: continue
    candidates.append(fn)

total_added=0
done=0
for fn in candidates:
    target = SCRATCH / fn.replace("/","__")
    if target.exists():
        # clear for fresh
        try: subprocess.run(["rm","-rf",str(target)],capture_output=True,timeout=30); 
        except: pass
    try:
        r = subprocess.run(["git","clone","--depth","1","-q",f"https://github.com/{fn}.git",str(target)],
                           capture_output=True,timeout=90)
    except Exception as e:
        print(f"  clone timeout/fail {fn}: {e}")
        try: subprocess.run(["rm","-rf",str(target)],capture_output=True,timeout=20)
        except: pass
        continue
    if target.exists():
        a = ingest_repo(fn, target)
        if a: total_added += a
    done+=1
    if done%5==0:
        DATA.write_text(json.dumps(site, ensure_ascii=False))
        print(f"  {done}/{len(candidates)}: +{total_added} (total {len(site)})", flush=True)
    # tidy
    try: subprocess.run(["rm","-rf",str(target)],capture_output=True,timeout=30)
    except: pass

DATA.write_text(json.dumps(site, ensure_ascii=False))
print(f"DONE: scanned {done} repos, added {total_added} skills. TOTAL {len(site)}")