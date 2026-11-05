#!/usr/bin/env python3
"""Daily CBB graphics, fully in the cloud.
1) Downloads index.html + feed.json from github.com/johnalanharris/cbb-model-data
2) Runs the site in headless Chromium (feed served from GitHub) and runs the extraction snippet
3) Renders: (1) Signal/Trigger/Biggest-Edge games + Top 20, (2) What to Watch
Graphic 1 order: 4+ Best/Strong Signal games -> else Trigger Games -> else top 10 by |Edge|.
Usage: python3 cbb_daily.py      (outputs to /home/claude/cbb/graphics)
"""
import os, sys, subprocess, json, datetime
from zoneinfo import ZoneInfo
BASE = "/home/claude/cbb"; os.makedirs(BASE, exist_ok=True)
EXTRACT_JS = r'''// Cloud extraction: loads the site from GitHub, serves the feed from GitHub, runs the original snippet.
const { chromium } = require('playwright');
const fs = require('fs');
const RAW = 'https://raw.githubusercontent.com/johnalanharris/cbb-model-data/main/';
const OUT = process.argv[2] || '/home/claude/cbb/cbb_data.txt';
const EXTRA_OUT = process.argv[3] || '/home/claude/cbb/extra.txt';
(async () => {
  const bust = '?t=' + Date.now();
  const html = await (await fetch(RAW + 'index.html' + bust)).text();
  const feed = await (await fetch(RAW + 'feed.json' + bust)).text();
  const j = JSON.parse(feed);
  const b = await chromium.launch(); const p = await b.newPage();
  await p.route('**/*', r => { const u = r.request().url();
    if (u.startsWith('https://site.local/')) return r.fulfill({ body: html, contentType: 'text/html' });
    if (u.includes('script.google.com')) return r.fulfill({ status: 200, contentType: 'application/json', body: feed });
    return r.continue().catch(() => {}); });
  await p.goto('https://site.local/#cbb/picks');
  const snippet = fs.readFileSync(process.env.SNIPPET, 'utf8');
  const res = await p.evaluate(snippet);
  const dump = await p.evaluate(() => document.getElementById('dump').textContent);
  fs.writeFileSync(OUT, dump);
  // all picks for the day (for Biggest Edges)
  const iso = (dump.match(/\nDate\|(.*)\n/) || [])[1] || '';
  const sec = (n, t) => '##' + n + '\n' + t.headers.join('|') + '\n' + t.rows.filter(r => r[0] === iso).map(r => r.join('|')).join('\n') + '\n';
  fs.writeFileSync(EXTRA_OUT, sec('PICKS', j.tabs.picks) + (j.tabs.signals ? sec('SIGNALS', j.tabs.signals) : '') + '##END\n');
  console.log(res);
  await b.close();
})().catch(e => { console.error('EXTRACT FAILED:', e.message); process.exit(1); });
'''
SNIPPET_JS = r'''(async () => {
  const FEED = 'https://script.google.com/macros/s/AKfycbyPMR2wVlHml_fR2_f9HAr07fERfSpVHcn7dap5cCjt5QO6BGmEOTcJ-sswImoOt57hoA/exec';
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  for (let i = 0; i < 20 && !document.querySelector('tr td .gm'); i++) await sleep(500);
  const wr = [...document.querySelectorAll('a,button,[role=tab]')].find(x => x.textContent.trim() === 'Watch Recs');
  if (wr) wr.click();
  for (let i = 0; i < 20 && !document.querySelector('td.wscore'); i++) await sleep(500);
  const body = document.body.innerText;
  const dateLabel = (body.match(/Watch Recs\n([A-Z][a-z]{2}, [A-Z][a-z]{2} \d+)\n/) || ['', ''])[1];
  const watch = [...document.querySelectorAll('tr')].filter(r => r.querySelector('td.wscore')).map(r => {
    const tds = [...r.querySelectorAll('td')];
    const ts = [...tds[0].querySelectorAll('.t')];
    const nm = t => t.querySelector('a').textContent.trim();
    const rk = t => (t.querySelector('.mr')?.textContent || '').replace('#', '').trim();
    const neutral = tds[0].querySelector('.nb') ? 'Y' : 'N';
    const gno = (tds[0].querySelector('.n')?.textContent || '').replace('Game', '').trim();
    const start = tds[1].textContent.trim();
    const score = tds[2].textContent.trim();
    const spread = (tds[3].querySelector('small')?.textContent || '').trim();
    const tier = (r.closest('.tablebox')?.previousElementSibling?.textContent || r.closest('section')?.querySelector('.ptitle')?.textContent || '').trim();
    return [gno, nm(ts[0]), rk(ts[0]), nm(ts[1]), rk(ts[1]), neutral, start, score, spread, tier].join('|');
  });
  const j = await (await fetch(FEED + '?t=' + Date.now())).json();
  const T = x => x.headers.join('|') + '\n' + x.rows.map(r => r.join('|')).join('\n');
  const mon = { Jan: 1, Feb: 2, Mar: 3, Apr: 4, May: 5, Jun: 6, Jul: 7, Aug: 8, Sep: 9, Oct: 10, Nov: 11, Dec: 12 };
  const m = dateLabel.match(/([A-Z][a-z]{2}) (\d+)$/);
  const iso = m ? (j.pickDates || []).find(d => +d.slice(5, 7) === mon[m[1]] && +d.slice(8, 10) === +m[2]) : '';
  const ph = j.tabs.picks.headers;
  const dayPicks = j.tabs.picks.rows.filter(r => r[0] === iso);
  const conf = Object.fromEntries(j.tabs.ratings.rows.map(r => [r[1], r[2]]));
  const P5 = new Set(['SEC', 'Big Ten', 'Big 12', 'ACC', 'Big East']);
  const MID = new Set(['Pac-12', 'AAC', 'A-10', 'Mountain West', 'WCC', 'MVC', 'MAC', 'CUSA', 'Big West']);
  const lvl = t => P5.has(conf[t]) ? 3 : MID.has(conf[t]) ? 2 : 1;
  const tierName = { 3: 'P5', 2: 'MID', 1: 'LOW' };
  const watchT = watch.map(w => { const f = w.split('|'); const tr = tierName[Math.max(lvl(f[1]), lvl(f[3]))]; return [...f.slice(0, 9), tr, conf[f[1]] || '', conf[f[3]] || ''].join('|'); });
  const iT = ph.indexOf('Trigger');
  const trig = dayPicks.filter(r => r[iT] === 'Y');
  const rt = j.tabs.ratings; const top = rt.rows.filter(r => +r[0] <= 20).sort((a, b) => a[0] - b[0]);
  let out = '##META\nKey|Value\nDateLabel|' + dateLabel + '\nDate|' + iso + '\nFeedUpdated|' + j.updated + '\n';
  out += '##WATCH\ngame|away|arank|home|hrank|neutral|start|score|spread|tier|aconf|hconf\n' + watchT.join('\n') + '\n';
  out += '##TRIG\n' + ph.join('|') + '\n' + trig.map(r => r.join('|')).join('\n') + '\n';
  out += '##TOP\n' + rt.headers.join('|') + '\n' + top.map(r => r.join('|')).join('\n') + '\n';
  out += '##RECORD\n' + T(j.tabs.record) + '\n##END\n';
  document.body.innerHTML = '<pre id=dump></pre>'; document.getElementById('dump').textContent = out;
  return `date=${dateLabel} iso=${iso} watch=${watch.length} picks=${dayPicks.length} triggers=${trig.length} feedUpdated=${j.updated} chars=${out.length}`;
})()
'''
open(f"{BASE}/extract.js", "w").write(EXTRACT_JS)
open(f"{BASE}/snippet.js", "w").write(SNIPPET_JS)
env = dict(os.environ, SNIPPET=f"{BASE}/snippet.js")
r = subprocess.run(["node", f"{BASE}/extract.js", f"{BASE}/cbb_data.txt", f"{BASE}/extra.txt"],
                   capture_output=True, text=True, env=env, timeout=180)
print(r.stdout.strip()); print(r.stderr.strip(), file=sys.stderr)
if r.returncode != 0: sys.exit("EXTRACT FAILED")
EXTRACT_LINE = r.stdout.strip().splitlines()[-1]
os.environ.setdefault("SRC", f"{BASE}/cbb_data.txt")
os.environ.setdefault("OUT", f"{BASE}/graphics")
os.environ.setdefault("EXTRA_SRC", f"{BASE}/extra.txt")
# ================= RENDER =================
import os, re, html, datetime
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright

SRC = os.environ.get("SRC", "/home/claude/cbb/cbb_data.txt")
OUT = os.environ.get("OUT", "/home/claude/cbb/graphics")
os.makedirs(OUT, exist_ok=True)
ET = ZoneInfo("America/New_York")

# ---------- parse ----------
sections, cur = {}, None
for line in open(SRC, encoding="utf-8"):
    line = line.rstrip("\n")
    if line.startswith("##"):
        cur = line[2:]; sections[cur] = []; continue
    if cur and line: sections[cur].append(line.split("|"))
def table(name):
    rows = sections.get(name) or [[]]
    return [dict(zip(rows[0], r)) for r in rows[1:]]

meta = {r["Key"]: r["Value"] for r in table("META")}
DATE_LABEL = meta.get("DateLabel", "")
ISO = meta.get("Date", "")
dt = datetime.date.fromisoformat(ISO) if ISO else datetime.date.today()
DOW = os.environ.get("FORCE_DOW") or dt.strftime("%a")       # Mon..Sun
LONG_DATE = f"{dt.strftime('%A')}, {dt.strftime('%B')} {dt.day}"
TAG = dt.strftime("%Y-%m-%d")

watch_raw = table("WATCH"); trig = table("TRIG"); top = table("TOP")
# ---- Graphic 1 selection: Best/Strong Signals (4+) -> Trigger Games -> Biggest Edges ----
EXTRA_SRC = os.environ.get("EXTRA_SRC", "/home/claude/cbb/extra.txt")
_ex, _cur = {}, None
if os.path.exists(EXTRA_SRC):
    for _l in open(EXTRA_SRC, encoding="utf-8"):
        _l = _l.rstrip("\n")
        if _l.startswith("##"): _cur = _l[2:]; _ex[_cur] = []; continue
        if _cur and _l: _ex[_cur].append(_l.split("|"))
def _xt(n):
    r = _ex.get(n) or [[]]
    return [dict(zip(r[0], x)) for x in r[1:]]
def _f(x):
    try: return float(str(x).replace("+", ""))
    except: return 0.0
all_picks = [p for p in _xt("PICKS") if p.get("Spread", "").strip() and p.get("ATS Pick", "").strip()]
sig_by = {(r["Away"], r["Home"]): r for r in _xt("SIGNALS")}
BEST_MIN = 5
sig_games = []
for p in all_picks:
    r = sig_by.get((p["Away"], p["Home"]))
    if not r: continue
    a, h = _f(r.get("Away Points")), _f(r.get("Home Points"))
    gap = abs(a - h)
    if gap < 4: continue
    star_home = h > a
    sp = _f(p["Spread"]); ln = sp if star_home else -sp
    q = dict(p); q["_gap"] = gap; q["_level"] = "Best" if gap >= BEST_MIN else "Strong"
    q["ATS Pick"] = f"{p['Home'] if star_home else p['Away']} " + ("PK" if ln == 0 else f"{ln:+g}")
    sig_games.append(q)
if len(sig_games) > 3:
    MODE = "signals"; trig = sorted(sig_games, key=lambda p: (-p["_gap"], p.get("Start", "")))
elif trig:
    MODE = "triggers"; trig = sorted(trig, key=lambda p: p.get("Start", ""))
else:
    MODE = "edges"; trig = sorted(all_picks, key=lambda p: -abs(_f(p["Edge"])))[:10]
MODE_TXT = {
    "signals": ("Best &amp; Strong Signals", "Signal Games &amp; Top 20",
                f"Best = Team Score difference of {BEST_MIN}+, Strong = 4. Pick = team with the higher Team Score."),
    "triggers": ("Trigger Games", "Trigger Games &amp; Top 20",
                 "Trigger = Confidence above 0.600 or below 0.400 and Edge beyond ±3."),
    "edges": ("Biggest Edges", "Biggest Edges &amp; Top 20",
              "No signal or trigger games today. Top 10 games by |Edge| (model line vs. Vegas spread); games without a line excluded."),
}[MODE]

P5 = {"SEC", "Big Ten", "Big 12", "ACC", "Big East"}
MID = {"Pac-12", "AAC", "A-10", "Mountain West", "WCC", "MVC", "MAC", "CUSA", "Big West"}
def _lvl(c): return 3 if c in P5 else 2 if c in MID else 1
for g in watch_raw:
    if g.get("aconf") is not None:
        g["tier"] = {3: "P5", 2: "MID", 1: "LOW"}[max(_lvl(g.get("aconf", "")), _lvl(g.get("hconf", "")))]

# de-duplicate games listed twice
seen, watch = set(), []
for g in watch_raw:
    k = (g["away"], g["home"])
    if k in seen: continue
    seen.add(k); watch.append(g)

def score(g):
    try: return float(g["score"])
    except: return 0.0
def tip_minutes(s):
    m = re.search(r"(\d{1,2}):(\d{2})\s*(AM|PM)", s or "")
    if not m: return None
    h, mi, ap = int(m.group(1)), int(m.group(2)), m.group(3)
    h = h % 12 + (12 if ap == "PM" else 0)
    return h * 60 + mi
def tip_label(s):
    m = re.search(r"(\d{1,2}:\d{2}\s*(AM|PM))", s or "")
    return (m.group(1) + " ET") if m else "TBD"
def fav_line(g):
    s = g["spread"].strip()
    if not s or s.lower() == "no line": return "No line"
    v = float(s.replace("+", ""))
    if v == 0: return "Pick'em"
    team = g["home"] if v < 0 else g["away"]
    return f"{team} -{abs(v):g}"
def team_html(name, rk):
    r = f"<span class=rkb>#{rk}</span>" if rk else ""
    return f"{r}<span class=tn>{html.escape(name)}</span>"
TIER = {"P5": ("Power 5", "p5"), "MID": ("Mid Major", "mid"), "LOW": ("Low Major", "low")}

# ---------- style ----------
CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{width:1080px;background:#F4F2EF;font-family:'Inter',sans-serif;color:#141414}
.card{width:1080px;background:#F4F2EF;padding:0 0 30px}
.hdr{background:#141414;padding:34px 48px 28px;position:relative;overflow:hidden;border-bottom:10px solid #C8102E}
.hdr:after{content:"";position:absolute;right:-40px;top:-80px;width:300px;height:300px;border-radius:50%;
  background:repeating-linear-gradient(-45deg,rgba(200,16,46,.55) 0 16px,transparent 16px 34px)}
.kick{font:700 18px 'Inter';letter-spacing:.22em;text-transform:uppercase;color:#E8A0AC}
.title{font:800 56px/1.02 'Inter Display','Inter';color:#fff;margin-top:8px;letter-spacing:-.01em;position:relative;z-index:1}
.sub{font:600 20px 'Inter';color:#D9D4CF;margin-top:10px;position:relative;z-index:1}
.sec{display:flex;align-items:baseline;gap:14px;padding:28px 44px 10px}
.sec h2{font:800 30px 'Inter';letter-spacing:-.01em}
.sec .cnt{font:700 15px 'Inter';color:#fff;background:#C8102E;border-radius:6px;padding:3px 9px}
.sec .hint{font:600 15px 'Inter';color:#77706A;margin-left:auto}
.foot{display:flex;justify-content:space-between;padding:24px 48px 0;font:600 15px 'Inter';color:#77706A}
.foot b{color:#C8102E}
.note{padding:12px 48px 0;font:500 15px/1.4 'Inter';color:#5E5853}
table{border-collapse:separate;border-spacing:0 6px;width:100%}
.tbl{padding:0 32px}
th{font:700 12.5px 'Inter';letter-spacing:.12em;text-transform:uppercase;color:#77706A;text-align:right;padding:4px 12px}
th.l,td.l{text-align:left}
td{background:#fff;font:600 18px 'Inter';font-variant-numeric:tabular-nums;text-align:right;padding:0 12px;height:52px;white-space:nowrap}
td:first-child{border-radius:10px 0 0 10px;border-left:6px solid #C8102E}
td:last-child{border-radius:0 10px 10px 0}
.mu{font:700 18px 'Inter'}
.mu small{font:600 14px 'Inter';color:#8C857F;margin:0 5px}
.pk{font:800 18px 'Inter';color:#C8102E}
.pos{color:#1E7A3C}.neg{color:#B3261E}
.rkb{display:inline-block;font:700 12.5px 'Inter';color:#8C857F;margin-right:5px;font-variant-numeric:tabular-nums}
.top2{display:grid;grid-template-columns:1fr 1fr;column-gap:20px;padding:0 32px}
.rr{display:flex;align-items:center;height:54px;background:#fff;border-radius:10px;margin:6px 0;padding:0 14px}
.rr .n{width:42px;height:36px;border-radius:8px;background:#141414;color:#fff;font:800 18px 'Inter';display:flex;align-items:center;justify-content:center;flex:none}
.rr.t1 .n{background:#C8102E}
.rr .tm{flex:1;padding-left:14px;min-width:0}
.rr .tm b{display:block;font:700 20px 'Inter';white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.rr .tm span{font:600 13px 'Inter';color:#8C857F;letter-spacing:.04em}
.rr .v{font:800 22px 'Inter';font-variant-numeric:tabular-nums}
/* watch */
.slot{margin:22px 32px 0;background:#141414;border-radius:18px;padding:18px 18px 18px}
.slot .sh{display:flex;align-items:baseline;justify-content:space-between;padding:0 6px 14px}
.slot .sh b{font:800 26px 'Inter';color:#fff;letter-spacing:-.01em}
.slot .sh span{font:700 14px 'Inter';letter-spacing:.14em;text-transform:uppercase;color:#E8A0AC}
.quad{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.gc{background:#fff;border-radius:12px;padding:14px 16px 14px;position:relative;min-height:150px}
.gc .tg{display:inline-block;font:800 11.5px 'Inter';letter-spacing:.12em;text-transform:uppercase;border-radius:5px;padding:3px 7px}
.gc .tg.p5{background:#C8102E;color:#fff}.gc .tg.mid{background:#141414;color:#fff}.gc .tg.low{background:#E4DED8;color:#141414}
.gc .tt{font:700 13px 'Inter';color:#8C857F;margin-left:8px}
.gc .ws{position:absolute;right:16px;top:12px;text-align:right}
.gc .ws b{display:block;font:800 34px/1 'Inter';color:#C8102E;font-variant-numeric:tabular-nums}
.gc .ws span{font:700 10.5px 'Inter';letter-spacing:.14em;color:#8C857F}
.gc .tms{margin-top:14px}
.gc .tml{display:flex;align-items:baseline;font:700 21px/1.25 'Inter';white-space:nowrap;overflow:hidden}
.gc .tml .tn{overflow:hidden;text-overflow:ellipsis}
.gc .at{font:600 13px 'Inter';color:#8C857F;margin:1px 0 1px 2px}
.gc .ln{margin-top:8px;font:600 14px 'Inter';color:#5E5853}
.tg2 td{height:64px;font-size:17px;padding:0 9px}
.tg2 td.stack{white-space:normal;line-height:1.25;font-size:17px;max-width:330px;padding-top:6px;padding-bottom:6px}
.tg2 td.stack small{margin:0 4px 0 0}
.tg2 td.wrap{white-space:normal;max-width:220px;line-height:1.2;font-size:16.5px}
.empty{grid-column:1/-1;color:#B9B2AC;font:600 16px 'Inter';padding:18px 8px}
"""

def page(kicker, title, body, sub, note="", foot_right=""):
    return f"""<html><head><meta charset=utf-8><style>{CSS}</style></head><body><div class=card id=card>
<div class=hdr><div class=kick>{kicker}</div><div class=title>{title}</div><div class=sub>{sub}</div></div>
{body}
{f'<div class=note>{note}</div>' if note else ''}
<div class=foot><span><b>MODEL RATINGS</b> · College Basketball</span><span>{foot_right or html.escape(DATE_LABEL)}</span></div>
</div></body></html>"""

pages = []

# ---------- 1) Trigger games + Top 20 ----------
def et_tip(iso):
    try:
        t = datetime.datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(ET)
        return t, t.strftime("%-I:%M %p ET")
    except Exception:
        return None, "TBD"
def num(s):
    try: return float(str(s).replace("+", ""))
    except: return 0.0
rows = []
for p in trig:
    _, tl = et_tip(p.get("Start", ""))
    sep = "vs" if p.get("Neutral") == "Y" else "@"
    sp = num(p["Spread"]); ed = num(p["Edge"])
    spd = "PK" if sp == 0 else f"{sp:+g}"
    cls = "pos" if ed > 0 else ("neg" if ed < 0 else "")
    rows.append(f"""<tr class=tg2><td class="l mu stack">{html.escape(p['Away'])}<br><small>{sep}</small>{html.escape(p['Home'])}</td>
<td>{tl}</td><td>{spd}</td><td>{num(p['Model Prediction']):+.1f}</td><td class={cls}>{ed:+.1f}</td><td>{float(p['Confidence']):.3f}</td>
<td class="l pk wrap">{html.escape(p['ATS Pick'])}{('<br><small style="font:700 12.5px Inter;color:#8C857F;letter-spacing:.06em">' + p['_level'].upper() + ' SIGNAL · ' + f"{p['_gap']:g}" + '</small>') if '_level' in p else ''}</td></tr>""")
if rows:
    tbody = f"""<div class=tbl><table><tr><th class=l>Matchup</th><th>Tip</th><th>Spread</th><th>Model</th><th>Edge</th><th>Conf</th><th class=l>Pick</th></tr>{''.join(rows)}</table></div>"""
else:
    tbody = "<div class=note style='padding:6px 48px 0'>No games today.</div>"
t1 = f"<div class=sec><h2>{MODE_TXT[0]}</h2><span class=cnt>{len(rows)}</span><span class=hint>Spread = home team · Conf = home cover confidence</span></div>{tbody}"
tops = sorted(top, key=lambda r: int(r["Rank"]))[:20]
def rrow(r):
    return f"""<div class="rr{' t1' if r['Rank']=='1' else ''}"><div class=n>{r['Rank']}</div><div class=tm><b>{html.escape(r['Team'])}</b><span>{html.escape(r['Conf'])}</span></div><div class=v>{float(r['John']):.2f}</div></div>"""
t2 = f"""<div class=sec style='padding-top:34px'><h2>Top 20 Power Ratings</h2><span class=hint>John rating</span></div>
<div class=top2><div>{''.join(rrow(r) for r in tops[:10])}</div><div>{''.join(rrow(r) for r in tops[10:20])}</div></div>"""
pages.append((f"cbb_{TAG}_1_picks_top20", page("Daily Card · John Model", MODE_TXT[1], t1 + t2,
    sub=LONG_DATE, note=MODE_TXT[2])))

# ---------- 2) Watchability ----------
if DOW == "Sat":
    SLOTS = [("Early Slate", "Before 2:00 PM ET", 0, 14*60), ("Afternoon Slate", "2:00 – 5:59 PM ET", 14*60, 18*60),
             ("Evening Slate", "6:00 – 8:59 PM ET", 18*60, 21*60), ("Late Slate", "9:00 PM ET or later", 21*60, 24*60+1)]
else:
    SLOTS = [("Early Slate", "Before 9:00 PM ET", 0, 21*60), ("Late Slate", "9:00 PM ET or later", 21*60, 24*60+1)]
WANT = [("P5", 2), ("MID", 1), ("LOW", 1)]
def gcard(g):
    tl, tc = TIER[g["tier"]]
    sep = "vs" if g["neutral"] == "Y" else "at"
    return f"""<div class=gc><span class="tg {tc}">{tl}</span><span class=tt>{tip_label(g['start'])}</span>
<div class=ws><b>{score(g):g}</b><span>WATCH</span></div>
<div class=tms><div class=tml>{team_html(g['away'], g['arank'])}</div><div class=at>{sep}</div><div class=tml>{team_html(g['home'], g['hrank'])}</div></div>
<div class=ln>{html.escape(fav_line(g))}</div></div>"""
body = ""
slot_summary = []
for name, rng, lo, hi in SLOTS:
    inslot = [g for g in watch if (m := tip_minutes(g["start"])) is not None and lo <= m < hi]
    picks = []
    for tier, n in WANT:
        picks += sorted([g for g in inslot if g["tier"] == tier], key=lambda g: -score(g))[:n]
    slot_summary.append((name, len(picks)))
    inner = "".join(gcard(g) for g in picks) or "<div class=empty>No games in this window.</div>"
    body += f"<div class=slot><div class=sh><b>{name}</b><span>{rng}</span></div><div class=quad>{inner}</div></div>"
top10 = sorted(watch, key=lambda g: -score(g))[:10]
trs = "".join(f"""<tr><td class="l mu">{i}. {team_html(g['away'], g['arank'])}<small>{'vs' if g['neutral']=='Y' else '@'}</small>{team_html(g['home'], g['hrank'])}</td>
<td>{tip_label(g['start'])}</td><td class=l>{TIER[g['tier']][0]}</td><td class=l style='font-weight:600;color:#5E5853'>{html.escape(fav_line(g))}</td><td class=pk>{score(g):g}</td></tr>""" for i, g in enumerate(top10, 1))
body += f"""<div class=sec style='padding-top:34px'><h2>Top 10 by Watch Score</h2><span class=hint>All games today</span></div>
<div class=tbl><table><tr><th class=l>Matchup</th><th>Tip</th><th class=l>Tier</th><th class=l>Line</th><th>Watch</th></tr>{trs}</table></div>"""
kind = "Saturday" if DOW == "Sat" else ("Sunday" if DOW == "Sun" else "Weekday")
pages.append((f"cbb_{TAG}_2_watch_recs", page(f"Watchability Recs · {kind} Slates", "What to Watch", body,
    sub=LONG_DATE + " · Each slate: best 2 Power 5, best Mid Major, best Low Major",
    note="Watch Score from the Watch Recs tab. Tiers: Power 5 = ACC, Big Ten, Big 12, Big East, SEC; Mid Major = Pac-12, AAC, A-10, Mountain West, WCC, MVC, MAC, CUSA, Big West; a game takes the higher tier of its two teams.")))

# ---------- render ----------
with sync_playwright() as pw:
    b = pw.chromium.launch()
    pg = b.new_page(viewport={"width": 1080, "height": 1000}, device_scale_factor=2)
    for slug, h in pages:
        pg.set_content(h); pg.wait_for_timeout(150)
        pg.locator("#card").screenshot(path=f"{OUT}/{slug}.png")
        print(slug)
    b.close()
print("slots:", slot_summary, "| mode:", MODE, "| signal games:", len(sig_games), "| rows:", len(rows), "| games:", len(watch))

# ================= SUMMARY =================
_now = datetime.datetime.now(ZoneInfo("America/New_York"))
_cnt = dict(kv.split("=", 1) for kv in EXTRACT_LINE.split() if "=" in kv)
_issues = []
if ISO != _now.strftime("%Y-%m-%d"): _issues.append(f"site date {ISO or 'blank'} is not today ({_now:%Y-%m-%d} ET)")
try:
    _fu = datetime.datetime.fromisoformat(meta.get("FeedUpdated", "").replace("Z", "+00:00"))
    _age = (_now - _fu).total_seconds() / 3600
    if _age > 24: _issues.append(f"feed last updated {_age:.0f}h ago")
except Exception: _issues.append("feed update time unreadable")
if len(watch_raw) != int(_cnt.get("watch", -1)): _issues.append("watch row count mismatch")
if len(top) != 20: _issues.append(f"top-20 has {len(top)} rows")
_tw = top10[0] if top10 else None
print("SUMMARY " + json.dumps({
    "date": LONG_DATE, "mode": MODE, "graphic1_rows": len(rows), "signal_games": len(sig_games),
    "trigger_games": len(table("TRIG")), "games": len(watch),
    "top_watch": (f"{_tw['away']} @ {_tw['home']}, {tip_label(_tw['start'])}, {score(_tw):g}" if _tw else None),
    "short_slates": [f"{n} ({c})" for n, c in slot_summary if c < 4],
    "feed_updated": meta.get("FeedUpdated"), "issues": _issues,
    "files": sorted(os.path.join(OUT, f) for f in os.listdir(OUT) if f.startswith(f"cbb_{TAG}"))}))
