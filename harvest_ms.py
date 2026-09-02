#!/usr/bin/env python3
"""harvest_ms.py - Extract skills from the extracted microsoft/skills repo and
append to data/skills.json (de-duped against existing entries).

Source: /home/ubuntu/skillharvest/ms_extract/skills-main/.github/skills
Repo: github.com/microsoft/skills
Output format: [name, description, category('general' fallback), source, url, [tags]]
"""
import json, re, pathlib, collections
BASE = pathlib.Path("/home/ubuntu/skillharvest/ms_extract/skills-main/.github/skills")
DATA = pathlib.Path("/home/ubuntu/skillowkey-site/data/skills.json")
REPO_URL = "https://github.com/microsoft/skills"

existing = json.loads(DATA.read_text())
existing_names = {(x[0].lower()) for x in existing}
existing_urls = {x[4] for x in existing}

def parse_skill(md_path, rel):
    txt = md_path.read_text(errors="ignore")
    # frontmatter
    m = re.match(r"^---\s*\n(.*?)\n---", txt, re.S)
    fm = {}
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                fm[k.strip().lower()] = v.strip().strip('"')
    name = fm.get("name") or rel
    desc = fm.get("description") or ""
    # clean desc
    desc = re.sub(r"\s+", " ", desc).strip()
    if len(desc) > 140: desc = desc[:140]
    # tags from frontmatter 'tags'
    tg = []
    if "tags" in fm:
        tg = [t.strip() for t in fm["tags"].split(",") if t.strip()]
    return name, desc, tg

def categorize(name, desc):
    d = (name + " " + desc).lower()
    rules = [
        (["python", "typescript", "sdk", "api", "codex", "coder", "npm", "go ", "javascript", ".net", "sdk"], "coding/dev"),
        (["security", "threat", "auth", "vuln", "entra", "keyvault", "audit"], "security"),
        (["market", "seo", "content", "social", "email", "ads", "brand"], "market/product"),
        (["financ", "tax", "account", "budget", "cfo", "invoice"], "finance/account"),
        (["design", "ui", "ux", "figma", "frontend", "image", "creative", "video"], "design/creative"),
        (["data", "ml", "ai", "model", "pipeline", "analytics"], "data/ai"),
        (["music", "audio", "podcast"], "music/video"),
        (["legal", "law", "contract", "compliance", "regulat"], "legal"),
        (["write", "doc", "research", "summar"], "writing/edu"),
        (["ops", "automation", "deploy", "ci", "workflow", "monitor", "admin"], "ops/automation"),
    ]
    for tags, cat in rules:
        if any(t in d for t in tags):
            return cat
    return "general"

added = 0
new_rows = []
for md in sorted(BASE.rglob("SKILL.md")):
    rel = str(md.relative_to(BASE))
    name, desc, tg = parse_skill(md, rel)
    if not name or name.lower() in existing_names:
        continue
    cat = categorize(name, desc)
    src = "microsoft/skills"
    row = [name, desc, cat, src, REPO_URL, tg if tg else [cat.split("/")[0]]]
    new_rows.append(row)
    existing_names.add(name.lower())
    added += 1

if added:
    DATA.write_text(json.dumps(existing + new_rows, ensure_ascii=False))
print(f"Added {added} Microsoft skills to skills.json (total now {len(existing)+added})")