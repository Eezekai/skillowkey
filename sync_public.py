#!/usr/bin/env python3
"""sync_public.py - Sync build outputs into public/ (dir wrangler serves as static assets).
Strategy to beat the 20k-file Workers Free limit:
  - Ship ONLY: app index.html, data/skills.json, category pages, sitemap, robots.txt.
  - Per-skill pages (28k) are served DYNAMICALLY by the API worker (SSR from embedded dataset),
    NOT as static files. So public/ stays at ~15 files.
"""
import shutil, pathlib
BASE = pathlib.Path("/home/ubuntu/skillowkey-site")
PUB = BASE / "public"
MP = BASE / "multipage"

# rebuild public clean
if PUB.exists(): shutil.rmtree(PUB)
PUB.mkdir(exist_ok=True)

# 1. app
shutil.copy(BASE/"index.html", PUB/"index.html")
# 2. data
(PUB/"data").mkdir(exist_ok=True)
shutil.copy(BASE/"data"/"skills.json", PUB/"data"/"skills.json")
# 3. category pages (9)
if (MP/"category").exists():
    shutil.copytree(MP/"category", PUB/"category")
# 4. sitemap + robots
for f in ("sitemap.xml","robots.txt"):
    if (MP/f).exists(): shutil.copy(MP/f, PUB/f)
# 5. robots referencing SSR is fine; keep the app as index.
# 6. og share image (brand asset)
if (BASE/"og-image.png").exists(): shutil.copy(BASE/"og-image.png", PUB/"og-image.png")

n_cat = len(list((PUB/"category").glob("*/"))) if (PUB/"category").exists() else 0
n_total = sum(1 for _ in PUB.rglob("*") if _.is_file())
print(f"public/ synced: {n_total} files ({n_cat} category pages). Under 20k limit: {n_total < 20000}")