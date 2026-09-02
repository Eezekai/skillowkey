import json
from collections import Counter

rows = json.load(open("/tmp/skills_final.json"))

# Category order + labels
CATS = ["data/ai","design/creative","finance/account","market/product","coding/dev","security","legal","writing/edu","music/video","ops/automation","general"]
LABELS = {
    "general":"General","data/ai":"Data & AI","design/creative":"Design & Creative",
    "finance/account":"Finance","market/product":"Marketing & Product",
    "coding/dev":"Coding & Dev","security":"Security","legal":"Legal",
    "writing/edu":"Writing & Edu","music/video":"Music & Video","ops/automation":"Ops & Automation"
}
EMOJI = {
    "general":"\U0001F9F0","data/ai":"\U0001F4CA","design/creative":"\U0001F3A8","finance/account":"\U0001F4B8",
    "market/product":"\U0001F4E3","coding/dev":"\U0001F4BB","security":"\U0001F6E1\uFE0F","legal":"\u2696\uFE0F",
    "writing/edu":"\u270D\uFE0F","music/video":"\U0001F3B5","ops/automation":"\u2699\uFE0F"
}
cc = Counter(r[2] for r in rows)

def jsesc(s):
    return s.replace("\\","\\\\").replace('"','\\"').replace("\n","\\n").replace("\r","").replace("\t"," ")

js_rows = []
for name, desc, cat, orig, url, tags in rows:
    tags_js = ",".join('"%s"' % jsesc(t) for t in tags)
    js_rows.append('["%s","%s","%s","%s","%s",[%s]]' % (jsesc(name), jsesc(desc), cat, jsesc(orig), url, tags_js))
data_js = "[" + ",".join(js_rows) + "]"

total = len(rows)
# all distinct tags for tag filtering (secondary tags, minus primary category tags)
all_tags = Counter()
for r in rows:
    for t in r[5]:
        if t not in LABELS.keys() and t not in EMOJI.keys():
            all_tags[t]+=1
# build a curated tag filter set
taglist = [t for t,n in all_tags.most_common(24)]
tag_js = ",".join('"%s"' % t for t in taglist)

cats_js = "[" + ",".join('{"id":"%s","label":"%s","emoji":"%s","n":%d}' % (c, LABELS[c], EMOJI[c], cc.get(c,0)) for c in CATS) + "]"

T = """<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Skillowkey - The Agent Skills Library</title>
<meta name="description" content="A curated, searchable library of __TOTAL__ ready-to-use agent skills. Sourced, organized by category and topic, with source links on every skill.">
<meta property="og:title" content="Skillowkey - The Agent Skills Library">
<meta property="og:description" content="__TOTAL__ agent skills, sorted and searchable. Browse free.">
<meta property="og:type" content="website">
<meta name="twitter:card" content="summary">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Crect width='100' height='100' rx='22' fill='%230b0e14'/%3E%3Cpath d='M22 28h56v14H22zm0 30h56v14H22z' fill='%235eead4'/%3E%3C/svg%3E">
<style>
:root{--bg:#0b0e14;--bg2:#11161f;--card:#161d29;--line:#232c3c;--txt:#e7ecf3;--mut:#94a3b8;--acc:#5eead4;--acc2:#38bdf8;--good:#34d399}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--txt);font-family:-apple-system,'Segoe UI',Roboto,Inter,sans-serif;line-height:1.55;-webkit-font-smoothing:antialiased}
a{color:var(--acc);text-decoration:none}
.wrap{max-width:1180px;margin:0 auto;padding:0 22px}
header{position:sticky;top:0;z-index:50;background:rgba(11,14,20,.88);backdrop-filter:blur(12px);border-bottom:1px solid var(--line)}
.nav{display:flex;justify-content:space-between;align-items:center;padding:14px 0}
.logo{display:flex;align-items:center;gap:10px;font-size:19px;font-weight:700;letter-spacing:.2px}
.logo .dot{width:11px;height:11px;border-radius:3px;background:linear-gradient(135deg,var(--acc),var(--acc2));box-shadow:0 0 14px var(--acc)}
.nav a.cc{color:var(--mut);font-size:14px;margin-left:22px;font-weight:500}
.nav a.cc:hover{color:var(--txt)}
.hero{padding:70px 0 42px;text-align:center;position:relative;overflow:hidden}
.hero:before{content:"";position:absolute;inset:0;background:radial-gradient(600px 260px at 50% 0%,rgba(94,234,212,.09),transparent 70%);pointer-events:none}
.eyebrow{display:inline-flex;align-items:center;gap:8px;font-size:12.5px;font-weight:600;color:var(--acc);background:rgba(94,234,212,.08);border:1px solid rgba(94,234,212,.25);padding:6px 14px;border-radius:999px;letter-spacing:.4px;text-transform:uppercase}
h1{font-size:clamp(34px,5.4vw,58px);line-height:1.08;font-weight:800;letter-spacing:-.5px;margin:22px auto 0;max-width:820px}
h1 .grad{background:linear-gradient(90deg,var(--acc),var(--acc2));-webkit-background-clip:text;background-clip:text;color:transparent}
.hero p.sub{font-size:clamp(15px,2.2vw,19px);color:var(--mut);max-width:660px;margin:18px auto 28px}
.stats{display:flex;gap:14px;justify-content:center;flex-wrap:wrap;margin-top:6px}
.stat{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:15px 24px;text-align:center}
.stat b{display:block;font-size:25px;font-weight:800;color:var(--acc)}
.stat span{font-size:12px;color:var(--mut);text-transform:uppercase;letter-spacing:.5px}
.searchbar{max-width:620px;margin:30px auto 0;position:relative}
.searchbar input{width:100%;padding:16px 20px 16px 50px;font-size:16px;border-radius:14px;border:1px solid var(--line);background:var(--card);color:var(--txt);outline:none;transition:.15s}
.searchbar input::placeholder{color:var(--mut)}
.searchbar input:focus{border-color:var(--acc);box-shadow:0 0 0 3px rgba(94,234,212,.15)}
.searchbar svg{position:absolute;left:18px;top:50%;transform:translateY(-50%);color:var(--mut)}
.chips{display:flex;gap:8px;justify-content:center;flex-wrap:wrap;margin-top:16px}
.chip{padding:7px 13px;font-size:12.5px;border-radius:999px;border:1px solid var(--line);background:var(--bg2);color:var(--mut);cursor:pointer;font-weight:600;transition:.12s}
.chip:hover{color:var(--txt);border-color:var(--mut)}
.chip.on{background:var(--acc);border-color:var(--acc);color:#06251f}
.chip .cn{opacity:.7;font-weight:700;margin-left:5px;font-size:11px}
.tagrow{display:flex;gap:8px;justify-content:center;flex-wrap:wrap;margin-top:12px}
.tag{font-size:11.5px;padding:4px 11px;border-radius:999px;border:1px solid var(--line);background:var(--card);color:var(--mut);cursor:pointer;transition:.12s;font-weight:600}
.tag:hover{color:var(--txt);border-color:var(--acc2)}
.tag.on{background:var(--acc2);border-color:var(--acc2);color:#06251f}
section.library{padding:24px 0 60px}
.libhead{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:14px}
.libhead h2{font-size:22px;font-weight:800}
.libhead span{color:var(--mut);font-size:13px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px;display:flex;flex-direction:column;transition:.15s}
.card:hover{border-color:var(--acc);transform:translateY(-2px)}
.card .cat{font-size:10.5px;font-weight:700;text-transform:uppercase;letter-spacing:.6px;color:var(--acc2);margin-bottom:7px}
.card .nm{font-weight:700;font-size:15px;margin-bottom:6px;word-break:break-word}
.card .ds{font-size:12.5px;color:var(--mut);flex:1;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.card .tags{display:flex;flex-wrap:wrap;gap:5px;margin-top:10px}
.card .tg{font-size:10.5px;padding:2px 8px;border-radius:999px;background:var(--bg2);border:1px solid var(--line);color:var(--mut)}
.card .ft{display:flex;justify-content:space-between;align-items:center;margin-top:11px;font-size:11px;color:var(--mut);gap:8px}
.card a.src{color:var(--mut);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:62%}
.card a.src:hover{color:var(--acc2)}
.trust{padding:50px 0;border-top:1px solid var(--line);border-bottom:1px solid var(--line);background:var(--bg2)}
.trust .grid3{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:18px;margin-top:24px}
.tbox{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:20px}
.tbox .ic{font-size:22px;margin-bottom:10px}
.tbox b{font-size:15px;display:block;margin-bottom:6px}
.tbox p{font-size:13px;color:var(--mut)}
.cta{padding:60px 0;text-align:center}
.cta h2{font-size:clamp(24px,4vw,36px);font-weight:800;margin-bottom:12px}
.cta p{color:var(--mut);max-width:520px;margin:0 auto 24px}
.btn{display:inline-flex;align-items:center;gap:9px;background:linear-gradient(90deg,var(--acc),var(--acc2));color:#06251f;font-weight:700;padding:14px 28px;border-radius:12px;font-size:15px;transition:.15s;box-shadow:0 6px 24px rgba(94,234,212,.25)}
.btn:hover{transform:translateY(-2px)}
footer{border-top:1px solid var(--line);padding:26px 0;color:var(--mut);font-size:13px}
footer .wrap{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px}
.empty{text-align:center;color:var(--mut);padding:40px 0;font-size:14px}
.more{text-align:center;margin-top:24px}
.btn.ghost{background:transparent;border:1px solid var(--line);color:var(--mut);box-shadow:none}
.btn.ghost:hover{color:var(--txt);border-color:var(--acc)}
</style></head><body>
<header><div class="wrap"><div class="nav">
  <div class="logo"><span class="dot"></span>Skillowkey</div>
  <nav><a class="cc" href="#library">Library</a><a class="cc" href="#about">About</a></nav>
</div></div></header>

<div class="hero"><div class="wrap">
  <div class="eyebrow">Ready-to-use agent skills, one search away</div>
  <h1>The agent skills library.<br><span class="grad">Curated. Organized. Ready.</span></h1>
  <p class="sub">Skip the endless GitHub hunting. Skillowkey gathers __TOTAL__ agent skills into one searchable, categorized library, each linked to its source, so you can find what works and get back to building.</p>
  <div class="stats">
    <div class="stat"><b>__TOTAL__</b><span>skills collected</span></div>
    <div class="stat"><b>249</b><span>source repos</span></div>
    <div class="stat"><b>11</b><span>categories</span></div>
    <div class="stat"><b>Free</b><span>to browse</span></div>
  </div>
  <div class="searchbar"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="7"/><path d="m21 21-4-4"/></svg><input id="q" placeholder="Search skills - e.g. security, tax, music, marketing, python" autocomplete="off"></div>
  <div class="chips" id="chips"></div>
  <div class="tagrow" id="tagrow"></div>
</div></div>

<section class="library" id="library"><div class="wrap">
  <div class="libhead"><h2>Browse the library</h2><span id="count"></span></div>
  <div class="grid" id="grid"></div>
  <div class="empty" id="empty" style="display:none">No skills match that filter. Clear a tag or search term and try again.</div>
  <div class="more" id="more"></div>
</div></section>

<section class="cta" id="about"><div class="wrap">
  <h2>Find the skill. Ship faster.</h2>
  <p>Bookmark Skillowkey as your starting point for agent projects. Every skill is organized, categorized, and one click away.</p>
  <a class="btn" href="#library">Browse the library</a>
</div></section>

<footer><div class="wrap">
  <div><b>Skillowkey</b> - the agent skills library</div>
  <div>2026</div>
</div></footer>

<script>
var SKILLS = __DATA__;
var CATS = __CATS__;
var TAGS = [__TAGS__];
var curCat = "all", curTag = "", q = "", shown = 90;
var chipsEl = document.getElementById("chips"), tagEl = document.getElementById("tagrow");
CATS.forEach(function(c){
  var b = document.createElement("button");
  b.className = "chip";
  b.innerHTML = c.emoji + " " + c.label + '<span class="cn">' + c.n + '</span>';
  b.onclick = function(){
    document.querySelectorAll("#chips .chip").forEach(function(x){x.classList.remove("on");});
    b.classList.add("on"); curCat=c.id; shown=90; render();
  };
  chipsEl.appendChild(b);
});
TAGS.forEach(function(t){
  var b = document.createElement("button");
  b.className = "tag";
  b.textContent = t;
  b.onclick = function(){
    if(curTag===t){ curTag=""; this.classList.remove("on"); }
    else { curTag=t; document.querySelectorAll("#tagrow .tag").forEach(function(x){x.classList.remove("on");}); this.classList.add("on"); }
    shown=90; render();
  };
  tagEl.appendChild(b);
});
function clearTag(){ curTag=""; document.querySelectorAll("#tagrow .tag").forEach(function(x){x.classList.remove("on");}); shown=90; render(); }
function render(){
  var grid = document.getElementById("grid"), more = document.getElementById("more");
  var list = SKILLS;
  if(curCat!=="all") list = list.filter(function(s){return s[2]===curCat;});
  if(curTag) list = list.filter(function(s){return s[5].indexOf(curTag)>=0;});
  if(q){ var qq=q.toLowerCase(); list = list.filter(function(s){return (s[0]+" "+s[1]+" "+s[5].join(" ")).toLowerCase().indexOf(qq)>=0;}); }
  document.getElementById("count").textContent = list.length + " skill" + (list.length===1?"":"s") + (curTag? " \u00b7 tag: "+curTag: "");
  document.getElementById("empty").style.display = list.length?"none":"block";
  var part = list.slice(0,shown);
  var html = "";
  part.forEach(function(s){
    var tgs = s[5].map(function(t){return '<span class="tg">'+t+'</span>';}).join("");
    html += '<div class="card"><div class="cat">'+s[2].replace(/\//g," / ")+'</div>'
      + '<div class="nm">'+s[0]+'</div><div class="ds">'+s[1]+'</div>'
      + (tgs? '<div class="tags">'+tgs+'</div>':'')
      + '<div class="ft">' + (s[4] ? '<a class="src" href="'+s[4]+'" target="_blank" rel="noopener">'+s[4].replace("https://","")+'</a>' : '<span>'+s[3]+'</span>') + '</div>'
      + '</div>';
  });
  grid.innerHTML = html;
  more.innerHTML = shown < list.length
    ? '<button class="btn ghost" onclick="shown+=90;render()">Load ' + Math.min(90, list.length-shown) + ' more - ' + list.length + ' total</button>'
    : (list.length>90 ? '<span style="color:var(--mut);font-size:13px">Showing all ' + list.length + '</span>' : "");
}
document.getElementById("q").addEventListener("input", function(e){ q=e.target.value; shown=90; render(); });
render();
</script>
</body></html>"""

HTML = T.replace("__DATA__", data_js).replace("__CATS__", cats_js).replace("__TAGS__", tag_js).replace("__TOTAL__", str(total))
open("/home/ubuntu/skillowkey-site/index.html","w").write(HTML)
print("written", len(HTML), "bytes,", total, "skills,", len(taglist), "tags")