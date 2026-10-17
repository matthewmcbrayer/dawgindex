#!/usr/bin/env python3
"""Checks for Original Investigation cases (LAB 001: tougher half vs. easier half of a schedule).

  python3 _editorial/test_lab_oi.py DRAFT_DIR [RESEARCH_FINAL_DIR]

DRAFT_DIR is an Original Investigation draft (case.json, case.md, data.json, explorer.json). RESEARCH_FINAL_DIR, when
given, holds the independently reproduced research numbers (final_numbers.json, ex2_common.json and, beside it,
../repro/repro_out.json); the exhibits must match them. Renders a private preview in a temp folder; writes nothing else.
"""
import copy, json, mimetypes, os, re, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.dont_write_bytecode = True
import build as B
import lab as L

DRAFT = os.path.abspath(sys.argv[1]); RES = os.path.abspath(sys.argv[2]) if len(sys.argv) > 2 else None
RESULTS = []
def check(ok, name, detail=""):
    RESULTS.append(bool(ok)); print(("PASS  " if ok else "FAIL  ") + name + (f"  ({detail})" if detail and not ok else ""), flush=True)

site = B.team_slugs(REPO)
case0, md0, data0, plan0 = L.load_case(DRAFT)

# ---------------------------------------------------------------- the tie rule
H = L.oi_halves
check(H([1, 2, 3, 4]) == ["t", "t", "e", "e"], "halves: even schedule splits in two")
check(H([5, 1, 3]) == ["e", "t", "x"], "halves: odd schedule leaves the middle game out")
check(H([1, 2, 2, 4]) == ["t", "x", "x", "e"], "halves: games tied across the halfway line count in neither half")
check(H([1, 3, 3, 3, 9]) == ["t", "x", "x", "x", "e"], "halves: a tie with the middle game takes every tied game out")
check(H([1, 1, 3, 9]) == ["t", "t", "e", "e"], "halves: ties inside one half stay in it")

# ---------------------------------------------------------------- validation
clean = L.validate(copy.deepcopy(case0), md0, data0, plan0, DRAFT, site, "preview")
check(not clean, "the draft passes every preview check", "; ".join(clean[:5]))
def neg(name, expect, c=None, md=None, d=None, mode="preview"):
    e = L.validate(c if c is not None else copy.deepcopy(case0), md if md is not None else md0, d if d is not None else copy.deepcopy(data0), "", DRAFT, site, mode)
    check(any(expect in x for x in e), f"refused: {name}", "; ".join(e[:3]) or "no error")
c = copy.deepcopy(case0); c["verdict"] = {"kind": "inconclusive"}; neg("a verdict on an Original Investigation", "has no verdict", c)
for w in ("Inconclusive", "Doesn’t Hold Up", "Myth Busted", "Proven False"):
    neg(f"'{w}' in the copy", "verdict language", md=md0 + f"\nThe answer: {w}.\n")
c = copy.deepcopy(case0); c["checks"] = "Checked twice."; neg("no exploratory / reproduction disclosure", "exploratory", c)
c = copy.deepcopy(case0); del c["scope_change"]; neg("no scope-change record", "scope_change", c)
c = copy.deepcopy(case0); c["research_datasets"][0]["label"] = ""; neg("research grades without their label", "research dataset needs label", c)
neg("an exhibit marker missing", "[[reveal]] exactly once", md=md0.replace("[[reveal]]", ""))
neg("an unknown exhibit marker", "unknown exhibit markers", md=md0 + "\n[[bound]]\n")
neg("a size published as ruled out", "ruled out", md=md0 + "\nHabits over 2 points are ruled out.\n")
c = copy.deepcopy(case0); c["card_line"] = "x" * 91; neg("a card line too long for the link preview", "card_line", c)
d = copy.deepcopy(data0); d["illusion"]["tougher"] += 0.1; neg("Exhibit 1 numbers that don't match the games", "Exhibit 1 tougher", d=d)
d = copy.deepcopy(data0); d["reveal"]["opponent"]["gap"] = 0.5; neg("a gap that isn't tougher minus easier", "gap must equal", d=d)
d = copy.deepcopy(data0); d["reveal"]["spread"]["ci"] = [2.5, 3.0]; neg("an interval that misses its estimate", "interval must contain", d=d)
d = copy.deepcopy(data0); d["explorer_sha256"] = "sha256:0"; neg("explorer.json swapped after data.json was written", "hash mismatch", d=d)
d = copy.deepcopy(data0); slug = next(iter(d["_explorer"]["teams"])); del d["_explorer"]["teams"][slug]; neg("a program missing from the explorer", "must cover all", d=d)
d = copy.deepcopy(data0); t = d["_explorer"]["teams"]["baylor"]["seasons"]["2025"]; t["g"][0][5] = {"t": "e", "e": "t", "x": "t"}[t["g"][0][5]]; neg("halves that break the tie rule", "tie rule", d=d)
d = copy.deepcopy(data0); d["_explorer"]["teams"]["baylor"]["seasons"]["2025"]["T"][2] += 1; neg("a half average that doesn't match its games", "half summaries", d=d)
d = copy.deepcopy(data0); d["_explorer"]["teams"]["baylor"]["seasons"]["2026"]["gap"] = 1.0; neg("halves shown below the 8-game minimum", "below the minimum", d=d)
c = copy.deepcopy(case0); neg("publishing without approval on record", "approved_by", c, mode="publish")

# ---------------------------------------------------------------- the exhibits match the research (independently reproduced)
if RES:
    FN = json.load(open(os.path.join(RES, "final_numbers.json"))); E2 = json.load(open(os.path.join(RES, "ex2_common.json")))
    RP = json.load(open(os.path.join(os.path.dirname(RES), "repro", "repro_out.json")))
    il, rv = data0["illusion"], data0["reveal"]
    check(all(il[k] == FN["ex1"][k] for k in ("team_seasons", "tougher", "easier", "gap", "ci", "spread_apart", "by_season")), "Exhibit 1 = final_numbers.json exactly")
    check(rv["team_seasons"] == E2["common_team_seasons"] and rv["spread"] == E2["spread"] and rv["opponent"] == E2["opponent_pregame_strength"]
          and rv["spread_home_removed"] == E2["spread_home_edge_removed"], "Exhibit 2 = ex2_common.json exactly")
    RC = json.load(open(os.path.join(os.path.dirname(RES), "repro", "repro_common.json")))
    flatc = json.dumps(RC)
    numsc = [float(x) for x in re.findall(r"-?\d+\.\d+", flatc)]
    near = lambda v, tol=0.015: any(abs(v - x) <= tol for x in numsc)
    s1 = RP["s1"]
    check(abs(s1["tough"] - il["tougher"]) < 0.006 and abs(s1["easy"] - il["easier"]) < 0.006 and abs(s1["gap"] - il["gap"]) < 0.015 and s1["n"] == il["team_seasons"],
          "Exhibit 1 agrees with the independent reproduction", str(s1))
    check(all(near(v) for v in il["by_season"].values()), "Exhibit 1 season gaps agree with the independent reproduction (tie rule at both boundaries)")
    check(str(rv["team_seasons"]) in flatc and all(near(rv[k][f]) for k in ("spread", "opponent") for f in ("tougher", "easier", "gap"))
          and abs(rv["spread_home_removed"]["gap"] - 1.75) < 0.015, "Exhibit 2 agrees with the independent reproduction on the same 727 team-seasons")
    shown = lambda v: L.fmt(v)
    check(shown(rv["spread"]["gap"]) == "+2.3" and shown(rv["opponent"]["gap"]) == "−0.4" and shown(rv["spread_home_removed"]["gap"]) == "+1.8" and shown(il["gap"]) == "+2.0",
          "every displayed headline number rounds the same from the final and the reproduced values")

# ---------------------------------------------------------------- every number in the article traces to the data
EXd = data0["_explorer"]
def tsx(slug, y): return EXd["teams"][slug]["seasons"][str(y)]
ok_md = []
ok_md.append(f"{L.fmt(data0['illusion']['tougher'])} against the tougher half, {L.fmt(data0['illusion']['easier'])} against the easier half" in md0)
ok_md.append(f"about {round(data0['illusion']['spread_apart'])} points of spread apart" in md0)
ok_md.append(f"a difference of {L.fmt(data0['reveal']['opponent']['gap'])} points" in md0)
ok_md.append(f"{data0['variation']['beyond_95_pct']:.0f}% land" in md0)
ok_md.append(f"+{tsx('california', 2025)['T'][2]:.1f} against its tougher half and {L.fmt(tsx('california', 2025)['E'][2])} against its easier half" in md0)
vb = tsx("vanderbilt", 2024); ok_md.append(f"it graded {L.fmt(vb['T'][2])}; across its five easiest, {L.fmt(vb['E'][2])}" in md0 and vb["T"][0] == 5 and vb["E"][0] == 5)
bama = [g for g in vb["g"] if EXd["opps"][g[1]] == "Alabama"][0]; ok_md.append(f"a {L.fmt(bama[3])} grade" in md0 and abs(bama[2]) == 22.5)
mi = tsx("miami", 2019); ok_md.append(round(mi["T"][2]) == 9 and round(-mi["E"][2]) == 18 and round(mi["E"][1]) == 22 and abs(mi["T"][1]) < 0.5)
md21 = tsx("maryland", 2021); ok_md.append(round(-md21["T"][2]) == 16 and round(md21["E"][2]) == 8)
ok_md.append(sum(len(t["g"]) for tm in EXd["teams"].values() for t in tm["seasons"].values()) == 9857 and "9,857 team-games" in md0)
check(all(ok_md), "every figure in the article matches the exhibit data and the explorer's games", str(ok_md))

# ---------------------------------------------------------------- rendered pages
tmp = tempfile.mkdtemp(prefix="labOI-")
L.preview(REPO, DRAFT, out_root=tmp, shots=False, cards=True, look="production")
P = os.path.join(tmp, "lab", f"{case0['number']}-{case0['slug']}")
page = open(os.path.join(P, "index.html")).read()
text = re.sub(r"<script.*?</script>", " ", page, flags=re.S); text = re.sub(r"<[^>]+>", " ", text)
check("DAWG Lab</a> / Original Investigation / 001" in page, "cover identifies the case as DAWG Lab / Original Investigation / 001")
check("lb-stamp" not in page and not L.OI_FORBIDDEN.search(text), "no verdict stamp and no verdict words on the page")
check(all(f'id="{i}"' in page for i in ("lb-ex-illusion", "lb-ex-reveal", "your-team")) and "Exhibit 1 ·" in page and "Exhibit 2 ·" in page and "Exhibit 3 ·" in page,
      "three numbered exhibits in order")
check("How we did it" in page and "What this doesn" in page, "methodology and limitations below the article")
check(case0["checks"].split(":")[0] in text and "independently" in text and "LAB 001 started as a different question" in text,
      "receipts carry the exploratory / reproduction disclosure and the scope change")
check(text.count("not official DAWG grades") >= 3, "2014–18 grades labeled as research grades, not official, wherever they're used")
check("/plan/" not in page and not os.path.exists(os.path.join(P, "plan")), "no research-plan page for an Original Investigation")
ex_pub = open(os.path.join(P, "explorer.json")).read()
check(ex_pub == data0["_explorer_raw"], "explorer.json published byte for byte")
sm = open(os.path.join(tmp, "lab", "sitemap.xml")).read(); man = json.load(open(os.path.join(tmp, "lab", "lab.json")))
check("/plan/" not in sm and man["cases"][0]["type"] == "original-investigation" and man["cases"][0]["verdict"] is None, "sitemap and manifest have no plan or verdict")
home = open(os.path.join(tmp, "lab", "index.html")).read()
check("plan is written before the results" not in home and "Original Investigation" in home, "Lab home doesn't claim a pre-written plan for this case")
check(os.path.isfile(os.path.join(P, "card.png")) and os.path.isfile(os.path.join(P, "og.png")), "share card and link preview rendered")

# ---------------------------------------------------------------- browser
from playwright.sync_api import sync_playwright
import requests
S = requests.Session(); CA = "/root/.ccr/ca-bundle.crt"; S.verify = CA if os.path.exists(CA) else True
cache = {}
def route(r):
    u = r.request.url
    if u.startswith("https://site.local/"):
        path = u.split("https://site.local/", 1)[1].split("?")[0].split("#")[0]
        if path == "" or path.endswith("/"): path += "index.html"
        for root in ((tmp,) if path.startswith("lab/") else (REPO,)):
            f = os.path.join(root, path)
            if os.path.isfile(f):
                return r.fulfill(status=200, body=open(f, "rb").read(), headers={"content-type": mimetypes.guess_type(f)[0] or "application/octet-stream"})
        return r.fulfill(status=404, body=b"")
    if "fonts.g" in u:
        if u not in cache:
            x = S.get(u, headers={"User-Agent": r.request.headers.get("user-agent", "")}, timeout=30); cache[u] = (x.status_code, x.content, x.headers.get("content-type", ""))
        st, b, ct = cache[u]; return r.fulfill(status=st, body=b, headers={"content-type": ct})
    return r.fulfill(status=404, body=b"")
f1 = L.fmt
EX = data0["_explorer"]
URL = f"https://site.local/lab/{case0['number']}-{case0['slug']}/"
with sync_playwright() as p:
    b = p.chromium.launch()
    for w, h in ((360, 780), (390, 844), (1440, 900)):
        mob = w < 600
        ctx = b.new_context(viewport={"width": w, "height": h}, is_mobile=mob, has_touch=mob); ctx.route("**/*", route); pg = ctx.new_page()
        errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(URL, wait_until="load"); pg.wait_for_function("document.body.getAttribute('data-ready')==='1'", timeout=20000)
        sw = pg.evaluate("document.documentElement.scrollWidth")
        check(sw <= w and not errs, f"case page at {w}px: no sideways scroll, no script errors", f"{sw}px; {errs[:2]}")
        t1 = pg.evaluate("[...document.querySelectorAll('#lb-illusion text')].map(t=>t.textContent)")
        il = data0["illusion"]
        check(f1(il["tougher"]) in t1 and f1(il["easier"]) in t1 and f1(il["gap"]) in pg.inner_text("#lb-illusion"), f"Exhibit 1 at {w}px shows the data's numbers", str(t1))
        ts = pg.evaluate("[...document.querySelectorAll('#lb-seasons text')].map(t=>t.textContent)")
        want = [f1(v) if not mob else f1(v).replace("+", "") for _, v in sorted(il["by_season"].items())]
        check(all(x in ts for x in want), f"Exhibit 1 season bars at {w}px match the data", f"{want} vs {ts}")
        check("Research grades" in ts, f"Exhibit 1 at {w}px: the 2014–18 bars are bracketed as research grades")
        t2 = pg.evaluate("[...document.querySelectorAll('#lb-reveal text')].map(t=>t.textContent)")
        rv = data0["reveal"]
        check(f1(rv["spread"]["gap"]) in t2 and f1(rv["opponent"]["gap"]) in t2 and (mob or any(f1(rv["opponent"]["tougher"]) in x for x in t2)), f"Exhibit 2 at {w}px shows the data's numbers", str(t2))
        small = pg.evaluate("Math.min(...[...document.querySelectorAll('#lb-reveal text,#lb-illusion text,#lb-seasons text')].map(t=>parseFloat(getComputedStyle(t).fontSize)))")
        check(small >= 11, f"exhibit labels at {w}px are at least 11px", str(small))
        # explorer: Vanderbilt 2024 (select, like a reader), then a tap on a game
        pg.select_option("#lb-xp-team", "vanderbilt"); pg.select_option("#lb-xp-season", "2024"); pg.wait_for_timeout(100)
        ts24 = EX["teams"]["vanderbilt"]["seasons"]["2024"]
        lead = pg.inner_text("#lb-xp-lead")
        check(f1(ts24["T"][2]) in lead and f1(ts24["E"][2]) in lead and f"{abs(ts24['gap']):.1f} points better" in lead and f"{ts24['T'][0]} games" in lead,
              f"explorer at {w}px: Vanderbilt 2024 rows match its games", lead[:160])
        nd = pg.evaluate("document.querySelectorAll('#lb-xp-chart circle[role=button]').length"); nh = pg.evaluate("[...document.querySelectorAll('#lb-xp-chart circle:not([role])')].filter(c=>c.getAttribute('fill')==='#FBF4E2').length")
        check(nd == ts24["n"] and nh == sum(1 for g in ts24["g"] if g[5] == "x"), f"explorer at {w}px: one dot per game, excluded games hollow", f"{nd} dots, {nh} hollow")
        pos = pg.evaluate("(()=>{const c=document.querySelector('#lb-xp-chart circle[role=button]'),s=c.ownerSVGElement,b=s.getBoundingClientRect(),k=b.width/s.viewBox.baseVal.width;return {x:+c.getAttribute('cx')*k,y:+c.getAttribute('cy')*k}})()")
        layer = pg.locator("#lb-xp-chart rect[data-tap]")
        (layer.tap(position=pos) if mob else layer.click(position=pos)); pg.wait_for_timeout(80)
        check(pg.is_visible("#lb-xp-tap") and "DAWG" in pg.inner_text("#lb-xp-tap"), f"explorer at {w}px: tapping a dot shows the game")
        check("team=vanderbilt" in pg.url and "season=2024" in pg.url, f"explorer at {w}px: the link keeps team and season")
        pg.select_option("#lb-xp-season", "2016"); pg.wait_for_timeout(60)
        check("research grades" in pg.inner_text("#lb-xp-lead"), f"explorer at {w}px: a 2014–18 season says research grades")
        opts = pg.evaluate("[...document.querySelectorAll('#lb-xp-season option')].map(o=>[o.value,o.textContent])")
        check(opts and all(("research grades" in t) == (int(v) <= 2018) for v, t in opts), f"explorer at {w}px: the season menu marks 2014–18 as research grades, and only those", str(opts))
        pg.select_option("#lb-xp-team", "baylor"); pg.select_option("#lb-xp-season", "2026"); pg.wait_for_timeout(60)
        check("needs at least 8 games" in pg.inner_text("#lb-xp-lead") and pg.evaluate("document.querySelectorAll('#lb-xp-chart circle[role=button]').length") == EX["teams"]["baylor"]["seasons"]["2026"]["n"],
              f"explorer at {w}px: a short season shows its games without halves")
        sw = pg.evaluate("document.documentElement.scrollWidth")
        check(sw <= w and not errs, f"after exploring at {w}px: no sideways scroll, no script errors", f"{sw}px; {errs[:2]}")
        XPF = "(()=>{const s=document.querySelector('#lb-xp-chart svg'),b=s.getBoundingClientRect(),k=b.width/s.viewBox.baseVal.width;return Math.min(...[...s.querySelectorAll('text')].map(t=>parseFloat(getComputedStyle(t).fontSize)*k))})()"
        check(pg.evaluate(XPF) >= 11, f"explorer chart at {w}px: labels at least 11px on screen", str(pg.evaluate(XPF)))
        # a team link opens straight to the chart: it must be drawn at the real column width, not shrunk
        pg.goto(URL + "?team=vanderbilt&season=2016", wait_until="load"); pg.wait_for_function("document.body.getAttribute('data-ready')==='1'", timeout=20000)
        fs = pg.evaluate(XPF); sw = pg.evaluate("document.documentElement.scrollWidth")
        check(fs >= 11 and sw <= w and not errs and pg.input_value("#lb-xp-season") == "2016", f"team link at {w}px: the explorer opens to the season with full-size chart labels", f"{fs}px, {sw}px wide, {errs[:2]}")
        if w in (360, 1440):
            # every team-season's chart: no two labels overlap, none cut off at the edges
            clash = pg.evaluate("""(EX) => { const out = [];
              for (const s in EX.teams) for (const y in EX.teams[s].seasons) { window.DAWGLabOI.show(s, y);
                const svg = document.querySelector('#lb-xp-chart svg'), W = svg.viewBox.baseVal.width;
                const bx = [...svg.querySelectorAll('text')].map(t => [t.textContent, t.getBBox()]);
                for (const [n, b] of bx) if (b.x < -0.5 || b.x + b.width > W + 0.5) out.push(s + ' ' + y + ' cut: ' + n);
                for (let i = 0; i < bx.length; i++) for (let j = i + 1; j < bx.length; j++) { const a = bx[i][1], c = bx[j][1];
                  if (a.x < c.x + c.width - 0.5 && c.x < a.x + a.width - 0.5 && a.y < c.y + c.height - 0.5 && c.y < a.y + a.height - 0.5) out.push(s + ' ' + y + ': ' + bx[i][0] + ' / ' + bx[j][0]); } }
              return out; }""", EX)
            check(not clash, f"explorer at {w}px: no overlapping or cut-off chart labels in any team-season", f"{len(clash)}: {clash[:6]}")
        if w == 1440:
            # every team-season, through the page's own renderer
            bad = pg.evaluate("""(EX) => { const out = []; const f = v => { const m = Math.abs(v).toFixed(1); return (m === '0.0' ? '' : v > 0 ? '+' : '−') + m; };
              for (const s in EX.teams) for (const y in EX.teams[s].seasons) { const ts = EX.teams[s].seasons[y]; window.DAWGLabOI.show(s, y);
                const lead = document.getElementById('lb-xp-lead').innerText, dots = document.querySelectorAll('#lb-xp-chart circle[role=button]').length;
                if (dots !== ts.n) out.push(s + ' ' + y + ' dots');
                if (ts.T && (!lead.includes(f(ts.T[2])) || !lead.includes(f(ts.E[2])))) out.push(s + ' ' + y + ' lead');
                if (!ts.T && !lead.includes('at least 8')) out.push(s + ' ' + y + ' short');
                if (lead.includes('research grades') !== (+y <= 2018)) out.push(s + ' ' + y + ' research label'); }
              return out; }""", EX)
            nts = sum(len(t["seasons"]) for t in EX["teams"].values())
            check(not bad and not errs, f"all {nts} team-seasons render with the right rows and one dot per game", str(bad[:5]))
        ctx.close()
    # Lab home: the team picker goes to the explorer
    ctx = b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True); ctx.route("**/*", route); pg = ctx.new_page()
    errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto("https://site.local/lab/", wait_until="load"); pg.wait_for_function("document.body.getAttribute('data-ready')==='1'", timeout=20000)
    pg.select_option("#lb-home-pick", "baylor")
    href = pg.get_attribute("#lb-home-link", "href")
    check(href.endswith("?team=baylor#your-team") and not errs and pg.evaluate("document.documentElement.scrollWidth") <= 390, "Lab home at 390px: picking a team links to its seasons", href)
    pg.goto(URL + "?team=baylor#your-team", wait_until="load"); pg.wait_for_function("document.body.getAttribute('data-ready')==='1'", timeout=20000)
    check(pg.input_value("#lb-xp-team") == "baylor" and pg.input_value("#lb-xp-season") == "2025", "a ?team= link opens the explorer on that team's latest full season")
    ctx.close(); b.close()

n = len(RESULTS); print(f"\n{sum(RESULTS)} of {n} checks passed")
sys.exit(0 if all(RESULTS) else 1)
