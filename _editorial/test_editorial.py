#!/usr/bin/env python3
"""Tests for the DAWG editorial build. Every scenario runs on a throwaway copy of the repo; the real repo is only read.

  python3 _editorial/test_editorial.py            (needs Playwright + Chromium; the social-card and layout checks render pages)
"""
import html, hashlib, json, os, re, shutil, subprocess, sys, tempfile, xml.dom.minidom
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import build as B

RESULTS = []
def check(ok, name, detail=""):
    RESULTS.append((bool(ok), name, detail)); print(("PASS  " if ok else "FAIL  ") + name + (f"  ({detail})" if detail and not ok else ""))

def sha(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()
def tree(root):
    out = {}
    for d, _, fs in os.walk(root):
        for f in fs:
            p = os.path.join(d, f); out[os.path.relpath(p, root)] = sha(p)
    return out

def copy_repo():
    tmp = tempfile.mkdtemp(prefix="edtest-")
    dst = os.path.join(tmp, "repo")
    shutil.copytree(REPO, dst, ignore=shutil.ignore_patterns(".git", "__pycache__"))
    return dst

def run(repo, *args):
    p = subprocess.run([sys.executable, os.path.join(repo, "_editorial", "build.py"), *args, "--repo", repo], capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr

def git_main(path):
    return subprocess.run(["git", "-C", REPO, "show", "origin/main:" + path], capture_output=True).stdout

SAMPLE = """---
slug: test-sample-story
status: draft
title: Sample Story for the Test Suite
tab: Test · Week 6
category: Analysis
date: '2026-10-11'
teams: [baylor]
dek: A sample dek that only exists inside the test suite.
description: A sample description that only exists inside the test suite.
image: card.png
image_alt: Sample card image.
---
The opening paragraph with **bold** and a [link](/#method).

## A section heading

| | A | B |
|---|---|---|
| Points | 1 | 2 |

::: doesnt
One sample is one sample.
:::
"""

def make_draft(root, slug="test-sample-story", text=SAMPLE):
    d = os.path.join(root, slug); os.makedirs(d, exist_ok=True)
    open(os.path.join(d, "story.md"), "w").write(text.replace("test-sample-story", slug))
    shutil.copy(os.path.join(REPO, "_editorial", "stories", "red-river-2026", "card.png"), os.path.join(d, "card.png"))
    return d

N_LIVE = len(json.load(open(os.path.join(REPO, "stories", "stories.json")))["stories"])   # stories live in the repo right now

def main():
    live_page, live_og = git_main("stories/red-river-2026/index.html"), git_main("stories/red-river-2026/og.png")
    # corrections Matthew approved after publication: the built page must equal main with exactly these applied
    CORRECTIONS = [(b'A single game\'s PLAY is good to about \xc2\xb112 points.',
                    b'Single-game PLAY results vary a lot: about 95% of them land within roughly \xc2\xb121 points, and the standard deviation is about 11 points.'),
                   (b'<div class="mid">Final<span>Red River</span></div>', b'<div class="mid">Final<span>Red River Rivalry</span></div>')]
    for a, b_ in CORRECTIONS:
        if a in live_page: live_page = live_page.replace(a, b_)

    # ---- 1. Red River survives unchanged
    r = copy_repo(); code, out = run(r, "build")
    check(code == 0, "build succeeds on the current sources", out[-300:])
    page = open(os.path.join(r, "stories/red-river-2026/index.html"), "rb").read()
    art = lambda x: x[x.index(b"<article"):x.index(b"</article>")]
    check(art(page) == art(live_page), "Red River article (headline through method note) byte-for-byte identical to the live page on main, apart from approved corrections")
    check(b"\xc2\xb112 points" not in page and b"about 95% of them land within roughly \xc2\xb121 points" in page, "Red River carries the corrected PLAY variation (95% of single games within about \u00b121), not \u00b112")
    nav_only = lambda x: re.sub(rb'<a href="/stories/"( aria-current="page")?>Stories</a>', b"", x).replace(b'\n.nav a[aria-current="page"]{border-bottom-color:var(--red)}', b"")
    check(nav_only(page) == nav_only(live_page), "the only other change to the Red River page is the Stories nav link and its style")
    check(open(os.path.join(r, "stories/red-river-2026/og.png"), "rb").read() == live_og, "Red River og.png identical to live")
    m1 = [e for e in json.load(open(os.path.join(r, "stories/stories.json")))["stories"] if e["slug"] == "red-river-2026"][0]
    check(m1["status"] == "published" and m1["team_ids"] == ["201", "251"] and m1["team_names"] == ["Oklahoma", "Texas"], "manifest entries carry status, team IDs (Oklahoma 201, Texas 251) and team names")
    allm = json.load(open(os.path.join(r, "stories/stories.json")))["stories"]
    idx0 = open(os.path.join(r, "stories/index.html")).read()
    check(m1.get("card_title") == "BOOMER SOONER! What Did We Actually Learn?" and all(e.get("card_title") for e in allm), "every manifest entry carries a short card_title (Red River's is its headline)")
    ok_cards = all((f'<h2 class="sr-only">{B.t(e["title"])}</h2>' in idx0 and f'<h2 class="st-t">{B.t(e["card_title"])}</h2>' not in idx0) if e.get("card_style") == "graphic"
                   else f'<h2 class="st-t">{B.t(e["card_title"])}</h2>' in idx0 for e in allm)
    check(ok_cards and idx0.count('class="st-art"') == len(allm), "/stories/ cards: graphic-led ones show no duplicate headline (title kept for screen readers); image-led ones show the card_title")
    check(all(e.get("card_style") in ("graphic", "image") for e in allm), "every manifest entry has a card_style (graphic or image)")
    code2, out2 = run(r, "build")
    check(code2 == 0 and "0 file(s) written" in out2, "second build writes nothing (deterministic)", out2[-200:])

    # ---- 2. never delete a live story whose source is missing
    r = copy_repo(); run(r, "build"); before = tree(os.path.join(r, "stories"))
    shutil.rmtree(os.path.join(r, "_editorial/stories/red-river-2026"))
    code, out = run(r, "build"); after = tree(os.path.join(r, "stories"))
    check(code == 0 and "KEPT" in out, "build with Red River's source removed still succeeds and reports it kept the story", out[-300:])
    check(all(after.get(k) == v for k, v in before.items() if k.startswith("red-river-2026/")), "Red River files untouched when its source is missing")
    check(set(before) <= set(after), "no file under stories/ was deleted")
    man = json.load(open(os.path.join(r, "stories/stories.json")))
    check("red-river-2026" in [e["slug"] for e in man["stories"]] and len(man["stories"]) == N_LIVE, "Red River stays in the manifest (and every other live story with it)")
    check("/stories/red-river-2026/" in open(os.path.join(r, "stories/index.html")).read(), "Red River stays on /stories/")
    check("/stories/red-river-2026/" in open(os.path.join(r, "stories/sitemap.xml")).read(), "Red River stays in the sitemap")
    # even with no manifest at all (a hand-made live page): described from its own meta tags, never dropped
    os.remove(os.path.join(r, "stories/stories.json")); code, out = run(r, "build")
    man = json.load(open(os.path.join(r, "stories/stories.json")))
    rr = [e for e in man["stories"] if e["slug"] == "red-river-2026"]
    check(code == 0 and rr and rr[0]["title"].startswith("BOOMER SOONER"), "with no manifest and no source, the live page is still listed (from its meta tags)")

    # ---- 3. nothing publishes without approval; drafts never enter the public output
    for label, edit in [
        ("a draft (status: draft) in _editorial/stories", lambda t: t),
        ("status: published but no approval on record", lambda t: t.replace("status: draft", "status: published")),
    ]:
        r = copy_repo(); before = tree(os.path.join(r, "stories"))
        d = make_draft(os.path.join(r, "_editorial/stories")); open(os.path.join(d, "story.md"), "w").write(edit(SAMPLE))
        code, out = run(r, "build")
        check(code != 0 and tree(os.path.join(r, "stories")) == before, f"build refuses {label} and writes nothing", out[-200:])

    # ---- 4. validation stops bad sources (and writes nothing)
    approved = SAMPLE.replace("status: draft", "status: published\napproved_by: Matthew McBrayer\napproved_at: '2026-10-11'")
    bad = {
        "unknown team slug": approved.replace("teams: [baylor]", "teams: [baylorr]"),
        "missing dek": approved.replace("dek: A sample dek that only exists inside the test suite.\n", ""),
        "card_title over 60 characters": approved.replace("status: published", "status: published\ncard_title: '" + "X" * 61 + "'"),
        "unknown card_style": approved.replace("status: published", "status: published\ncard_style: poster"),
        "'2.0' in the copy": approved.replace("The opening paragraph", "The DAWG 2.0 opening paragraph"),
        "future date": approved.replace("date: '2026-10-11'", "date: '2030-01-01'"),
        "slug that collides with a team page": approved,
    }
    for label, text in bad.items():
        r = copy_repo(); before = tree(os.path.join(r, "stories"))
        slug = "baylor" if "collides" in label else "test-sample-story"
        make_draft(os.path.join(r, "_editorial/stories"), slug, text)
        code, out = run(r, "build")
        check(code != 0 and tree(os.path.join(r, "stories")) == before, f"build refuses a story with {label}", out[-160:])
    r = copy_repo(); d = make_draft(os.path.join(r, "_editorial/stories"), text=approved.replace("image_alt: Sample card image.", "image_alt: Sample card image.\nog_image: card.png"))
    code, out = run(r, "build")
    check(code != 0 and "1200x630" in out, "build refuses an og_image that isn't 1200x630", out[-160:])
    r = copy_repo(); make_draft(os.path.join(r, "_editorial/stories"), text=approved); d2 = make_draft(os.path.join(r, "_editorial/stories"), "test-sample-two", approved)
    open(os.path.join(d2, "story.md"), "w").write(approved)   # same slug inside a differently named folder
    code, out = run(r, "build")
    check(code != 0, "build refuses a duplicate slug / folder mismatch", out[-160:])

    r = copy_repo(); d = make_draft(os.path.join(r, "_editorial/stories"), text=approved.replace("title: Sample Story for the Test Suite", "title: Sample: Story"))
    code, out = run(r, "build")
    check(code == 1 and "Traceback" not in out and "valid YAML" in out, "a front-matter typo stops the build with a readable message", out[-200:])

    # ---- 5. private preview, then approval, then publish
    r = copy_repo(); drafts = tempfile.mkdtemp(prefix="drafts-"); prev = tempfile.mkdtemp(prefix="preview-")
    d = make_draft(drafts); repo_before = tree(r)
    code, out = run(r, "preview", d, "--out", prev)
    check(code == 0, "preview renders a draft", out[-200:])
    pp = open(os.path.join(prev, "test-sample-story/index.html")).read()
    check('name="robots" content="noindex, nofollow"' in pp and "Preview · not published" in pp, "preview page is marked noindex and carries a 'not published' banner")
    check(tree(r) == repo_before, "preview writes nothing inside the repo")
    check(all(os.path.isfile(os.path.join(prev, "test-sample-story", f)) for f in ("preview-desktop.png", "preview-phone.png")), "preview makes desktop and phone screenshots")
    code, out = run(r, "preview", d, "--out", os.path.join(r, "stories"))
    check(code != 0 and "outside the site repo" in out, "preview refuses to write inside the repo")
    code, out = run(r, "approve", d)
    check(code != 0 and not os.path.exists(os.path.join(r, "_editorial/stories/test-sample-story")), "approve without --by is refused")
    code, out = run(r, "approve", d, "--by", "Matthew McBrayer")
    fm, _ = B.parse_story(os.path.join(r, "_editorial/stories/test-sample-story/story.md"))
    check(code == 0 and fm["status"] == "published" and fm["approved_by"] == "Matthew McBrayer", "approve --by records the approval and moves the story in", out[-200:])
    code, out = run(r, "build")
    check(code == 0, "build publishes the approved story", out[-300:])
    sp = os.path.join(r, "stories/test-sample-story")
    check(B.png_size(os.path.join(sp, "og.png")) == (1200, 630), "missing og_image: a 1200x630 social card is generated")
    html = open(os.path.join(sp, "index.html")).read()
    check('<aside class="doesnt"' in html and '<table class="tbl">' in html and "<h2>A section heading</h2>" in html, "Markdown body renders with the article styles (heading, table, 'doesn't tell us' box)")
    check("noindex" not in html and "Preview" not in html, "published page has no preview banner or noindex")
    man = json.load(open(os.path.join(r, "stories/stories.json")))["stories"]
    check(len(man) == N_LIVE + 1 and all(man[i]["date"] >= man[i + 1]["date"] for i in range(len(man) - 1)), "manifest lists every live story plus the new one, newest first")
    idx = open(os.path.join(r, "stories/index.html")).read()
    check(idx.count('class="st-card') == N_LIVE + 1, "/stories/ shows every story")
    smp = [e for e in man if e["slug"] == "test-sample-story"]
    check(smp and smp[0]["card_style"] == "image" and f'<a class="st-card i" href="/stories/test-sample-story/">' in idx and f'<h2 class="st-t">{B.t(smp[0]["card_title"])}</h2>' in idx,
          "a story without card_style defaults to image-led: its title shows under the image")
    sm = open(os.path.join(r, "stories/sitemap.xml")).read(); xml.dom.minidom.parseString(sm)
    check(sm.count("<loc>") == N_LIVE + 2, "sitemap is valid XML with /stories/ and every story")
    published_copy = r

    # ---- 6. every published page: social tags, links, images, phone layout
    from playwright.sync_api import sync_playwright
    pages = ["stories/index.html", "stories/red-river-2026/index.html", "stories/test-sample-story/index.html"]
    for pth in pages:
        s = open(os.path.join(published_copy, pth)).read()
        tags = dict(re.findall(r'<meta (?:property|name)="((?:og|twitter):[a-z:]+)" content="([^"]*)"', s))
        img = tags.get("og:image", "")
        local = os.path.join(published_copy, img.replace(B.SITE + "/", "")) if img.startswith(B.SITE) else ""
        ok = all(k in tags for k in ("og:title", "og:description", "og:image", "twitter:card", "twitter:image")) and tags.get("twitter:card") == "summary_large_image" and local and B.png_size(local) == (1200, 630)
        check(ok, f"{pth}: social preview tags complete, image exists and is 1200x630")
        refs = [u for u in re.findall(r'(?:href|src)="(/[^"#?]*)', s)]
        missing = [u for u in refs if not (os.path.isfile(os.path.join(published_copy, u.lstrip("/"))) or os.path.isfile(os.path.join(published_copy, u.lstrip("/"), "index.html")) or u == "/")]
        check(not missing, f"{pth}: every local link and image resolves", ", ".join(missing[:5]))
    import mimetypes, requests
    S = requests.Session(); S.verify = B.CA if os.path.exists(B.CA) else True
    def route(rt):
        u = rt.request.url
        if u.startswith("https://preview.local/"):
            f = os.path.join(published_copy, u.split("https://preview.local/", 1)[1].split("?")[0])
            if os.path.isdir(f): f = os.path.join(f, "index.html")
            return rt.fulfill(status=200 if os.path.isfile(f) else 404, body=open(f, "rb").read() if os.path.isfile(f) else b"", headers={"content-type": mimetypes.guess_type(f)[0] or "text/html"})
        if "fonts.g" in u:
            x = S.get(u, timeout=30); return rt.fulfill(status=x.status_code, body=x.content, headers={"content-type": x.headers.get("content-type", "")})
        return rt.fulfill(status=404, body=b"")
    with sync_playwright() as p:
        b = p.chromium.launch()
        for w in (360, 390, 1280):
            c = b.new_context(viewport={"width": w, "height": 800}, is_mobile=w < 600, has_touch=w < 600); c.route("**/*", route); pg = c.new_page()
            for pth in pages:
                errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
                pg.goto("https://preview.local/" + pth.replace("index.html", "")); pg.evaluate("document.fonts.ready"); pg.wait_for_timeout(200)
                ov = pg.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
                broken = pg.evaluate("[...document.images].filter(i=>!i.complete||i.naturalWidth===0).map(i=>i.src)")
                check(ov == 0 and not broken and not errs, f"{pth} at {w}px: no sideways scroll, no broken images, no script errors", f"overflow {ov}, broken {broken}, errors {errs}")
            c.close()
        # pixel parity: live Red River (from main) vs the built one, desktop and phone
        live_dir = tempfile.mkdtemp(prefix="live-"); os.makedirs(os.path.join(live_dir, "stories/red-river-2026"))
        open(os.path.join(live_dir, "stories/red-river-2026/index.html"), "wb").write(live_page)
        from PIL import Image, ImageChops
        for w, dsf in ((1280, 1), (390, 2), (360, 2)):
            shots = []
            def make_rt2(src):
                def rt2(rt):
                    u = rt.request.url
                    if u.startswith("https://preview.local/"):
                        rel = u.split("https://preview.local/", 1)[1].split("?")[0]
                        f = os.path.join(src if rel.startswith("stories/red-river-2026/index") or rel == "stories/red-river-2026/" else REPO, rel)
                        if os.path.isdir(f): f = os.path.join(f, "index.html")
                        return rt.fulfill(status=200 if os.path.isfile(f) else 404, body=open(f, "rb").read() if os.path.isfile(f) else b"", headers={"content-type": mimetypes.guess_type(f)[0] or "text/html"})
                    return route(rt)
                return rt2
            for src in (live_dir, published_copy):
                c = b.new_context(viewport={"width": w, "height": 900}, device_scale_factor=dsf, is_mobile=w < 600, has_touch=w < 600); c.route("**/*", make_rt2(src)); pg = c.new_page()
                pg.goto("https://preview.local/stories/red-river-2026/"); pg.evaluate("document.fonts.ready"); pg.wait_for_timeout(400)
                f = os.path.join(live_dir, f"shot-{len(shots)}-{w}.png"); pg.locator("article").screenshot(path=f); shots.append(f); c.close()
            A, Bm = Image.open(shots[0]).convert("RGB"), Image.open(shots[1]).convert("RGB")
            same = A.size == Bm.size and ImageChops.difference(A, Bm).getbbox() is None
            check(same, f"Red River article looks identical to live at {w}px (pixel-for-pixel, {A.size[0]}x{A.size[1]})")
        b.close()

    # ---- 7. the real repo: build only ever touches _editorial/ and stories/
    st = subprocess.run(["git", "-C", REPO, "status", "--porcelain"], capture_output=True, text=True).stdout.split("\n")
    outside = [l for l in st if l.strip() and not re.match(r"^.. (_editorial/|stories/)", l)]
    check(not outside, "in the real repo, every change is under _editorial/ or stories/", "; ".join(outside[:5]))
    r = copy_repo(); before = {k: v for k, v in tree(r).items() if not k.startswith("stories/")}
    os.remove(os.path.join(r, "stories/stories.json")); run(r, "build")
    after = {k: v for k, v in tree(r).items() if not k.startswith("stories/")}
    check(before == after, "a full build changes nothing outside stories/ (homepage, team pages, data untouched)")

    n_ok = sum(1 for ok, _, _ in RESULTS if ok)
    print(f"\n{n_ok} of {len(RESULTS)} checks passed")
    sys.exit(0 if n_ok == len(RESULTS) else 1)

if __name__ == "__main__":
    main()
