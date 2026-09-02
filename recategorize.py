#!/usr/bin/env python3
"""recategorize.py - Re-tag every skill into the new flat 8-category taxonomy:
agreement | seo | automation | api | transactional | tools | content | drafting
Keeps 'general' as fallback for unmatched. Also enriches with descriptive 1-word labels.
Idempotent: rewrites category field on each skill row.
"""
import json, re
from pathlib import Path
BASE = Path("/home/ubuntu/skillowkey-site")
DATA = BASE / "data" / "skills.json"

site = json.loads(DATA.read_text())

# Order matters: more specific first.
RULES = [
  ("agreement",   ["contract","legal","law","clause","compliance","regulation","nda","licens","policy","dispute","agreement","terms","jurisdiction","audit","governance","risk","insurance","privacy","gdpr","ethic"]),
  ("seo",         ["seo","backlink","keyword","serp","search engine","meta description","page rank","google search","index","rank","traffic","organic"]),
  ("api",         ["api","sdk","endpoint","graphql","integration","webhook","mcp","client","api key","interface","rest","federat","oauth","authentication","serialize","request","response"]),
  ("transactional",["sale","sell","checkout","payment","invoice","order","commerce","shopify","ecommerce","billing","pricing","revenue","cart","crm","lead","conversion","subscription","purchase","marketplace","wallet","pay","financ","accounting","tax","budget"]),
  ("automation",   ["automation","automate","workflow","pipeline","orchestrat","batch","cron","deploy","bot","repetitiv","process","ci","cd","devops","schedul","continuous"]),
  ("drafting",     ["draft","resume","cover letter","memo","report","proposal","essay","document","outline","summar","research","note","blueprint","writing","write","content plan","article","presentation","slide"]),
  ("content",      ["content","blog","social","email","newsletter","marketing","brand","youtube","video","podcast","image","creative","copywriter","story","caption","design","ui","ux","photo","marketing","growth","campaign"]),
  ("tools",        ["tool","utility","cli","command-line","manager","helper","convert","formatter","linter","scraper","extract","monitor","debug","test","fetch","cleanup","code","programming","python","javascript","typescript","frontend","backend","database","sql","server","cloud","terraform","k8s","docker","linux","security","vulnerab","password","malware","encrypt","network","app","application","software","system","data","model","pipeline engine","engineer","build","develop","implement","analy","metric","report gen","setup","install","config","deploy skill","api key","agent"]),
]

def cat_for(name, desc):
    d = (name + " " + desc).lower()
    for cat, kws in RULES:
        if any(k in d for k in kws):
            return cat
    return "general"

# count current to compare
from collections import Counter
before = Counter(x[2] for x in site)

changed = 0
for s in site:
    new = cat_for(s[0], s[1])
    if new != s[2]:
        s[2] = new
        changed += 1

DATA.write_text(json.dumps(site, ensure_ascii=False))
after = Counter(x[2] for x in site)
print("re-tagged", changed, "skills")
print("=== BEFORE ===")
for k, v in before.most_common(): print(f"  {k}: {v}")
print("=== AFTER ===")
for k, v in after.most_common(): print(f"  {k}: {v}")
print("total:", len(site))