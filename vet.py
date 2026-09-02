#!/usr/bin/env python3
"""vet.py - Security + quality gate for Skillowkey's skill database.

FLAGS (never deletes): 
  1. dangerous  - command-pipe-to-shell / credential exfiltration / malicious patterns
  2. suspicious - likely-malicious, lower confidence (netcat listeners, forks, onion)
  3. junk       - garbage / empty / too-short / raw-code descriptions
Writes data/vet_flags.json + vet_report.json and prints a summary.

Row shape: [name, desc, category, source, url, [tags], stars, pushed, created]
"""
import json, re, collections, pathlib
BASE = pathlib.Path("/home/ubuntu/skillowkey-site/")
DATA = BASE / "data" / "skills.json"
OUT_FLAGS = BASE / "data" / "vet_flags.json"
OUT_REP = BASE / "vet_report.json"

# ---------- pattern library ----------
# High-confidence "pipe straight to shell" -> malware / persistence
PIPE2SHELL = [
    r"\bcurl[^\n]*\|\s*(ba)?sh\b",
    r"\bcurl[^\n]*\|\s*wget",
    r"\bwget[^\n]*\|\s*(ba)?sh\b",
    r"\bcurl[^\n]*\|\s*sudo",
    r"\bcurl[^\n]*\|\s*python3?\b",
    r"\beval\s*[\(\"]",
    r"eval\s*\$\s*\(",
    r"\bbash\s+-c\s+[\"']",
    r"base64\s*-\s*d\s*\|\s*(ba)?sh",
    r"\bsh\s+-c\s+[\"']",
    # powershell encoded / download+exec
    r"powershell\s+[^\n]*(enc(odedcommand)?|IEX|DownloadString|DownloadFile)",
    r"iex\s*[\(\"]",
]
# Credential / secret exfiltration
EXFIL = [
    r"(GITHUB_TOKEN|GH_TOKEN|AWS_SECRET|AWS_ACCESS_KEY|API_KEY|OPENAI_API_KEY|ANTHROPIC_API_KEY|XAI_API_KEY|SECRET_|DISCORD_TOKEN|SLACK_TOKEN|PAT)",
    r"(printenv|env\b)[^\n]*(curl|wget|nc|POST|send)",
    r"exfil", r"exfiltrat", r"data[-\s]?breach",
    r"(evil\.|\.onion|ngrok[^\n]*/|webhook\.site|requestbin|webhook\.codespaces)[^\n]*(collect|log|conf)|collect[^\n]*(evil\.|ngrok)",
]
# Suspicious exec tools / known bad, lower confidence
SUSPICIOUS = [
    r"\bnc\s+-e\b", r"\bncat\s+--sh-exec\b", r"\bsocat\s+[^\n]*exec",  # reverse shells
    r"chmod\s+777\s+/etc/", r"passwd\s+-l\s+root", r"usermod", r"sudoers",
    r"crontab[^\n]*curl",  # persistence
    r"\.onion", r"ransom",
]
# Garbage / meaningless descriptions
GARBAGE_SET = {"|", "0", "n/a", "n/a.", "none", "tbd", "-", "--", "no", "yes",
               "sdf", "asdf", "test", "test.", "todo", "null", "undefined", "nan",
               '[object object]', "blank", "empty", "n/a n/a", "slam"}
JUNK_RE = [
    r"^[\W_]{1,8}$",                    # | | | or punctuation-only
    r"^\[object Object\]$",             # JS stringify of object
    r"^[\d.\s]*$",                      # only digits
    r"^(curl|wget|python|node|bash|#!/)",  # starts with raw command
]

def is_dangerous(name, desc):
    """Return (bool, type, reason). Checks name+description.

    Whitelist legitimate security-detection skills: if the description is
    explicitly about DETECTING/HUNTING/ANALYZING/ALERTING on exfiltration,
    injection, or powershell abuse (a defensive context), it is NOT dangerous.
    """
    blob = f"{name} {desc}".lower()
    defensive = bool(re.search(
        r"(detect|detection|hunt|analy(se|ze)|alert|identif|monitor|indicators?|"
        r"forensic|mitre|telemetry|log|investigat|correlate|attribute|triage"
        r"|response|guidelines?|playbook|framework|defense|policies?|best\s*pract"
r"|avoid|never\s+use|reject|block|prevent|guard|sanitize|reviewing|remove|eliminate|hardening|misuse|abuse)",
        blob))
    # clear malicious: pipe-to-shell or explicit exfil WITH an actual endpoint blob
    # require an actual target/collect action, not just the word "exfil"
    for pat in PIPE2SHELL:
        if re.search(pat, blob) and not defensive:
            return True, "malicious", f"pipe-to-shell: {pat}"
    # exfil: must show BOTH an action (curl/POST/collect) AND a clearly-hostile
    # sink (evil-domain / onion / ngrok / requestbin / webhook.site / id-based
    # collect endpoint). NOT generic "webhook" (legit email APIs use webhooks).
    exfil_has_action = re.search(r"(curl|wget|POST|\bprintenv\b|\benv\b|collect|send|upload)", blob)
    exfil_has_sink = re.search(r"(evil\.|\.onion|\bngrok\.|\brequestbin|webhook\.site|beeceptor|"
                               r"interact\.sh|oast\.(fun|pro|online|site|me)|collect\?)", blob)
    if exfil_has_action and exfil_has_sink and not defensive:
        return True, "malicious", "credential exfiltration"
    for pat in SUSPICIOUS:
        if re.search(pat, blob) and not defensive:
            return True, "suspicious", f"suspicious: {pat}"
    return False, "", ""

def clean_desc(desc):
    return re.sub(r"\s+", " ", str(desc)).strip() if desc else ""

def is_junk(desc):
    d = clean_desc(desc).strip()
    if not d: return True
    dl = d.lower()
    if dl in GARBAGE_SET: return True
    for p in JUNK_RE:
        if re.search(p, d): return True
    if len(d) < 12: return True
    return False

def main():
    skills = json.loads(DATA.read_text())
    flagged = []
    junk_only = []
    stats = collections.Counter()
    for idx, s in enumerate(skills):
        name, desc = s[0], s[1]
        # dangerous/suspicious takes priority
        danger, typ, reason = is_dangerous(name, desc)
        if danger:
            stats[typ] += 1
            flagged.append({"index": idx, "name": name, "type": typ,
                            "reason": reason, "snippet": clean_desc(desc)[:140]})
        else:
            # duplicate detection by normalized name
            pass
    # junk detection on the non-dangerous set
    ok_idx = {f["index"] for f in flagged}
    for idx, s in enumerate(skills):
        if idx in ok_idx: continue
        if is_junk(s[1]):
            stats["junk"] += 1
            junk_only.append({"index": idx, "name": s[0], "type": "junk",
                              "reason": "garbage/too-short description",
                              "snippet": clean_desc(s[1])[:140]})

    all_flag = flagged + junk_only
    OUT_FLAGS.write_text(json.dumps({"flagged": all_flag,
                                     "safe_count": len(skills)-len(all_flag),
                                     "flagged_count": len(all_flag),
                                     "malicious_count": stats["malicious"],
                                     "suspicious_count": stats["suspicious"],
                                     "junk_count": stats["junk"]}, indent=1))
    report = {
        "total_skills": len(skills),
        "flagged_total": len(all_flag),
        "malicious": stats["malicious"],
        "suspicious": stats["suspicious"],
        "junk": stats["junk"],
        "safe": len(skills)-len(all_flag),
        "top_malicious": sorted([f for f in flagged if f["type"]=="malicious"],
                                key=lambda x:-x["index"])[:15],
        "sample_suspicious": [f for f in flagged if f["type"]=="suspicious"][:10],
        "junk_fraction_pct": round(100*stats["junk"]/len(skills),1) if skills else 0,
        "malicious_fraction_pct": round(100*stats["malicious"]/len(skills),1) if skills else 0,
    }
    OUT_REP.write_text(json.dumps(report, indent=1))
    print(f"TOTAL {len(skills)} | safe {report['safe']} | malicious {stats['malicious']} | "
          f"suspicious {stats['suspicious']} | junk {stats['junk']}")
    print(f"wrote {OUT_FLAGS} and {OUT_REP}")
    if report["top_malicious"]:
        print("\nTop malicious examples:")
        for f in report["top_malicious"][:6]:
            print(f"  [{f['index']}] {f['name']}: {f['reason']}")

if __name__ == "__main__":
    main()