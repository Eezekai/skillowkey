#!/usr/bin/env python3
"""write_design_spec.py - emits the data/sample + design requirements to /tmp/fable_spec/
So Fable subagent has concrete material without needing the full 5438-row dataset.
"""
import json, pathlib
base = pathlib.Path("/home/ubuntu/skillowkey-site/")
out = pathlib.Path("/tmp/fable_spec/"); out.mkdir(parents=True, exist_ok=True)
d = json.load(open(base/"data/skills.json"))

# representative design sample (~14 varied)
selected = [d[0], d[2], d[5], d[10], d[14], d[18], d[25], d[40], d[60], d[120], d[300], d[700], d[1500], d[3000]]
(out/"sample.json").write_text(json.dumps(selected, indent=1))
(out/"count.txt").write_text(str(len(d)))
(out/"cats_and_tags.txt").write_text(
    "Categories + counts: " + dict_str + "\n\nTags: " + tags_str
)

# fetch cats/tags from the currently deployed index.html
html = (base/"index.html").read_text()
import re
cats = re.search(r"var CATS = (\[.*?\]);", html, re.S)
tags = re.search(r"var TAGS = (\[.*?\]);", html, re.S)
print("CATS regex match:", bool(cats))
print("TAGS regex match:", bool(tags))
dict_str = cats.group(1) if cats else "[]"
tags_str = tags.group(1) if tags else "[]"
(out/"cats_and_tags.txt").write_text(
    "Categories: " + dict_str + "\n\nTags: " + tags_str
)
print("Spec written to /tmp/fable_spec")