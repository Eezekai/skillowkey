#!/usr/bin/env python3
"""build.py - generate index.html from template.html + skills.json + skills_meta.json.
Data row: [name, desc, category, source, url, [tags], stars, pushed_at, created_at]
Merges stars/pushed/created from skills_meta.json (keyed by url).
"""
import json, re, collections
from pathlib import Path
BASE = Path("/home/ubuntu/skillowkey-site/")
TPL = (BASE / "template.html").read_text()
skills = json.loads((BASE / "data" / "skills.json").read_text())

# --- vet gate: exclude dangerous/suspicious from the app too ---
def load_exclude():
    vf = BASE / "data" / "vet_flags.json"
    if vf.exists():
        try:
            f = json.loads(vf.read_text())
            return {x["index"] for x in f["flagged"] if x["type"] == "malicious"}
        except: pass
    return set()
EXCLUDE = load_exclude()
if EXCLUDE:
    print(f"EXCLUDING {len(EXCLUDE)} dangerous/suspicious skills")
    skills = [s for i, s in enumerate(skills) if i not in EXCLUDE]
meta = {}
mp = BASE / "data" / "skills_meta.json"
if mp.exists():
    meta = json.loads(mp.read_text())
    print(f"Using {len(meta)} enriched repo entries")

# build merged rows [name, desc, cat, src, url, tags, stars, pushed, created]
rows = []
for s in skills:
    name, desc, cat, src, url = s[0], s[1], s[2], s[3], s[4]
    tags = s[5] if len(s) > 5 else []
    m = meta.get(url, {})
    stars = m.get("stars", 0) or 0
    if stars == 0 and m.get("_err"):
        stars = 0
    pushed = m.get("pushed_at", "") or ""
    created = m.get("created_at", "") or ""
    rows.append([name, desc, cat, src, url, tags, stars, pushed, created])

# categories with counts from current data
cats = collections.OrderedDict()
for r in rows:
    c = r[2]
    if c not in cats: cats[c] = {"id": c, "label": c, "emoji": "●", "color": "#0AF77A", "n": 0}
    cats[c]["n"] += 1
# prettier labels
def beautify(cid):
    return cid.replace("/", " & ").replace("-", " ").title()
for c in cats.values():
    c["label"] = beautify(c["id"])
# color palette per category index
palette = ["#64d3ff","#ff4dd5","#0AF77A","#c1f32b","#f59e0b","#8b5cf6","#ef4444","#0ea5e9","#10b981","#f43f5e","#84cc16","#3b82f6","#fb7185"]
for i, c in enumerate(cats.values()):
    c["color"] = palette[i % len(palette)]

# tags: collect all, ranked by frequency, top 20
tagcount = collections.Counter()
for r in rows:
    for t in r[5]: tagcount[t] += 1
tags_list = [t for t, _ in tagcount.most_common(24)]

out = TPL
def inject(token, value):
    global out
    assert token in out, f"token missing: {token}"
    out = out.replace(token, value, 1)

inject("var SKILLS = [];", "var SKILLS = " + json.dumps(rows, ensure_ascii=False) + ";")
inject("var CATS = [];", "var CATS = " + json.dumps(list(cats.values()), ensure_ascii=False) + ";")
inject("var TAGS = [];", "var TAGS = " + json.dumps(tags_list, ensure_ascii=False) + ";")
# update meta description count
out = out.replace("<meta name=\"description\" content=\"A curated, searchable library of ready-to-use AI agent skills.",
                  f"<meta name=\"description\" content=\"A curated, searchable library of {len(rows)} ready-to-use AI agent skills.")

(BASE / "index.html").write_text(out)
print(f"Wrote index.html: {len(out)} bytes, {len(rows)} rows, {len(cats)} cats, {len(tags_list)} tags")