#!/usr/bin/env python3
"""Tests for the DAWG Lab build (_editorial/lab.py). Every scenario runs on a throwaway copy of the repo; the real repo is
only read. The published-case scenarios use a test fixture made from the SAMPLE case with its sample markings swapped
for test text, so it can pass the publish checks inside the copy. Its numbers are random, not research.

  python3 _editorial/test_lab.py            (needs Playwright + Chromium: cards, redirects and layouts are rendered)
"""
import copy, html, json, mimetypes, os, re, shutil, subprocess, sys, tempfile, xml.dom.minidom
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True
import build as B
import lab as L

RESULTS = []
def check(ok, name, detail=""):
    RESULTS.append((bool(ok), name, detail)); print(("PASS  " if ok else "FAIL  ") + name + (f"  ({detail})" if detail and not ok else ""), flush=True)

def copy_repo():
    dst = os.path.join(tempfile.mkdtemp(prefix="labtest-"), "repo")
    shutil.copytree(REPO, dst, ignore=shutil.ignore_patterns(".git", "__pycache__", "lab"))
    # the ignore above also skips templates/lab; put it back
    shutil.copytree(os.path.join(REPO, "_editorial", "templates", "lab"), os.path.join(dst, "_editorial", "templates", "lab"))
    return dst

def run(repo, *args):
    p = subprocess.run([sys.executable, os.path.join(repo, "_editorial", "lab.py"), *args, "--repo", repo], capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr

def rd(p): return open(p, encoding="utf-8").read()
def wj(p, o): open(p, "w").write(json.dumps(o, ensure_ascii=False, indent=1) + "\n")


def make_fixture(root):
    """The SAMPLE case with sample markings replaced by neutral test text (still random numbers)."""
    L.sample(REPO, root)
    d = os.path.join(root, "001-playing-down")
    c = json.loads(rd(os.path.join(d, "case.json")))
    c["sample"] = False
    c["verdict"].update(subtitle="Reason set in the plan", answer="Test answer: one plain sentence for the test suite.", card_line="Test line for the link preview.")
    c["verdict_record"] = "Test verdict record for the suite."
    c["second_check"] = "Rerun independently for the test suite"
    c["data_lock"]["snapshot"] = "sha256:test00000000000000000000"
    c["research_datasets"][0]["provenance"] = "Test provenance line for the suite."
    wj(os.path.join(d, "case.json"), c)
    data = json.loads(rd(os.path.join(d, "data.json")))
    data["sample"] = False
    wj(os.path.join(d, "data.json"), data)
    md = rd(os.path.join(d, "case.md")).replace("Sample text.", "Test text.").replace("Sample: the limits", "Test: the limits")
    open(os.path.join(d, "case.md"), "w").write(md)
    open(os.path.join(d, "plan.md"), "w").write("## Test plan\n\nTest text standing in for the approved research plan, published in full with its exploration disclosure.\n")
    return d


def main():
    site_teams = B.team_slugs(REPO)
    names = B.team_names(REPO, site_teams)

    # ---- 1. no empty Lab
    r = copy_repo()
    code, out = run(r, "build")
    check(code == 0 and not os.path.exists(os.path.join(r, "lab")), "with no approved case, build writes nothing (no empty Lab)", out)
    idx = rd(os.path.join(r, "stories", "index.html"))
    check('href="/lab/"' not in idx, "Stories nav has no Lab link while the Lab is unpublished")
    check(not os.path.exists(os.path.join(REPO, "lab")), "the real repo has no lab/ folder (nothing published)")

    # ---- 2. the sample can't publish
    drafts = tempfile.mkdtemp(prefix="labdrafts-")
    sd = L.sample(REPO, drafts)
    code, out = run(r, "approve", sd, "--by", "Test")
    check(code != 0 and "sample" in out and not os.path.exists(os.path.join(r, "_editorial", "lab")), "approve refuses a case marked sample", out)
    sc = json.loads(rd(os.path.join(sd, "case.json"))); sc.update(status="published", approved_by="x", approved_at="2026-10-16", published="2026-10-16")
    sm, sdat, splan = rd(os.path.join(sd, "case.md")), json.loads(rd(os.path.join(sd, "data.json"))), rd(os.path.join(sd, "plan.md"))
    errs = L.validate(copy.deepcopy(sc), sm, sdat, splan, sd, site_teams, "publish")
    check(any("marked sample" in e for e in errs) and any("sample/illustrative" in e for e in errs), "publish checks reject sample flag and sample wording", "; ".join(errs[:3]))

    # ---- 3. validation negatives (publish mode, on the clean fixture)
    fx_root = tempfile.mkdtemp(prefix="labfx-")
    fx = make_fixture(fx_root)
    base_c = json.loads(rd(os.path.join(fx, "case.json"))); base_c.update(status="published", approved_by="Test", approved_at="2026-10-16", published="2026-10-16")
    base_md, base_d, base_p = rd(os.path.join(fx, "case.md")), json.loads(rd(os.path.join(fx, "data.json"))), rd(os.path.join(fx, "plan.md"))
    clean = L.validate(copy.deepcopy(base_c), base_md, base_d, base_p, fx, site_teams, "publish")
    check(not clean, "the test fixture passes every publish check", "; ".join(clean))

    def neg(name, expect, c=None, md=None, d=None, p=None):
        e = L.validate(c if c is not None else copy.deepcopy(base_c), md if md is not None else base_md,
                       d if d is not None else copy.deepcopy(base_d), p if p is not None else base_p, fx, site_teams, "publish")
        check(any(expect in x for x in e), f"refused: {name}", "; ".join(e) or "no error")
    c = copy.deepcopy(base_c); del c["plan"]["version"]; neg("no research-plan version", "plan.version", c)
    c = copy.deepcopy(base_c); c["plan"]["locked"] = ""; neg("no plan lock date", "plan.locked", c)
    neg("empty published plan", "plan.md is empty", p="  \n")
    c = copy.deepcopy(base_c); del c["data_lock"]["cutoff"]; neg("no data cutoff", "data_lock.cutoff", c)
    c = copy.deepcopy(base_c); c["methods"]["dawg"] = ""; neg("no method version", "methods.dawg", c)
    c = copy.deepcopy(base_c); c["versions"][-1]["version"] = "0.9"; neg("version history out of step", "versions must end", c)
    c = copy.deepcopy(base_c); c["corrections"] = [{"date": "2026-10-20"}]; neg("correction without text", "correction needs", c)
    c = copy.deepcopy(base_c); c["research_datasets"] = []; neg("research seasons without a research dataset", "research-only seasons", c)
    c = copy.deepcopy(base_c); c["research_datasets"][0]["label"] = ""; neg("research dataset without its label", "research dataset needs label", c)
    c = copy.deepcopy(base_c); c["verdict"]["subtitle"] = ""; neg("verdict without its plan-written subtitle", "verdict.subtitle", c)
    c = copy.deepcopy(base_c); del c["presentation"]["team_headlines"]["outside"]; neg("team headlines not written for every state", "team_headlines", c)
    c = copy.deepcopy(base_c); c["presentation"]["team_headlines"]["within"] = "{team} sits comfortably inside the expected range"; neg("team headline too long for a card", "share cards fit", c)
    c = copy.deepcopy(base_c); c["presentation"]["team_headlines"]["outside"] = "{team} plays down"; neg("team headline that claims a habit", "confirmed trait", c)
    c = copy.deepcopy(base_c); c["verdict"]["kind"] = "probably"; neg("unknown verdict", "verdict.kind", c)
    c = copy.deepcopy(base_c); c["type"] = "original-investigation"; neg("a case relabeled Original Investigation without its disclosures", "missing short_answer", c)
    c = copy.deepcopy(base_c); del c["approved_by"]; neg("no approval on record", "approved_by", c)
    d = copy.deepcopy(base_d); d["teams"]["not-a-team"] = d["teams"]["baylor"]; neg("unknown team slug", "unknown team slug", d=d)
    d = copy.deepcopy(base_d); del d["teams"]["baylor"]["groups"][0]["n"]; neg("team row without a sample size", "sample size", d=d)
    d = copy.deepcopy(base_d); del d["teams"]["baylor"]["range_lo"]; neg("a program meeting the minimum without its expected range", "no range_lo", d=d)
    d = copy.deepcopy(base_d); d["teams"]["baylor"]["outside"] = not d["teams"]["baylor"]["outside"]; neg("an outside flag that contradicts the range", "doesn't match", d=d)
    d = copy.deepcopy(base_d); d["teams"]["kansas"]["range_lo"] = -3.0; neg("an expected range shown below the display minimum", "below the display minimum", d=d)
    d = copy.deepcopy(base_d); d["teams"]["baylor"]["adjusted"] = 0.4; neg("a shrunken (adjusted) value", "approved descriptive outputs", d=d)
    d = copy.deepcopy(base_d); d["teams"]["baylor"]["down"] += 0.5; neg("a gap that isn't down part minus up part", "down part minus up part", d=d)
    d = copy.deepcopy(base_d); d["teams"]["baylor"]["groups"][1]["n"] += 1; neg("group counts that don't add up to the games", "add up to", d=d)
    d = copy.deepcopy(base_d); d["cuts"] = [{"id": "plan", "plan": True, "U": 2.4}]; neg("the retired upper-bound layout", "retired upper-bound", d=d)
    neg("a size published as ruled out", "ruled out", md=base_md + "\nHabits bigger than 2 points are ruled out.\n")
    neg("an upper-bound style ±N", "ruled out", md=base_md + "\nNothing bigger than ±0.9 per game.\n")
    d = copy.deepcopy(base_d); d["teams"]["baylor"]["finding"] = {"text": "Baylor plays down."}; neg("team finding without its criteria", "team finding needs", d=d)
    d = copy.deepcopy(base_d); [x.update(primary=True) for x in d["persistence"]]; neg("more than one main carryover estimate", "exactly one", d=d)
    c = copy.deepcopy(base_c); del c["verdict_record"]; neg("no verdict record", "verdict_record", c)
    # the descriptive tables (spec §2, §7, §8)
    G = lambda: [{"label": g["label"], "avg": 0.1, "n": 10} for g in base_d["league"]["groups"]]
    some = sorted(base_d["teams"])[:3]
    TB = {"league": [{"label": "2014–26, all games", "groups": G()}],
          "postseason": {"title": "Postseason", "label": "Postseason", "note": "Opt-outs make these less comparable.", "groups": G(), "programs": {s_: 1 for s_ in some}},
          "season2026": {"title": "2026 so far", "label": "2026", "note": "Partial season; official grades.", "groups": G(), "group_keys": ["HF", "MF", "EV", "DOG"],
                         "programs": {s_: {"HF": 1, "MF": 0, "EV": 0, "DOG": 0} for s_ in some}}}
    neg("a [[tables]] marker without the tables", "no tables", md=base_md + "\n[[tables]]\n")
    d = copy.deepcopy(base_d); d["tables"] = copy.deepcopy(TB); d["tables"]["postseason"]["note"] = "Bowl games."; neg("postseason table without the opt-out note", "opt-outs", d=d, md=base_md + "\n[[tables]]\n")
    d = copy.deepcopy(base_d); d["tables"] = copy.deepcopy(TB); d["tables"]["season2026"]["note"] = "2026 games."; neg("2026 table not labeled a partial season", "partial season", d=d, md=base_md + "\n[[tables]]\n")
    d = copy.deepcopy(base_d); d["tables"] = copy.deepcopy(TB); d["tables"]["season2026"]["programs"]["not-a-team"] = {"HF": 1}; neg("2026 table with an unknown program", "unknown program", d=d, md=base_md + "\n[[tables]]\n")
    d = copy.deepcopy(base_d); d["tables"] = copy.deepcopy(TB); d["tables"]["league"][0]["groups"][0].pop("n"); neg("league table row without its games", "games (n)", d=d, md=base_md + "\n[[tables]]\n")
    d = copy.deepcopy(base_d); d["tables"] = copy.deepcopy(TB)
    e_ = L.validate(copy.deepcopy(base_c), base_md + "\n[[tables]]\n", d, base_p, fx, site_teams, "publish")
    check(not e_, "complete tables pass", "; ".join(e_))
    if not e_:
        tms = L.derive_teams(base_c, d, B.team_ids(REPO), B.team_names(REPO, site_teams), site_teams)
        hb = L.body_html(base_c, base_md + "\n[[tables]]\n", d, tms)
        names_in = re.findall(r'<tr data-team="[^"]+"><th scope="row" class="lb-tl" data-v="([^"]+)"', hb)
        shown = [tm["name"] for tm in sorted(tms.values(), key=lambda x: x["name"]) if tm["state"] != "none"]
        check(names_in == [L.a(x) for x in shown] and "lb-sort" in hb and "Landing outside one is a description, not a finding." in hb
              and "different numbers" in hb and "too few games" in hb,
              "program table: every program with games, alphabetical, sortable, with the range wording, the gap-vs-carryover note and 'too few games' below the minimum")
    neg("unfilled [placeholder]", "placeholder", md=base_md + "\nThe gap was [X] points.\n")
    neg("'illustrative' wording", "sample/illustrative", md=base_md + "\nAn illustrative example.\n")
    neg("'2.0' in the copy", "'2.0'", md=base_md + "\nDAWG 2.0 says so.\n")
    c = copy.deepcopy(base_c); c["plan"].pop("label"); neg("plan version '2.0' with no public label", "plan.label", c)
    ok_links = L.validate(copy.deepcopy(base_c), base_md + "\nSee [the method](/#method). [[programs]]\n", copy.deepcopy(base_d), base_p, fx, site_teams, "publish")
    check(not ok_links, "markdown links and [[markers]] are not mistaken for placeholders", "; ".join(ok_links))

    # team copy stays descriptive unless a supported team finding exists
    ids = B.team_ids(REPO)
    c = copy.deepcopy(base_c); c["presentation"]["measure_short"] = "as a big favorite, which it always is"
    teams = L.derive_teams(c, base_d, ids, names, site_teams)
    te = L.team_copy_errors(teams)
    check(te and "reads as a confirmed trait" in te[0], "team text that implies a confirmed habit is refused", te[0] if te else "no error")
    teams = L.derive_teams(base_c, base_d, ids, names, site_teams)
    check(not L.team_copy_errors(teams), "derived team text passes the descriptive-language guard for all 68 programs")
    check(len(teams) == 68 and set(teams) == site_teams, "every one of the 68 site teams gets a state", str(len(teams)))
    states = {s: tm["state"] for s, tm in teams.items()}
    check(all(states[s] == "below" for s in ("kansas", "purdue", "georgia-tech")), "below-minimum programs are marked below the minimum")
    check(all((tm["state"] == "ok") == tm["card"] for tm in teams.values()), "share cards exist only for programs meeting the display minimum")
    check(all(tm["n_label"] and tm["hf_games"] >= 0 and "games" in tm["sentence"] for tm in teams.values() if tm["state"] != "none"), "every team sentence carries its sample size")
    cov = f"{float(base_c['presentation']['band_coverage']):g}"
    txts = [tm[k] for tm in teams.values() for k in ("sentence", "band_text", "answer", "pin", "short") if tm.get(k)]
    check(not any(re.search(r"\bluck\b", x, re.I) for x in txts), "team copy says 'expected range', never 'luck range'")
    rt = lambda tm: f"{L.fmt(tm['range_lo'])} to {L.fmt(tm['range_hi'])}"
    check(all(rt(tm) in tm["band_text"] and "no-lasting-tendency simulation" in tm["band_text"] for tm in teams.values() if tm["state"] == "ok"),
          "every expected-range sentence gives the program's own range and says it comes from the no-lasting-tendency simulation")
    check(all(tm["band_text"].startswith("That’s inside the range our no-lasting-tendency simulation gives for its mix of games. Expected range: ")
              for tm in teams.values() if tm["state"] == "ok" and tm["inside"])
          and all(tm["band_text"].startswith("That’s outside the range our no-lasting-tendency simulation gives for its mix of games. Expected range: ")
                  and f"{cov}% range by chance alone" in tm["band_text"] and tm["band_text"].endswith("Landing outside one is a description, not a finding.")
                  for tm in teams.values() if tm["state"] == "ok" and not tm["inside"]),
          "team text follows the spec §5 template; outside adds the chance note and 'a description, not a finding'")
    check(all(tm["inside"] == (not base_d["teams"][s]["outside"]) for s, tm in teams.items() if tm["state"] == "ok"), "inside/outside comes from the deliverable's flag, not recomputed")
    check(all(tm["research_games"] == base_d["teams"][s]["research_games"] and (tm["research_text"] != "") == tm["has_research"] for s, tm in teams.items() if tm["state"] != "none"),
          "every program's research-grade game count comes straight from the data")

    # ---- 4. approve + build a published case in the copy
    code, out = run(r, "approve", fx, "--by")
    check(code != 0, "approve without a name is refused")
    code, out = run(r, "approve", fx, "--by", "Test Approver")
    check(code == 0 and os.path.isfile(os.path.join(r, "_editorial", "lab", "001-playing-down", "case.json")), "approve moves the fixture into _editorial/lab/", out)
    shutil.copy(os.path.join(fx_root, "docket.json"), os.path.join(r, "_editorial", "lab", "docket.json"))
    code, out = run(r, "build")
    check(code == 0, "build of the approved case succeeds", out[-600:])
    lab = os.path.join(r, "lab"); case_d = os.path.join(lab, "001-playing-down")
    need = ["index.html", "lab.css", "lab.js", "lab.json", "sitemap.xml", "corrections/index.html", "001/index.html",
            "001-playing-down/index.html", "001-playing-down/plan/index.html", "001-playing-down/data.json",
            "001-playing-down/card.png", "001-playing-down/og.png"]
    miss = [n for n in need if not os.path.isfile(os.path.join(lab, n))]
    check(not miss, "build writes the landing, case, plan, corrections, redirect, manifest, sitemap and images", ", ".join(miss))
    stubs = sorted(d for d in os.listdir(os.path.join(lab, "001")) if os.path.isdir(os.path.join(lab, "001", d)))
    check(stubs == sorted(site_teams), "a short share URL exists for all 68 programs", f"{len(stubs)}")
    for f in ("card.png",):
        check(B.png_size(os.path.join(case_d, f)) == (1080, 1350), "case share card is 1080x1350")
    check(B.png_size(os.path.join(case_d, "og.png")) == (1200, 630), "case preview image is 1200x630")
    try:
        xml.dom.minidom.parseString(rd(os.path.join(lab, "sitemap.xml"))); sm_ok = True
    except Exception:
        sm_ok = False
    check(sm_ok and "/lab/001-playing-down/plan/" in rd(os.path.join(lab, "sitemap.xml")), "Lab sitemap is valid XML with the case and its plan")
    man = json.loads(rd(os.path.join(lab, "lab.json")))
    check(man["cases"][0]["url"] == "/lab/001-playing-down/" and "2.0" not in json.dumps(man), "lab.json lists the case and never prints '2.0'")

    # ---- 5. team preview tags: right team, right image, right description
    bad = []
    for s in sorted(site_teams):
        tm = teams[s]
        h = rd(os.path.join(lab, "001", s, "index.html"))
        meta = dict(re.findall(r'<meta (?:property|name)="([^"]+)" content="([^"]*)"', h))
        img = meta.get("og:image", "")
        want_img = f"https://dawgindex.com/lab/001-playing-down/og/{s}.png" if tm["card"] else "https://dawgindex.com/lab/001-playing-down/og.png"
        if html.unescape(meta.get("og:title", "")).find(tm["name"]) < 0: bad.append(f"{s}: og:title")
        if tm["sentence"][:60] not in html.unescape(meta.get("og:description", "")): bad.append(f"{s}: og:description")
        if "not a verdict" not in meta.get("og:description", ""): bad.append(f"{s}: description not marked descriptive")
        if img != want_img or meta.get("twitter:image") != want_img: bad.append(f"{s}: image {img}")
        if meta.get("og:url") != f"https://dawgindex.com/lab/001/{s}/": bad.append(f"{s}: og:url")
        if f'<link rel="canonical" href="https://dawgindex.com/lab/001-playing-down/?team={s}">' not in h: bad.append(f"{s}: canonical")
        if 'content="noindex, follow"' not in h: bad.append(f"{s}: robots")
        p = os.path.join(r, img.replace("https://dawgindex.com/", ""))
        if not os.path.isfile(p) or B.png_size(p) != (1200, 630): bad.append(f"{s}: image missing or wrong size")
        elif B.png_text(p, "dawg-lab-team") != (s if tm["card"] else "case"): bad.append(f"{s}: image shows {B.png_text(p, 'dawg-lab-team')}")
        if tm["card"]:
            cp = os.path.join(case_d, "cards", s + ".png")
            if B.png_size(cp) != (1080, 1350) or B.png_text(cp, "dawg-lab-team") != s: bad.append(f"{s}: share card")
        elif os.path.exists(os.path.join(case_d, "cards", s + ".png")): bad.append(f"{s}: card exists below the minimum")
    check(not bad, "all 68 short URLs carry the right team's title, description, image (1200x630, stamped with that team) and canonical", "; ".join(bad[:6]))

    # ---- 6. card copy: descriptive, research-labeled, no trait words outside the question
    tpl = os.path.join(r, "_editorial", "templates")
    c_pub = json.loads(rd(os.path.join(r, "_editorial", "lab", "001-playing-down", "case.json")))
    bad = []
    for s, tm in teams.items():
        if not tm["card"]:
            continue
        for size in ("card", "og"):
            inner = L.card_inner(c_pub, tm, size)
            txt = html.unescape(re.sub(r"<[^>]+>", " ", re.sub(r'<div class="qs">.*?</div>', "", inner)))
            if "What happened · not a verdict" not in txt: bad.append(f"{s}/{size}: no descriptive tag")
            m = L.TRAIT.search(txt)
            if m: bad.append(f"{s}/{size}: '{m.group(0)}'")
            if tm["has_research"] and tm["card_research"] not in txt: bad.append(f"{s}/{size}: research label missing")
            want = c_pub["presentation"]["team_headlines"]["within" if tm["inside"] else "outside"].replace("{team}", tm["name"])
            if tm["answer"] != want or f'<div class="hl">{html.escape(want, quote=False)}</div>' not in inner: bad.append(f"{s}/{size}: headline isn't the approved one")
            if f'<b>{tm["hf_games"]}</b>' not in inner or f"across {tm['seasons']} seasons" not in txt: bad.append(f"{s}/{size}: sample size")
            if tm["band_text"] in txt or tm["sentence"] in txt: bad.append(f"{s}/{size}: long copy on the card")
            if not tm["has_research"] and "research grade" in txt: bad.append(f"{s}/{size}: research label on a program with none")
    check(not bad, "every team card says 'What happened · not a verdict', uses no habit words, and labels research grades", "; ".join(bad[:6]))
    case_inner = html.unescape(L.card_inner(c_pub, None, "card") + L.card_inner(c_pub, None, "og"))
    check(case_inner.count("not official DAWG grades") == 2, "both case images label the research-only grades")
    page = rd(os.path.join(case_d, "index.html"))
    check("not official DAWG grades" in page and "Research-only data" in page, "the case page labels research grades on Exhibit A and in the receipts")
    check("not official DAWG grades" in rd(os.path.join(lab, "index.html")), "the Lab landing labels research grades on its Exhibit A")
    check("noindex" not in page and "Preview" not in page and "Sample data" not in page, "published case page has no preview, sample or noindex markings")
    check(f'<a href="/lab/001-playing-down/plan/">read the plan' in page and "Plan locked" in page and "Data through Week 8" in page, "receipts carry the plan link, lock date and data cutoff")
    plan_pg = rd(os.path.join(case_d, "plan", "index.html"))
    check("exploration disclosure" in plan_pg, "the plan page publishes the plan in full")

    # ---- 7. Stories gain the Lab nav link only now, and nothing else changes
    for p in ("stories/index.html", "stories/red-river-2026/index.html"):
        live = rd(os.path.join(REPO, p)); now = rd(os.path.join(r, p))
        check(now.replace('<a href="/lab/">Lab</a>', "") == live and now.count('href="/lab/"') == 2, f"{p}: only change is the Lab link in header and footer")
    code, out = run(r, "build")
    check(code == 0 and "0 file(s) written" in out, "rebuilding changes nothing (byte-identical)", out[-300:])

    # ---- 7b. what was approved is what publishes: an edit after approval needs re-approval
    cj = os.path.join(r, "_editorial", "lab", "001-playing-down", "case.json")
    approved = rd(cj); ce = json.loads(approved)
    ce["presentation"]["team_headlines"]["within"] = "Inside its expected range"; wj(cj, ce)
    before = {k: os.path.getmtime(os.path.join(lab, k)) for k in ("index.html", "001-playing-down/index.html")}
    code, out = run(r, "build")
    check(code != 0 and "edited after approval" in out and before == {k: os.path.getmtime(os.path.join(lab, k)) for k in before},
          "a headline edited after approval stops the build; nothing is rewritten", out[-200:])
    code, out = run(r, "reapprove", "001-playing-down")
    check(code != 0, "re-approval needs a name")
    code, out = run(r, "reapprove", "001-playing-down", "--by", "Test Approver")
    code2, out2 = run(r, "build")
    ok_tm = next(s_ for s_, tm in teams.items() if tm["state"] == "ok" and tm["inside"])
    stub = rd(os.path.join(lab, "001", ok_tm, "index.html"))
    check(code == 0 and code2 == 0 and "Inside its expected range" in rd(os.path.join(case_d, "data.json")) and B.png_text(os.path.join(case_d, "og", ok_tm + ".png"), "dawg-lab-team") == ok_tm,
          "after re-approval the new headline publishes to the page data and the cards are re-rendered", out2[-200:])
    open(cj, "w").write(approved); run(r, "reapprove", "001-playing-down", "--by", "Test Approver"); run(r, "build")

    # ---- 8. canonical URLs never change; live cases stay live
    r2 = r + "-slug"; shutil.copytree(r, r2)
    src = os.path.join(r2, "_editorial", "lab", "001-playing-down"); dst = os.path.join(r2, "_editorial", "lab", "001-down")
    os.rename(src, dst); cc = json.loads(rd(os.path.join(dst, "case.json"))); cc["slug"] = "down"; wj(os.path.join(dst, "case.json"), cc)
    code, out = run(r2, "build")
    check(code != 0 and "never change" in out, "a published case can't change its slug", out[-300:])
    shutil.rmtree(dst)
    code, out = run(r2, "build")
    check(code != 0 and "no source" in out and os.path.isfile(os.path.join(r2, "lab", "001-playing-down", "index.html")), "removing a published case's source stops the build; the page stays live", out[-300:])

    # ---- 9. outside lab/ and stories/, the build touches nothing
    def tree(root, skip=("lab/", "stories/", "_editorial/", ".git/")):
        o = {}
        for d_, _, fs in os.walk(root):
            for f in fs:
                rel = os.path.relpath(os.path.join(d_, f), root)
                if not rel.startswith(skip) and "__pycache__" not in rel:
                    o[rel] = os.path.getsize(os.path.join(d_, f))
        return o
    check(tree(r) == tree(REPO), "homepage, team pages and data are untouched by the Lab build")

    # ---- 10. preview stays private
    pv = tempfile.mkdtemp(prefix="labpv-")
    code, out = run(r, "preview", sd, "--out", r + "/x")
    check(code != 0 and "outside the site repo" in out, "previews can't be written inside the repo")
    code, out = run(r, "preview", sd, "--out", pv, "--no-cards")
    pvp = rd(os.path.join(pv, "lab", "001-playing-down", "index.html"))
    check(code == 0 and "noindex, nofollow" in pvp and "Sample data" in pvp and "Preview" in pvp, "sample preview is noindex and visibly marked Preview and Sample data")
    pv2 = tempfile.mkdtemp(prefix="labpv2-")
    code, out = run(r, "preview", sd, "--out", pv2, "--look", "production", "--no-cards")
    pp = rd(os.path.join(pv2, "lab", "001-playing-down", "index.html"))
    check(code == 0 and "lb-preview" not in pp and 'class="lb-sample"' not in pp and "noindex, nofollow" in pp and "lb-tagS" in pp,
          "production-look preview drops the banners but stays noindex, private, and keeps the small Sample data tags on charts")
    sc_ = json.loads(rd(os.path.join(sd, "case.json"))); sdat_ = json.loads(rd(os.path.join(sd, "data.json")))
    tms = L.derive_teams(sc_, sdat_, ids, names, site_teams); tm0 = next(tm for tm in tms.values() if tm["card"])
    cp = L.card_page(sc_, sdat_, tms, tm0, "card", os.path.join(r, "_editorial", "templates"), "production")
    check('class="sample"' not in cp and "Sample data" in cp, "production-look cards drop the corner ribbon and keep a Sample data tag on the chart")

    # ---- 11. in the browser
    browser_checks(r, teams)

    n = sum(1 for ok, _, _ in RESULTS if ok)
    print(f"\n{n} of {len(RESULTS)} checks passed")
    sys.exit(0 if n == len(RESULTS) else 1)


def browser_checks(r, teams):
    from playwright.sync_api import sync_playwright
    import requests
    S = requests.Session(); S.verify = B.CA if os.path.exists(B.CA) else True
    cache = {}
    def route(rt):
        u = rt.request.url
        if u.startswith("https://lab.local/"):
            path = u.split("https://lab.local/", 1)[1].split("?")[0].split("#")[0]
            f = os.path.join(r, path)
            if os.path.isdir(f): f = os.path.join(f, "index.html")
            if os.path.isfile(f):
                return rt.fulfill(status=200, body=open(f, "rb").read(), headers={"content-type": mimetypes.guess_type(f)[0] or "text/html"})
            return rt.fulfill(status=404, body=b"not found")
        if "fonts.googleapis.com" in u or "fonts.gstatic.com" in u:
            if u not in cache:
                try:
                    x = S.get(u, headers={"User-Agent": rt.request.headers.get("user-agent", "")}, timeout=30)
                    cache[u] = (x.status_code, x.content, x.headers.get("content-type", ""))
                except Exception:
                    cache[u] = (404, b"", "text/plain")
            st, b, ct = cache[u]
            return rt.fulfill(status=st, body=b, headers={"content-type": ct, "access-control-allow-origin": "*"})
        return rt.fulfill(status=404, body=b"")
    O = "https://lab.local"
    with sync_playwright() as p:
        br = p.chromium.launch()
        def ctx(w, h):
            c = br.new_context(viewport={"width": w, "height": h}, is_mobile=w < 600, has_touch=w < 600)
            c.route("**/*", route); return c
        def ready(pg):
            pg.wait_for_selector("body[data-ready='1']", state="attached", timeout=10000); pg.wait_for_timeout(150)
        c = ctx(1440, 900); pg = c.new_page(); errs = []
        pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None); pg.on("pageerror", lambda e: errs.append(str(e)))

        # short URLs: every one lands on the case with that team's panel open
        bad = []
        for s in sorted(teams):
            pg.goto(f"{O}/lab/001/{s}/"); pg.wait_for_url(re.compile(r".*/lab/001-playing-down/.*"), timeout=10000); ready(pg)
            u = pg.url
            if not u.endswith(f"/lab/001-playing-down/?team={s}"): bad.append(f"{s}: {u}"); continue
            if not pg.evaluate("!document.getElementById('lb-panel').hidden"): bad.append(f"{s}: panel closed")
            if pg.text_content("#lb-p-name") != teams[s]["name"]: bad.append(f"{s}: panel shows {pg.text_content('#lb-p-name')}")
        check(not bad, "all 68 short URLs redirect to the case with the right team's panel open", "; ".join(bad[:5]))

        pg.goto(f"{O}/lab/001/?team=baylor#lb-carry-sec"); pg.wait_for_url(re.compile(r".*001-playing-down.*")); ready(pg)
        check(pg.url.endswith("/lab/001-playing-down/?team=baylor#lb-carry-sec"), "/lab/001/ redirect keeps the query and the hash", pg.url)
        check(pg.text_content("#lb-p-name") == teams["baylor"]["name"], "/lab/001/?team=baylor opens Baylor")

        # Back closes the panel and stays on the case
        pg.goto(f"{O}/lab/001-playing-down/?team=baylor"); ready(pg)
        pg.go_back(); pg.wait_for_timeout(250)
        check(pg.evaluate("document.getElementById('lb-panel').hidden") and "001-playing-down" in pg.url, "Back closes the team panel and stays on the case", pg.url)
        pg.click("#lb-open-panel"); pg.wait_for_timeout(150); pg.keyboard.press("Escape"); pg.wait_for_timeout(250)
        check(pg.evaluate("document.getElementById('lb-panel').hidden"), "Escape closes the panel")

        # invalid slug
        pg.goto(f"{O}/lab/001-playing-down/?team=not-a-team"); ready(pg)
        check(pg.is_visible("#lb-notice") and "?team" not in pg.url and pg.evaluate("document.getElementById('lb-panel').hidden"),
              "an unknown team slug shows a notice, opens nothing and is removed from the URL", pg.url)

        # below the minimum
        pg.goto(f"{O}/lab/001-playing-down/?team=kansas"); ready(pg)
        body = pg.text_content("#lb-p-body")
        check("Too few games for an expected range" in body and pg.evaluate("document.getElementById('lb-p-share').hidden") and "Expected range" in body and "not shown below the minimum" in body
              and "Adjusted" not in body, "below-minimum team: says not enough games, shows no expected range and no share card", body[:160])

        # research marking in the panel
        rs = next(s for s, tm in teams.items() if tm["state"] == "ok" and tm["has_research"])
        pg.goto(f"{O}/lab/001-playing-down/?team={rs}"); ready(pg)
        body = pg.text_content("#lb-p-body")
        check(teams[rs]["research_text"] in body and "Adjusted" not in body and "Season by season" not in body,
              "panel states how many games use research grades, with no shrunken value and no season-by-season chart", body[:120])
        links = pg.locator("#lb-p-body .lb-research-note a[href='#lb-receipts']")
        check(links.count() == 4, "every panel section that charts research games carries the label and a provenance link (4 of 4)", str(links.count()))
        links.first.click(); pg.wait_for_timeout(400)
        top = pg.evaluate("document.getElementById('lb-receipts').getBoundingClientRect().top")
        check(pg.evaluate("document.getElementById('lb-panel').hidden") and -5 <= top < 200, "'How they were made' closes the panel and lands on the receipts with the provenance", str(top))
        check(teams[rs]["research_text"] in pg.text_content("#lb-strip-res"), "the team strip on the case page states the research-grade games")
        pg.evaluate("window.scrollTo(0, document.body.scrollHeight * 0.45)"); pg.wait_for_timeout(300)
        check(teams[rs]["research_short"] in (pg.text_content("#lb-side-n") or ""), "the desktop side card carries the research marker")
        nr = [s_ for s_, tm in teams.items() if tm["state"] == "ok" and not tm["has_research"]]
        if nr:
            pg.goto(f"{O}/lab/001-playing-down/?team={nr[0]}"); ready(pg)
            check(pg.locator("#lb-p-body .lb-research-note").count() == 0, "a program with no research seasons shows no research label")
        check("not a verdict on" in body, "panel marks the team result as what happened, not a verdict")

        # precedence: ?team= beats the remembered team
        pg.goto(f"{O}/lab/001-playing-down/?team=texas"); ready(pg)
        pg.goto(f"{O}/lab/001-playing-down/?team=baylor"); ready(pg)
        check(pg.text_content("#lb-p-name") == teams["baylor"]["name"], "?team= wins over the remembered team")
        pg.goto(f"{O}/lab/001-playing-down/"); ready(pg)
        check(pg.input_value("#lb-pick") == "baylor" and pg.evaluate("document.getElementById('lb-panel').hidden"), "without ?team= the remembered team is preselected and the panel stays closed")

        # homepage: the team picker is the main action
        pg.evaluate("try{localStorage.clear()}catch(e){}")
        pg.goto(f"{O}/lab/"); ready(pg)
        bb = pg.locator("#lb-home-pick").bounding_box()
        check(pg.input_value("#lb-home-pick") == "" and bb["y"] + bb["height"] < 900 and bb["height"] >= 56,
              "Lab homepage: the team picker sits above the fold, large, with no team preselected", str(bb))
        pg.select_option("#lb-home-pick", rs); pg.wait_for_timeout(150)
        check(pg.text_content("#lb-home-ans") == teams[rs]["answer"] and pg.get_attribute("#lb-home-link", "href").endswith(f"?team={rs}") and pg.is_visible("#lb-home-rn"),
              "picking a team on the homepage shows its answer, its research marker and a link to its result")
        pg.click("#lb-home-link"); pg.wait_for_url(re.compile(r".*\?team=")); ready(pg)
        check(pg.text_content("#lb-p-name") == teams[rs]["name"], "the homepage link opens that team's panel")

        # drawer on desktop
        pg.goto(f"{O}/lab/001-playing-down/?team=baylor"); ready(pg)
        bb = pg.locator("#lb-panel").bounding_box()
        check(bb and 560 <= bb["width"] <= 640 and bb["x"] > 700, "desktop: the team panel is a side drawer", str(bb))
        check(not errs, "no script errors on desktop", "; ".join(errs[:3]))
        c.close()

        # phones: full-screen panel
        for w, h in ((390, 844), (360, 740)):
            c = ctx(w, h); pg = c.new_page(); e2 = []
            pg.on("pageerror", lambda e: e2.append(str(e))); pg.on("console", lambda m: e2.append(m.text) if m.type == "error" else None)
            pg.goto(f"{O}/lab/"); ready(pg)
            hb = pg.locator("#lb-home-pick").bounding_box()
            check(hb["y"] + hb["height"] < h and abs(hb["width"] - (w - 2 * 16 - 2 * 18 - 4)) < 30, f"{w}px: the homepage team picker is above the fold and full width", str(hb))
            pg.goto(f"{O}/lab/001-playing-down/?team=baylor"); ready(pg)
            bb = pg.locator("#lb-panel").bounding_box()
            check(bb and abs(bb["width"] - w) < 1 and abs(bb["height"] - h) < 1 and pg.is_visible(".lb-back") and not pg.is_visible(".lb-close"),
                  f"{w}px: the team panel is full screen with a Back button", str(bb))
            pg.click(".lb-back"); pg.wait_for_timeout(250)
            check(pg.evaluate("document.getElementById('lb-panel').hidden"), f"{w}px: Back to the case closes it")
            pg.evaluate("window.scrollTo(0, document.body.scrollHeight * 0.5)"); pg.wait_for_timeout(300)
            check(pg.is_visible("#lb-pin") and teams["baylor"]["name"] in pg.text_content("#lb-pin"), f"{w}px: the pinned team bar appears once the team strip scrolls away")
            if teams["baylor"]["research_short"]:
                check(teams["baylor"]["research_short"] in pg.text_content("#lb-pin"), f"{w}px: the pinned bar carries the research marker")
            # the carryover chart and the 68-program chart on a phone: fit their boxes, carry axis numbers; tapping a program row picks it
            for sel in ("#lb-persist", "#lb-programs"):
                pg.locator(sel).scroll_into_view_if_needed(); pg.wait_for_timeout(150)
                box = pg.locator(sel).bounding_box(); sv = pg.locator(sel + " svg").bounding_box()
                nt = pg.evaluate(f"[...document.querySelectorAll('{sel} svg text')].filter(t => /^[+−]\\d+$/.test(t.textContent)).length")
                check(sv["width"] <= box["width"] + 1 and nt >= 3, f"{w}px: {sel} fits its box and has axis numbers", f"ticks {nt}")
            rows_ = pg.evaluate("document.querySelectorAll('#lb-programs svg text').length")
            sb = pg.locator("#lb-programs svg").bounding_box()
            pg.mouse.click(sb["x"] + 20, sb["y"] + 26 + 19 * 22 + 11); pg.wait_for_timeout(200)
            pick_ = pg.input_value("#lb-pick")
            check(rows_ > 68 and pick_ == sorted(teams, key=lambda s_: teams[s_]["name"])[19], f"{w}px: tapping a row in the 68-program chart picks that program", pick_)
            check(not e2, f"{w}px: no script errors", "; ".join(e2[:3]))
            c.close()

        # no sideways scroll, no broken images, every page
        for w in (360, 390, 1440):
            c = ctx(w, 900); pg = c.new_page(); e3 = []
            pg.on("pageerror", lambda e: e3.append(str(e)))
            for path in ("/lab/", "/lab/001-playing-down/", "/lab/001-playing-down/?team=baylor", "/lab/001-playing-down/plan/", "/lab/corrections/"):
                pg.goto(O + path); pg.wait_for_load_state("load"); pg.wait_for_timeout(250)
                sw = pg.evaluate("document.documentElement.scrollWidth"); broken = pg.evaluate("[...document.images].filter(i => i.complete && i.naturalWidth === 0 && !i.hidden).map(i => i.src)")
                check(sw <= w and not broken and not e3, f"{path} at {w}px: no sideways scroll, no broken images, no script errors", f"scrollWidth {sw}; {broken[:2]}; {e3[:2]}")
            c.close()
        br.close()


if __name__ == "__main__":
    main()
