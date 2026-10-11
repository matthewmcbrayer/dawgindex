#!/usr/bin/env python3
"""Browser checks for the editorial pieces of the built homepage: STORIES nav, Beyond the Score, team-page stories.

  python3 _editorial/test_site_integration.py SITE_DIR [SHOTS_DIR]

SITE_DIR is a built site (e.g. the weekly2 stage). The story list can be swapped per scenario, so the four-story layout and the
draft filter are tested without publishing anything.
"""
import json, mimetypes, os, sys
import requests
from playwright.sync_api import sync_playwright

SITE = os.path.abspath(sys.argv[1]); SHOTS = sys.argv[2] if len(sys.argv) > 2 else None
CA = "/root/.ccr/ca-bundle.crt"
S = requests.Session(); S.verify = CA if os.path.exists(CA) else True
RESULTS = []
def check(ok, name, detail=""):
    RESULTS.append(bool(ok)); print(("PASS  " if ok else "FAIL  ") + name + (f"  ({detail})" if detail and not ok else ""))

REAL = json.load(open(os.path.join(SITE, "stories/stories.json")))
def sample(slug, date, title, status="published", teams=(("baylor", "239", "Baylor"),)):
    return {"slug": slug, "status": status, "url": f"/stories/{slug}/", "title": title, "headline": {"big": title, "sub": None}, "tab": "Sample",
            "category": "Analysis", "date": date, "teams": [t[0] for t in teams], "team_ids": [t[1] for t in teams], "team_names": [t[2] for t in teams],
            "dek": "Layout sample for the test suite. Not a real story.", "image": "/stories/red-river-2026/card.png", "image_alt": "", "og_image": "/stories/red-river-2026/og.png"}
FOUR = {"version": 1, "stories": [
    sample("sample-newest", "2026-10-14", "Sample: the newest story leads the section"),
    REAL["stories"][0],
    sample("sample-third", "2026-10-09", "Sample: a third story in the list"),
    sample("sample-fourth", "2026-10-08", "Sample: a fourth story in the list"),
    sample("sample-fifth", "2026-10-07", "Sample: a fifth story should not show"),
    sample("sample-draft", "2026-10-15", "DRAFT MUST NOT SHOW", status="draft"),
    {k: v for k, v in sample("sample-nostatus", "2026-10-16", "NO STATUS MUST NOT SHOW").items() if k != "status"},
]}

def make_route(manifest):
    def route(r):
        u = r.request.url
        if u.startswith("https://preview.local/"):
            path = u.split("https://preview.local/", 1)[1].split("?")[0].split("#")[0]
            if path == "stories/stories.json" and manifest is not None:
                if manifest == 404: return r.fulfill(status=404, body=b"")
                return r.fulfill(status=200, body=json.dumps(manifest).encode(), headers={"content-type": "application/json"})
            f = os.path.join(SITE, path)
            if os.path.isdir(f): f = os.path.join(f, "index.html")
            if os.path.isfile(f):
                return r.fulfill(status=200, body=open(f, "rb").read(), headers={"content-type": mimetypes.guess_type(f)[0] or "application/octet-stream"})
            return r.fulfill(status=404, body=b"")
        if "fonts.g" in u:
            x = S.get(u, timeout=30); return r.fulfill(status=x.status_code, body=x.content, headers={"content-type": x.headers.get("content-type", "")})
        return r.fulfill(status=204, body=b"")
    return route

def page(b, w, manifest=None, url="https://preview.local/"):
    mob = w < 600
    c = b.new_context(viewport={"width": w, "height": 900}, device_scale_factor=2 if mob else 1, is_mobile=mob, has_touch=mob)
    c.route("**/*", make_route(manifest)); pg = c.new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(url); pg.wait_for_function("document.getElementById('home-host') && document.getElementById('home-host').getAttribute('data-ready') === '1'", timeout=30000)
    pg.evaluate("document.fonts.ready"); pg.wait_for_timeout(900)
    return c, pg, errs

R = "document.getElementById('home-host').shadowRoot"
def js(pg, expr): return pg.evaluate(f"(() => {{ const r = {R}; {expr} }})()")

with sync_playwright() as p:
    b = p.chromium.launch()
    for w in (1280, 390, 360):
        c, pg, errs = page(b, w)
        o = js(pg, """const ids = [...r.querySelectorAll('main[data-view="home"] > section')].map(s => s.id || s.className);
            const sec = r.getElementById('beyond-sec'); const nav = r.querySelector('header .nav'); const st = [...nav.querySelectorAll('a')].find(a => a.textContent.trim() === 'Stories');
            const fst = [...r.querySelectorAll('.foot-nav a')].find(a => a.textContent.trim() === 'Stories');
            const lead = r.querySelector('#bt-grid .bt-lead'); const img = lead && lead.querySelector('img');
            const sb = st ? st.getBoundingClientRect() : null;
            return {ids, hidden: sec.hidden, solo: r.getElementById('bt-grid').classList.contains('solo'), lead: lead && lead.getAttribute('href'),
              items: r.querySelectorAll('#bt-grid .bt-item').length, title: lead && lead.querySelector('.bt-t').textContent,
              meta: lead && lead.querySelector('.bt-m').textContent, imgOk: !!(img && img.complete && img.naturalWidth > 0) || (img && img.loading === 'lazy'),
              nav: st && st.getAttribute('href'), navVisible: !!(sb && sb.width > 0 && sb.left >= 0 && sb.right <= window.innerWidth),
              navFits: nav.scrollWidth <= nav.clientWidth + 1, foot: fst && fst.getAttribute('href'),
              all: [...sec.querySelectorAll('a')].some(a => a.getAttribute('href') === '/stories/')};""")
        i4, ib, ir = o["ids"].index("four-sec"), o["ids"].index("beyond-sec"), o["ids"].index("rankings-sec")
        check(ib == i4 + 1 and ir == ib + 1, f"{w}px: Beyond the Score sits right after the four cards and before Rankings", str(o["ids"][:5]))
        check(not o["hidden"] and o["solo"] and o["lead"] == "/stories/red-river-2026/" and o["items"] == 0, f"{w}px: one published story shows as a full-width lead", str(o))
        check(o["title"] == "BOOMER SOONER! What Did We Actually Learn?" and "Oct. 11, 2026" in o["meta"] and "Oklahoma" in o["meta"], f"{w}px: lead card shows the title, date and teams from the story list")
        check(o["all"], f"{w}px: section links to /stories/")
        check(o["nav"] == "/stories/" and o["foot"] == "/stories/", f"{w}px: STORIES is in the header nav and footer nav, linking to /stories/")
        check(o["navVisible"] and o["navFits"], f"{w}px: every header nav item, STORIES included, is visible without scrolling the nav", f"visible {o['navVisible']} fits {o['navFits']}")
        ov = pg.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
        check(ov == 0 and not errs, f"{w}px homepage: no sideways scroll, no script errors", f"{ov} {errs}")
        if SHOTS:
            pg.locator("#home-host").locator("#beyond-sec").screenshot(path=os.path.join(SHOTS, f"home-beyond-{w}.png"))
            pg.locator("#home-host").locator("header.mast").screenshot(path=os.path.join(SHOTS, f"nav-{w}.png"))
            if w == 1280:
                top = pg.evaluate(f"(() => {{ const r = {R}; return r.getElementById('rankings-sec').getBoundingClientRect().top + window.scrollY; }})()")
                pg.set_viewport_size({"width": 1280, "height": int(top) + 120}); pg.wait_for_timeout(400)
                pg.screenshot(path=os.path.join(SHOTS, "homepage-desktop-top.png"))
            if w == 390:
                top = pg.evaluate(f"(() => {{ const r = {R}; return r.getElementById('rankings-sec').getBoundingClientRect().top + window.scrollY; }})()")
                pg.set_viewport_size({"width": 390, "height": int(top) + 80}); pg.wait_for_timeout(400)
                pg.screenshot(path=os.path.join(SHOTS, "homepage-phone-390-top.png"))
        c.close()

    # scaling: lead + up to three more, newest first; drafts and entries without status never show
    for w in (1280, 390):
        c, pg, errs = page(b, w, FOUR)
        o = js(pg, """return {lead: r.querySelector('#bt-grid .bt-lead').getAttribute('href'), solo: r.getElementById('bt-grid').classList.contains('solo'),
            items: [...r.querySelectorAll('#bt-grid .bt-item')].map(a => a.getAttribute('href')), text: r.getElementById('beyond-sec').textContent};""")
        check(o["lead"] == "/stories/sample-newest/" and not o["solo"], f"{w}px, five published + drafts: the newest published story leads")
        check(o["items"] == ["/stories/red-river-2026/", "/stories/sample-third/", "/stories/sample-fourth/"], f"{w}px: exactly three more, newest first", str(o["items"]))
        check("DRAFT MUST NOT SHOW" not in o["text"] and "NO STATUS MUST NOT SHOW" not in o["text"] and "fifth" not in o["text"], f"{w}px: drafts and entries without published status never show")
        ov = pg.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
        check(ov == 0 and not errs, f"{w}px four-story layout: no sideways scroll, no script errors", f"{ov} {errs}")
        if SHOTS: pg.locator("#home-host").locator("#beyond-sec").screenshot(path=os.path.join(SHOTS, f"home-beyond-4stories-{w}.png"))
        c.close()

    # a deep link below the section: the story list arrives AFTER /#rankings has scrolled; Rankings must not get pushed down
    for w in (390, 1280):
        mob = w < 600
        c = b.new_context(viewport={"width": w, "height": 844}, device_scale_factor=2 if mob else 1, is_mobile=mob, has_touch=mob)
        held, base = [], make_route(None)
        def late(r):
            if r.request.url.split("?")[0].endswith("/stories/stories.json"): held.append(r); return
            base(r)
        c.route("**/*", late); pg = c.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto("https://preview.local/#rankings"); pg.wait_for_function("document.getElementById('home-host').getAttribute('data-ready') === '1'", timeout=30000)
        pg.wait_for_timeout(1500)
        t0 = js(pg, "return r.getElementById('rankings-sec').getBoundingClientRect().top;")
        for r in held: r.fulfill(status=200, body=json.dumps(REAL).encode(), headers={"content-type": "application/json"})
        pg.wait_for_timeout(1200)
        o = js(pg, "return {top: r.getElementById('rankings-sec').getBoundingClientRect().top, shown: !r.getElementById('beyond-sec').hidden};")
        check(held and o["shown"] and abs(o["top"] - t0) <= 2 and not errs, f"{w}px: stories arriving after a /#rankings jump don't push Rankings down", f"held {len(held)} before {t0:.0f} after {o['top']:.0f} {errs}")
        c.close()

    # the story list is missing: the section stays hidden and the rest of the homepage still draws
    c, pg, errs = page(b, 1280, 404)
    o = js(pg, "return {hidden: r.getElementById('beyond-sec').hidden, four: r.getElementById('four').children.length, rows: r.querySelectorAll('#board tbody tr').length};")
    check(o["hidden"] and o["four"] == 4 and o["rows"] > 0 and not errs, "story list unavailable: section hidden, four cards and rankings still render", str(o))
    c.close()

    # team pages: stories tagged with the team's ID
    for slug, tid, expect in (("oklahoma", "201", True), ("texas", "251", True), ("baylor", "239", False)):
        for w in (1280, 390, 360):
            c, pg, errs = page(b, w, url=f"https://preview.local/?team={slug}")
            pg.wait_for_timeout(1500)
            o = js(pg, """const s = r.getElementById('t-stories'); return {view: [...r.querySelectorAll('main.view')].filter(m => !m.hidden).map(m => m.getAttribute('data-view')),
                hidden: s.hidden, links: [...s.querySelectorAll('.bt-lead')].map(a => a.getAttribute('href'))};""")
            ok = (not o["hidden"] and o["links"] == ["/stories/red-river-2026/"]) if expect else (o["hidden"] and not o["links"])
            check(o["view"] == ["team"] and ok, f"{slug} team page ({tid}) at {w}px: " + ("shows the Red River story" if expect else "no tagged stories, section hidden"), str(o))
            sec_ov = js(pg, "const s = r.getElementById('t-stories'); if (s.hidden) return 0; return Math.max(0, ...[s, ...s.querySelectorAll('*')].map(e => e.getBoundingClientRect().right - document.documentElement.clientWidth));")
            check(sec_ov <= 0.5 and not errs, f"{slug} team page at {w}px: stories section fits the screen, no script errors", f"{sec_ov} {errs}")
            if SHOTS and expect and slug == "oklahoma":
                pg.locator("#home-host").locator("#t-stories").screenshot(path=os.path.join(SHOTS, f"team-oklahoma-stories-{w}.png"))
                if w in (1280, 390):
                    y0 = pg.evaluate(f"(() => {{ const r = {R}; return r.querySelector('.teampage').getBoundingClientRect().top + window.scrollY; }})()")
                    y1 = pg.evaluate(f"(() => {{ const r = {R}; const e = r.getElementById('t-stories'); return e.getBoundingClientRect().bottom + window.scrollY; }})()")
                    pg.set_viewport_size({"width": w, "height": int(y1) + 60}); pg.wait_for_timeout(500)
                    pg.screenshot(path=os.path.join(SHOTS, f"team-oklahoma-page-{w}.png"))
            c.close()
    b.close()

print(f"\n{sum(RESULTS)} of {len(RESULTS)} checks passed")
sys.exit(0 if all(RESULTS) else 1)
