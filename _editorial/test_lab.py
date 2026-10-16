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
    c["verdict"].update(subtitle="Reason set in the plan", answer="Test answer: one plain sentence for the test suite.")
    c["second_check"] = "Rerun independently for the test suite"
    c["data_lock"]["snapshot"] = "sha256:test00000000000000000000"
    c["research_datasets"][0]["provenance"] = "Test provenance line for the suite."
    wj(os.path.join(d, "case.json"), c)
    data = json.loads(rd(os.path.join(d, "data.json")))
    data["sample"] = False
    for cut in data["cuts"]:
        cut["note"] = cut["note"].replace("Sample number. ", "")
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
    c = copy.deepcopy(base_c); c["verdict"]["kind"] = "probably"; neg("unknown verdict", "verdict.kind", c)
    c = copy.deepcopy(base_c); c["type"] = "original-investigation"; neg("Original Investigation (not in v0)", "Original Investigation", c)
    c = copy.deepcopy(base_c); del c["approved_by"]; neg("no approval on record", "approved_by", c)
    d = copy.deepcopy(base_d); d["teams"]["not-a-team"] = d["teams"]["baylor"]; neg("unknown team slug", "unknown team slug", d=d)
    d = copy.deepcopy(base_d); del d["teams"]["baylor"]["groups"][0]["n"]; neg("team row without a sample size", "sample size", d=d)
    d = copy.deepcopy(base_d); del d["teams"]["baylor"]["season_rows"][0]["n"]; neg("season row without a sample size", "sample size", d=d)
    d = copy.deepcopy(base_d); d["teams"]["baylor"]["finding"] = {"text": "Baylor plays down."}; neg("team finding without its criteria", "team finding needs", d=d)
    d = copy.deepcopy(base_d); [x.update(plan=True) for x in d["cuts"]]; neg("more than one plan-choice cut", "exactly one", d=d)
    neg("unfilled [placeholder]", "placeholder", md=base_md + "\nThe gap was [X] points.\n")
    neg("'illustrative' wording", "sample/illustrative", md=base_md + "\nAn illustrative example.\n")
    neg("'2.0' in the copy", "'2.0'", md=base_md + "\nDAWG 2.0 says so.\n")
    c = copy.deepcopy(base_c); c["plan"].pop("label"); neg("plan version '2.0' with no public label", "plan.label", c)
    ok_links = L.validate(copy.deepcopy(base_c), base_md + "\nSee [the method](/#method). [[bound]]\n", copy.deepcopy(base_d), base_p, fx, site_teams, "publish")
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
            if f"not a verdict on {tm['name']}" not in txt: bad.append(f"{s}/{size}: no descriptive tag")
            m = L.TRAIT.search(txt)
            if m: bad.append(f"{s}/{size}: '{m.group(0)}'")
            if tm["has_research"] and c_pub["research_datasets"][0]["label"] not in txt: bad.append(f"{s}/{size}: research label missing")
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
        check("Not enough games for a fair read" in body and pg.evaluate("document.getElementById('lb-p-share').hidden") and "Adjusted" in body and "not shown below the minimum" in body,
              "below-minimum team: says not enough games, hides the adjusted value and the share card", body[:160])

        # research marking in the panel
        rs = next(s for s, tm in teams.items() if tm["state"] == "ok" and tm["has_research"])
        pg.goto(f"{O}/lab/001-playing-down/?team={rs}"); ready(pg)
        body = pg.text_content("#lb-p-body")
        check("not official DAWG grades" in body and "Hollow" in body and pg.locator("#lb-p-seasons circle[fill='none'], #lb-p-seasons circle[fill='#FBF4E2']").count() > 0,
              "panel labels research grades on the chance strip and marks research seasons hollow", body[:120])
        check("not a verdict on" in body, "panel marks the team result as what happened, not a verdict")

        # precedence: ?team= beats the remembered team
        pg.goto(f"{O}/lab/001-playing-down/?team=texas"); ready(pg)
        pg.goto(f"{O}/lab/001-playing-down/?team=baylor"); ready(pg)
        check(pg.text_content("#lb-p-name") == teams["baylor"]["name"], "?team= wins over the remembered team")
        pg.goto(f"{O}/lab/001-playing-down/"); ready(pg)
        check(pg.input_value("#lb-pick") == "baylor" and pg.evaluate("document.getElementById('lb-panel').hidden"), "without ?team= the remembered team is preselected and the panel stays closed")

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
            pg.goto(f"{O}/lab/001-playing-down/?team=baylor"); ready(pg)
            bb = pg.locator("#lb-panel").bounding_box()
            check(bb and abs(bb["width"] - w) < 1 and abs(bb["height"] - h) < 1 and pg.is_visible(".lb-back") and not pg.is_visible(".lb-close"),
                  f"{w}px: the team panel is full screen with a Back button", str(bb))
            pg.click(".lb-back"); pg.wait_for_timeout(250)
            check(pg.evaluate("document.getElementById('lb-panel').hidden"), f"{w}px: Back to the case closes it")
            pg.evaluate("window.scrollTo(0, document.body.scrollHeight * 0.5)"); pg.wait_for_timeout(300)
            check(pg.is_visible("#lb-pin") and teams["baylor"]["name"] in pg.text_content("#lb-pin"), f"{w}px: the pinned team bar appears once the team strip scrolls away")
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
