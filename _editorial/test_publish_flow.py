#!/usr/bin/env python3
"""End-to-end check of publishing a new story, on a throwaway copy of the site (the real repo is only read).

  python3 _editorial/test_publish_flow.py

draft -> private preview -> approve --by -> build, then the built homepage and team pages are opened in a browser to
confirm the new story appears with no hand edits to any HTML page outside stories/.
"""
import hashlib, json, mimetypes, os, shutil, subprocess, sys, tempfile
import requests
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE)
CA = "/root/.ccr/ca-bundle.crt"; S = requests.Session(); S.verify = CA if os.path.exists(CA) else True
RESULTS = []
def check(ok, name, detail=""):
    RESULTS.append(bool(ok)); print(("PASS  " if ok else "FAIL  ") + name + (f"  ({detail})" if detail and not ok else ""))
def sha(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()
def tree(root, skip=("stories/", "_editorial/")):
    out = {}
    for d, _, fs in os.walk(root):
        for f in fs:
            p = os.path.join(d, f); rel = os.path.relpath(p, root)
            if not rel.startswith(skip) and "__pycache__" not in rel: out[rel] = sha(p)
    return out

tmp = tempfile.mkdtemp(prefix="flow-"); site = os.path.join(tmp, "site"); drafts = os.path.join(tmp, "drafts"); prev = os.path.join(tmp, "preview")
shutil.copytree(REPO, site, ignore=shutil.ignore_patterns(".git", "__pycache__"))
def run(*a):
    p = subprocess.run([sys.executable, os.path.join(site, "_editorial/build.py"), *a, "--repo", site], capture_output=True, text=True); return p.returncode, p.stdout + p.stderr
before = tree(site)
man0 = json.load(open(os.path.join(site, "stories/stories.json")))["stories"]

# a new story tagged Baylor (no story yet) and Oklahoma (already has Red River)
d = os.path.join(drafts, "flow-test-story"); os.makedirs(d)
shutil.copy(os.path.join(site, "_editorial/stories/red-river-2026/card.png"), os.path.join(d, "card.png"))
open(os.path.join(d, "story.md"), "w").write("""---
slug: flow-test-story
status: draft
title: "Flow Test: A New Story Appears Everywhere"
tab: Test · Week 6
category: Analysis
date: '2026-10-12'
teams: [baylor, oklahoma]
dek: A throwaway story that proves publishing needs no hand-edited HTML.
description: A throwaway story used only by the publishing-flow test.
image: card.png
image_alt: Sample card.
---
Body text.

::: doesnt
This story exists only inside the test.
:::
""")
# and a second draft that is never approved
d2 = os.path.join(drafts, "flow-unapproved"); shutil.copytree(d, d2)
open(os.path.join(d2, "story.md"), "w").write(open(os.path.join(d, "story.md")).read().replace("flow-test-story", "flow-unapproved").replace("Flow Test: A New Story", "UNAPPROVED DRAFT"))

code, out = run("preview", d, "--out", prev, "--no-shots")
check(code == 0 and json.load(open(os.path.join(site, "stories/stories.json")))["stories"] == man0, "preview leaves the published story list untouched", out[-200:])
code, out = run("approve", d, "--by", "Matthew McBrayer")
check(code == 0, "approve --by moves the draft in with the approval on record", out[-200:])
code, out = run("build")
check(code == 0, "build succeeds", out[-300:])
man = json.load(open(os.path.join(site, "stories/stories.json")))["stories"]
new = [e for e in man if e["slug"] == "flow-test-story"]
check(len(man) == len(man0) + 1 and new and new[0]["status"] == "published" and new[0]["team_ids"] == ["239", "201"],
      "manifest gains the new story automatically (published, team IDs Baylor 239 and Oklahoma 201)", str(new))
check(not any(e["slug"] == "flow-unapproved" for e in man), "the unapproved draft is not in the manifest")
import datetime as _dt
from zoneinfo import ZoneInfo as _Z
check(new and new[0]["date"] == _dt.datetime.now(_Z("America/Chicago")).date().isoformat() and new[0].get("published_at", "").endswith("Z"),
      "approve sets the story date to the day it goes live (Central) and records published_at", str(new[:1]))
check(os.path.isfile(os.path.join(site, "stories/flow-test-story/index.html")) and os.path.isfile(os.path.join(site, "stories/flow-test-story/og.png")),
      "story page and social image are generated")
check(tree(site) == before, "no file outside stories/ and _editorial/ changed: homepage, team pages and data are not edited by hand or by the build")

def route(r):
    u = r.request.url
    if u.startswith("https://preview.local/"):
        path = u.split("https://preview.local/", 1)[1].split("?")[0].split("#")[0]; f = os.path.join(site, path)
        if os.path.isdir(f): f = os.path.join(f, "index.html")
        return r.fulfill(status=200 if os.path.isfile(f) else 404, body=open(f, "rb").read() if os.path.isfile(f) else b"", headers={"content-type": mimetypes.guess_type(f)[0] or "text/html"})
    if "fonts.g" in u:
        x = S.get(u, timeout=30); return r.fulfill(status=x.status_code, body=x.content, headers={"content-type": x.headers.get("content-type", "")})
    return r.fulfill(status=204, body=b"")
R = "document.getElementById('home-host').shadowRoot"
with sync_playwright() as p:
    b = p.chromium.launch()
    for w in (1280, 390):
        c = b.new_context(viewport={"width": w, "height": 900}, is_mobile=w < 600, has_touch=w < 600); c.route("**/*", route); pg = c.new_page()
        pg.goto("https://preview.local/"); pg.wait_for_function("document.getElementById('home-host').getAttribute('data-ready') === '1'"); pg.wait_for_timeout(1200)
        o = pg.evaluate(f"(() => {{ const r = {R}; const c = [...r.querySelectorAll('#bt-grid .bt-card')].map(a => a.getAttribute('href')); return {{lead: c[0], items: c.slice(1), text: r.getElementById('beyond-sec').textContent}}; }})()")
        check(o["lead"] == "/stories/flow-test-story/" and o["items"] == [e["url"] for e in man0][:3], f"{w}px homepage: the new story leads Beyond the Score, the earlier stories move to the list in order", str(o))
        check("UNAPPROVED" not in o["text"], f"{w}px homepage: the unapproved draft never appears")
        for slug, expect in (("baylor", ["/stories/flow-test-story/"]), ("oklahoma", ["/stories/flow-test-story/", "/stories/red-river-2026/"]), ("texas", ["/stories/red-river-2026/"])):
            pg.goto(f"https://preview.local/?team={slug}"); pg.wait_for_timeout(2500)
            links = pg.evaluate(f"(() => {{ const r = {R}; const s = r.getElementById('t-stories'); return s.hidden ? [] : [...s.querySelectorAll('.bt-card')].map(a => a.getAttribute('href')); }})()")
            check(links == expect, f"{w}px {slug} team page lists {len(expect)} stor{'y' if len(expect) == 1 else 'ies'}, newest first", str(links))
        pg.goto("https://preview.local/stories/"); pg.wait_for_timeout(600)
        cards = pg.evaluate("[...document.querySelectorAll('a.st-card')].map(a => a.getAttribute('href'))")
        check(cards == ["/stories/flow-test-story/"] + [e["url"] for e in man0], f"{w}px /stories/ archive lists the new story first, then every earlier story", str(cards))
        c.close()
    b.close()
sm = open(os.path.join(site, "stories/sitemap.xml")).read()
check("/stories/flow-test-story/" in sm, "sitemap gains the new story")
shutil.rmtree(tmp)
print(f"\n{sum(RESULTS)} of {len(RESULTS)} checks passed")
sys.exit(0 if all(RESULTS) else 1)
