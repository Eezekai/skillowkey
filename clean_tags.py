#!/usr/bin/env python3
"""clean_tags.py - Strip bracket/quote artifacts from skill tags.
Some harvested SKILL.md files had `tags: [a, b]` and the parser kept the
literal [ ] and quotes. This cleans every tag across the dataset so the
UI never renders raw brackets.
"""
import json, re
from pathlib import Path
DATA = Path("/home/ubuntu/skillowkey-site/data/skills.json")

d = json.loads(DATA.read_text())
STRIP_BRACKETS = re.compile(r'^[\["\']+|[\]"\']+$')
cleaned = 0
for s in d:
    if len(s) > 5 and isinstance(s[5], list):
        new = []
        for t in s[5]:
            t = STRIP_BRACKETS.sub("", t).strip()
            if t:
                new.append(t)
        if new != s[5]:
            s[5] = new
            cleaned += 1
DATA.write_text(json.dumps(d, ensure_ascii=False))
print(f"cleaned tags on {cleaned} skills | total {len(d)}")

# verify no brackets remain in any tag
from collections import Counter
alltags = Counter()
for s in d:
    for t in (s[5] if len(s) > 5 else []):
        alltags[t] += 1
bad = [t for t in alltags if '[' in t or ']' in t or t.startswith('"')]
print("remaining bracket/quote tags:", bad if bad else "NONE")
print("top 24 tags:", [t for t, _ in alltags.most_common(24)])