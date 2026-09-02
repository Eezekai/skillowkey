#!/usr/bin/env python3
"""Redeploy Skillowkey static site to Cloudflare Worker at skillowkey.com.
Usage: python3 redeploy.py  (from /home/ubuntu/skillowkey-site)
Key: set in env CLOUDFLARE_TOKEN (or edit below). Worker is SERVICE-WORKER format
(e.g. addEventListener('fetch')), NOT es-module. Upload part must be named index.js.
"""
import os, json, subprocess
from pathlib import Path

ACC = "c24e84083b8e4729e831ca86e234d4dc"
TOKEN = os.environ.get("CLOUDFLARE_TOKEN", "")  # REQUIRED - set via env, do not commit
if not TOKEN:
    print("ERROR: set CLOUDFLARE_TOKEN env var before running")
    raise SystemExit(1)
SC = "skillowkey"
HTML = Path("/home/ubuntu/skillowkey-site/index.html").read_text()

html_lit = json.dumps(HTML)
worker = "const html = " + html_lit + ";\n" + \
 'addEventListener("fetch", event => {\n' + \
 '  event.respondWith(new Response(html, {\n' + \
 '    headers: {"content-type": "text/html; charset=utf-8", "cache-control": "public, max-age=300"}\n' + \
 '  }));\n' + \
 '});\n'
Path("/tmp/worker_sw.js").write_text(worker)

cmd = ["curl","-sS","-X","PUT",
  f"https://api.cloudflare.com/client/v4/accounts/{ACC}/workers/scripts/{SC}",
  "-H", f"Authorization: Bearer {TOKEN}",
  "-F", 'metadata={"body_part":"index.js","content_type":"application/javascript"};type=application/json',
  "-F", "index.js=@/tmp/worker_sw.js;type=application/javascript"]
r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
d = json.loads(r.stdout)
print("deploy success:", d.get("success"), d.get("errors"))

# verify
import time; time.sleep(2)
v = subprocess.run(["curl","-sS","https://skillowkey.com/"], capture_output=True, text=True, timeout=25).stdout
print("live size:", len(v), "| light bg present:", "#fbfcfc" in v, "| title ok:", "<title>Skillowkey" in v)