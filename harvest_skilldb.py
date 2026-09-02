#!/usr/bin/env python3
"""harvest_skilldb.py - systematically harvest ALL skilldb repos not yet in site data.
Finds _SKILL.md / SKILL.md / _SKILL.md variants, parses frontmatter, dedupes.
Writes additional rows, then rebuilds.
"""
import json, re, os, glob, pathlib, collections
DATA = pathlib.Path("/home/ubuntu/skillowkey-site/data/skills.json")
DB = "/home/ubuntu/skilldb"

site = json.loads(DATA.read_text())
def norm(u):
    u = u.replace("https://","").replace("http://","").rstrip("/")
    if u.startswith("github.com/"):
        p = u.split("github.com/")[1].split("/")
        return (p[0]+"/"+p[1]).lower()
    return u.lower()
site_series = {norm(x[4]) for x in site}
site_names = {x[0].lower() for x in site}

dirs = sorted(os.path.basename(p) for p in glob.glob(DB+"/*") if os.path.isdir(p))
missing = []
for d in dirs:
    if "__" in d:
        o,r = d.split("__",1)
        if (o+"/"+r).lower() not in site_series:
            missing.append(d)

print(f"{len(missing)} skilldb repos to harvest", flush=True)

def parse_skill(path):
    txt = path.read_text(errors="ignore")
    m = re.match(r"^---\s*\n(.*?)\n---", txt, re.S)
    fm = {}
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k,v = line.split(":",1)
                fm[k.strip().lower()] = v.strip().strip('"')
    name = fm.get("name") or ""
    desc = fm.get("description") or ""
    desc = re.sub(r"\s+"," ",desc).strip()
    if len(desc) > 160: desc = desc[:160]
    tg = []
    if "tags" in fm: tg=[t.strip() for t in fm["tags"].split(",") if t.strip()]
    return name, desc, tg

def categorize(name, desc):
    d = (name+" "+desc).lower()
    rules = [
        (["python","typescript","sdk","api","codex","coder","npm","javascript",".net","go ","java","graphql"], "coding/dev"),
        (["security","threat","auth","vuln","audit","malware","secure","token"], "security"),
        (["market","seo","content","social","email","ads","brand","cmo","growth"], "market/product"),
        (["financ","tax","account","budget","cfo","invoice","revenue"], "finance/account"),
        (["design","ui","ux","figma","frontend","image","creative","video","slide"], "design/creative"),
        (["data","ml","ai","model","pipeline","analytics","huggingface","dataset"], "data/ai"),
        (["music","audio","podcast"], "music/video"),
        (["legal","law","contract","compliance","regulat"], "legal"),
        (["write","doc","research","summar","essay","blog"], "writing/edu"),
        (["ops","automation","deploy","ci","workflow","monitor","admin","cloud"], "ops/automation"),
    ]
    for tags, cat in rules:
        if any(t in d for t in tags): return cat
    return "general"

added_total = 0
repos_added = []
for d in missing:
    base = pathlib.Path(DB) / d
    o, r = d.split("__",1)
    repo_url = f"https://github.com/{o}/{r}"
    src = f"{o}/{r}"
    # collect skill files: *SKILL.md or SKILL.md
    files = []
    for pat in ("**/*_SKILL.md","**/SKILL.md","**/*_SKILL.MD","**/SKILL.MD"):
        files += glob.glob(str(base)+"/"+pat, recursive=True)
    # dedupe paths
    files = sorted(set(files))
    added_repo = 0
    for f in files:
        p = pathlib.Path(f)
        name, desc, tg = parse_skill(p)
        if not name:
            # derive from relative path
            rel = str(p.relative_to(base))
            name = os.path.basename(rel).replace("_SKILL.md","").replace("SKILL.md","").replace("_"," ")
        name = name.strip()
        if not name or name.lower() in site_names:
            continue
        cat = categorize(name, desc)
        row = [name, desc, cat, src, repo_url, tg if tg else [cat.split("/")[0]]]
        site.append(row)
        site_names.add(name.lower())
        added_repo += 1
    if added_repo:
        repos_added.append((d, added_repo))
        added_total += added_repo
    print(f"{d}: +{added_repo}", flush=True)

DATA.write_text(json.dumps(site, ensure_ascii=False))
print(f"\nTOTAL ADDED from {len(repos_added)} repos: {added_total}")
print(f"NEW TOTAL: {len(site)} skills")