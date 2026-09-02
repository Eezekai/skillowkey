#!/usr/bin/env python3
"""deploy.py - build app + worker, then deploy to Cloudflare Worker.
Usage: CLOUDFLARE_TOKEN=<token> python3 deploy.py
"""
import os, json, subprocess, time, sys
from pathlib import Path
BASE = Path("/home/ubuntu/skillowkey-site")

# 1. rebuild index.html fresh
r = subprocess.run(["python3", str(BASE/"build.py")], capture_output=True, text=True, cwd=str(BASE))
print("build.py:", r.stdout.strip(), r.stderr.strip())
if r.returncode != 0: sys.exit("build failed")

# 2. build worker
r = subprocess.run(["python3", str(BASE/"build_worker.py")], capture_output=True, text=True, cwd=str(BASE))
print("build_worker:", r.stdout.strip(), r.stderr.strip())
if r.returncode != 0: sys.exit("worker build failed")

TOKEN = os.environ.get("CLOUDFLARE_TOKEN", "")
if not TOKEN: sys.exit("set CLOUDFLARE_TOKEN")
ACC = "c24e84083b8e4729e831ca86e234d4dc"
SC = "skillowkey"
worker_js = Path("/tmp/worker_api.js").read_text()

cmd = ["curl","-sS","-X","PUT",
  f"https://api.cloudflare.com/client/v4/accounts/{ACC}/workers/scripts/{SC}",
  "-H", f"Authorization: Bearer {TOKEN}",
  "-F", 'metadata={"body_part":"index.js","content_type":"application/javascript"};type=application/json',
  "-F", "index.js=@/tmp/worker_api.js;type=application/javascript"]
r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
try:
    d = json.loads(r.stdout); print("deploy success:", d.get("success"), d.get("errors"))
except Exception as e:
    print("deploy raw:", r.stdout[:500]); raise SystemExit

time.sleep(3)
def check(url):
    out = subprocess.run(["curl","-sS","-m","25",url], capture_output=True, text=True).stdout
    return len(out), out[:80].replace("\\n"," ")
for u in ["https://skillowkey.com/", "https://skillowkey.com/health", "https://skillowkey.com/api/stats", "https://skillowkey.com/api/search?q=claude"]:
    try:
        size, head = check(u); print(f"  {u}: {size}B | {head}")
    except Exception as e:
        print(f"  {u}: ERR {e}")