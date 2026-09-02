#!/usr/bin/env python3
"""harvest_smithery.py - Bulk-ingest Smithery MCP server registry into Skillowkey.
Adds MCP servers (agent tools) as skills in category 'mcp/tools'.
Source: https://registry.smithery.ai/servers?page=N&pageSize=M (public).
"""
import json, os, re, time, urllib.request, urllib.error
from pathlib import Path
BASE = Path("/home/ubuntu/skillowkey-site")
DATA = BASE / "data" / "skills.json"
SM_SRC = "smithery-mcp"

def fetch_servers(page, per=20):
    u = f"https://registry.smithery.ai/servers?page={page}&pageSize={per}"
    req = urllib.request.Request(u, headers={"Accept":"application/json","User-Agent":"Mozilla/5.0 skillowkey-harvest"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except Exception:
        return {}

site = json.loads(DATA.read_text())
names = {x[0].lower() for x in site}
srcs = set(x[4].lower() for x in site)

def add_skill(name, desc, owner, homepage, usecount):
    if not name or name.lower() in names: return 0
    if homepage:
        kl = homepage.lower().rstrip("/")
        if kl in srcs: return 0
        srcs.add(kl)
    desc = re.sub(r"\s+"," ",desc).strip()[:160]
    site.append([name, desc, "mcp/tools", SM_SRC, homepage or "", ["mcp","tools"], usecount, "", ""])
    names.add(name.lower())
    return 1

PAGES = int(os.environ.get("SMITH_PAGES","50"))
PER = int(os.environ.get("SMITH_PER","40"))
added = 0
scanned = 0
for page in range(1, PAGES+1):
    d = fetch_servers(page, PER)
    srvs = d.get("servers", [])
    if not srvs:
        time.sleep(2); continue
    for s in srvs:
        if s.get("unlisted") or s.get("inactive"): continue
        scanned += 1
        nm = s.get("displayName") or s.get("qualifiedName") or ""
        desc = s.get("description") or ""
        owner = s.get("owner") or s.get("namespace") or ""
        homepage = s.get("homepage") or ""
        usec = s.get("useCount") or 0
        verified = s.get("verified") or False
        bysm = s.get("bySmithery") is True
        # quality gate: keep verified, high-use, or smithery-official
        if not verified and usec < 30 and not bysm: continue
        added += add_skill(nm, desc, owner, homepage, usec)
    # write incrementally
    DATA.write_text(json.dumps(site, ensure_ascii=False))
    time.sleep(1.5)
print(f"scanned {scanned} servers, added {added} skills. total {len(site)}")