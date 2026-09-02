#!/usr/bin/env python3
"""multipage.py - Generate one static HTML page per skill + per category + a tag page,
giving Google crawlable URLs (the #1 SEO lever for a directory site).

Outputs into /home/ubuntu/skillowkey-site/multipage/ :
  index.html          (the existing app, copied)
  category/<slug>/index.html
  skills/<slug>/index.html
  sitemap.xml         (regenerated pointing at real files)
  robots.txt          (allow crawl)
Deployment target: directory-served static site (Pages/worker-static). 
"""
import json, re, pathlib, urllib.parse
BASE = pathlib.Path("/home/ubuntu/skillowkey-site/")
OUT = BASE / "multipage"
skills = json.loads((BASE/"data/skills.json").read_text())
APP = (BASE/"index.html").read_text()

def esc(s): return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"',"&quot;")
def slug(n):
    s = re.sub(r'[^a-z0-9]+','-', n.lower()).strip('-')
    return (s[:60] or 'skill')
def cat_slug(c): return c.replace('/','-')

# category -> label from CATS
CATS = [{"id":"coding/dev","label":"Coding & Dev"},{"id":"market/product","label":"Marketing & Product"},
        {"id":"data/ai","label":"Data & AI"},{"id":"security","label":"Security"},
        {"id":"general","label":"General"},{"id":"writing/edu","label":"Writing & Edu"},
        {"id":"legal","label":"Legal"},{"id":"design/creative","label":"Design & Creative"},
        {"id":"ops/automation","label":"Ops & Automation"},{"id":"finance/account","label":"Finance & Account"},
        {"id":"music/video","label":"Music & Video"}]
cat_label = {c["id"]:c["label"] for c in CATS}

def page(title, desc, body, canonical, schema):
    return f"""<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{canonical}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc[:150])}">
{schema}
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Geist:wght@500;700;800&display=swap">
<style>body{{font-family:'Geist',system-ui,sans-serif;max-width:900px;margin:0 auto;padding:24px;color:#111;line-height:1.6}}
a{{color:#0057ff;text-decoration:none}} .crumb{{font-size:13px;color:#666;margin-bottom:18px}}
h1{{font-size:28px;margin:6px 0 8px}} .src{{font-size:13px}} .tag{{display:inline-block;background:#eef;border-radius:999px;padding:3px 10px;font-size:12px;margin-right:6px;color:#333}}
.back{{display:inline-block;margin-top:24px;font-size:13px}} ul{{columns:3;font-size:14px;gap:20px}} li{{margin-bottom:8px}} .stat{{color:#888;font:13px monospace}}</style>
</head><body>{body}</body></html>"""

def scr(typ, obj): return f'<script type="application/ld+json">{json.dumps(obj)}</script>'

urls = ["https://skillowkey.com/"]
# clear old output
import shutil
if OUT.exists(): shutil.rmtree(OUT)
(OUT/"category").mkdir(parents=True, exist_ok=True)
(OUT/"skills").mkdir(parents=True, exist_ok=True)

# group
def g(item, i, d=""):
    try: return item[i] if item[i] is not None and item[i] != "" else d
    except (IndexError, KeyError): return d

by_cat = {}
for s in skills: by_cat.setdefault(g(s,2,"general"), []).append(s)

n_skills=0; used=set()
for cat, items in by_cat.items():
    cs = cat_slug(cat)
    canon = f"https://skillowkey.com/category/{cs}/"
    urls.append(canon)
    rows = "".join(f'<li><a href="/skills/{slug(g(i,0))}/">{esc(g(i,0))}</a> <span class="stat">({g(i,6,0)})</span></li>' for i in items)
    body = f'<div class="crumb"><a href="/">Skillowkey</a> / Category</div><h1>{esc(cat_label.get(cat,cat))} Skills</h1>'
    body += f'<p class="src">{len(items)} skills • <a href="/">Browse all via the interactive library →</a></p>'
    body += f'<ul>{rows}</ul><a class="back" href="/">← Back to library</a>'
    sch = scr("Collection", {"@context":"https://schema.org","@type":"CollectionPage","name":f"{cat_label.get(cat,cat)} Skills","numberOfItems":len(items),"url":canon})
    (OUT/"category"/cs).mkdir(parents=True, exist_ok=True)
    (OUT/"category"/cs/"index.html").write_text(page(f"{cat_label.get(cat,cat)} Skills - Skillowkey", f"Browse {len(items)} {cat_label.get(cat,cat)} AI agent skills (SKILL.md), each source-linked and ready to use.", body, canon, sch))

for s in skills:
    sl = slug(g(s,0))
    if sl in used: 
        sl = sl + "-" + str(len(used))
    used.add(sl)
    canon = f"https://skillowkey.com/skills/{sl}/"
    urls.append(canon)
    s_cat = g(s,2,"general"); s_tags = g(s,5,[]); s_name=g(s,0); s_desc=g(s,1,""); s_star=g(s,6,0); s_url=g(s,4,"#")
    tags = "".join(f'<span class="tag">{esc(t)}</span>' for t in s_tags)
    body = f'<div class="crumb"><a href="/">Skillowkey</a> / <a href="/category/{cat_slug(s_cat)}/">{esc(cat_label.get(s_cat,s_cat))}</a> / {esc(s_name)}</div>'
    body += f'<h1>{esc(s_name)}</h1>'
    body += f'<p class="stat">★ {s_star} • {s_cat.replace("/"," / ")}</p>'
    body += f'<div>{tags}</div>'
    body += f'<p>{esc(s_desc)}</p>'
    body += f'<p class="src">Source: <a href="{esc(s_url)}" rel="noopener">{esc(s_url)}</a></p>'
    body += f'<a class="back" href="/">← Back to all skills</a>'
    sch = scr("SoftwareApplication", {"@context":"https://schema.org","@type":"SoftwareApplication","name":s_name,"description":s_desc,"url":canon,"applicationCategory":"DeveloperApplication","keywords":s_tags})
    d = OUT/"skills"/sl; d.mkdir(parents=True, exist_ok=True)
    (d/"index.html").write_text(page(f"{s_name} - AI Agent Skill | Skillowkey", f"{s_name}: {str(s_desc)[:150]}", body, canon, sch))
    n_skills+=1

# copy the interactive app to index
(OUT/"index.html").write_text(APP)
(OUT/"robots.txt").write_text("User-agent: *\nAllow: /\nSitemap: https://skillowkey.com/sitemap.xml\n")
urls = list(dict.fromkeys(urls))
sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
for u in urls: sitemap += f'  <url><loc>{u}</loc></url>\n'
sitemap += '</urlset>\n'
(OUT/"sitemap.xml").write_text(sitemap)
print(f"Generated multipage/: {n_skills} skill pages, {len(by_cat)} category pages, sitemap {len(urls)} URLs")
print("size MB:", round(sum(p.stat().st_size for p in OUT.rglob('*') if p.is_file())/1e6,1))