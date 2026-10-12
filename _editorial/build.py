#!/usr/bin/env python3
"""DAWG editorial build. Turns approved story sources into the public /stories/ pages.

Kept apart from the V3 grading pipeline: it reads only _editorial/ and sitemap.xml (for the list of team slugs), and writes
only under stories/. It never deletes anything.

  python3 _editorial/build.py build              render every approved story in _editorial/stories/ into stories/
  python3 _editorial/build.py check              validate sources and show what build would do; writes nothing
  python3 _editorial/build.py preview DRAFT_DIR  render one draft privately (outside the repo) with desktop + phone screenshots
  python3 _editorial/build.py approve DRAFT_DIR --by "Matthew McBrayer"
                                                 move a draft into _editorial/stories/ as published (only after Matthew's explicit OK)

Rules this script enforces:
  1. Nothing is published without approval: a story in _editorial/stories/ must say status: published, approved_by and
     approved_at, or the build stops and writes nothing. Drafts never live in the repo (it is public); they live in the
     private drafts folder (default /home/claude/editorial-drafts) and are previewed outside the repo.
  2. Live stories are never deleted: a published story whose source is missing keeps its files, its manifest entry,
     its place on /stories/ and in the sitemap. The script has no code path that removes a file.
  3. Output is deterministic: the same sources produce byte-identical files.
"""
import argparse, datetime as dt, html, json, os, re, shutil, sys, tempfile
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = "https://dawgindex.com"
REQUIRED = ["slug", "status", "title", "tab", "category", "date", "teams", "dek", "description", "thumb"]
PUBLISH_REQUIRED = ["approved_by", "approved_at"]
NOT_TEAMS = {"stories", "v2", "brand", "data", "logos", "code", "_editorial"}
DRAFTS = "/home/claude/editorial-drafts"
PREVIEWS = "/home/claude/editorial-preview"
CA = "/root/.ccr/ca-bundle.crt"


class BuildError(Exception):
    pass


# ---------------------------------------------------------------- helpers
def t(s):        # text node
    return html.escape(str(s), quote=False)


def a(s):        # attribute value (keeps apostrophes literal, like the hand-made page)
    return html.escape(str(s), quote=False).replace('"', "&quot;")


def read(p, mode="r"):
    with open(p, mode) as f:
        return f.read()


def write_if_changed(path, data, log):
    """Write only when bytes differ, so untouched files keep their timestamps and git sees no change."""
    b = data.encode() if isinstance(data, str) else data
    if os.path.isfile(path) and read(path, "rb") == b:
        return False
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp-editorial"
    with open(tmp, "wb") as f:
        f.write(b)
    os.replace(tmp, path)
    log.append(("wrote", os.path.relpath(path)))
    return True


def png_size(p):
    with open(p, "rb") as f:
        head = f.read(24)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return int.from_bytes(head[16:20], "big"), int.from_bytes(head[20:24], "big")


def png_text(path, key):
    """One tEXt chunk from a PNG (thumbs.py stamps thumb.png with a hash of the thumb: block it was drawn from)."""
    try:
        with open(path, "rb") as f:
            d = f.read()
    except OSError:
        return None
    if d[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    i = 8
    while i + 8 <= len(d):
        n, typ = int.from_bytes(d[i:i + 4], "big"), d[i + 4:i + 8]
        if typ == b"tEXt":
            k, _, v = d[i + 8:i + 8 + n].partition(b"\0")
            if k.decode("latin-1") == key:
                return v.decode("latin-1")
        if typ == b"IEND":
            break
        i += 12 + n
    return None


def spec_hash(spec):
    import hashlib
    return hashlib.sha256(json.dumps(spec, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


def nice_date(d):
    d = dt.date.fromisoformat(d)
    m = ["Jan.", "Feb.", "March", "April", "May", "June", "July", "Aug.", "Sept.", "Oct.", "Nov.", "Dec."][d.month - 1]
    return f"{m} {d.day}, {d.year}"


def parse_story(path):
    raw = read(path)
    if not raw.startswith("---\n"):
        raise BuildError(f"{path}: must start with a --- front-matter block")
    if "\n---\n" not in raw[3:]:
        raise BuildError(f"{path}: front matter has no closing ---")
    end = raw.index("\n---\n", 4)
    try:
        fm = yaml.safe_load(raw[4:end]) or {}
    except yaml.YAMLError as e:
        raise BuildError(f"{path}: front matter isn't valid YAML (quote any value containing a colon): {str(e).splitlines()[0]}")
    body = raw[end + 5:]
    for k in ("date", "approved_at"):
        if isinstance(fm.get(k), (dt.date, dt.datetime)):
            fm[k] = fm[k].isoformat()[:10]
    if isinstance(fm.get("published_at"), dt.datetime):
        fm["published_at"] = fm["published_at"].astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return fm, body


def local_now():
    try:
        from zoneinfo import ZoneInfo
        return dt.datetime.now(ZoneInfo("America/Chicago"))
    except Exception:
        return dt.datetime.now(dt.timezone.utc)


def team_slugs(repo):
    """The 68 team page slugs, read from the site's own sitemap (written by the weekly build)."""
    sm = os.path.join(repo, "sitemap.xml")
    slugs = set()
    if os.path.isfile(sm):
        for loc in re.findall(r"<loc>https://dawgindex\.com/([a-z0-9-]+)/</loc>", read(sm)):
            if loc not in NOT_TEAMS:
                slugs.add(loc)
    if not slugs:
        raise BuildError("couldn't read the team list from sitemap.xml")
    return slugs


def team_ids(repo):
    """slug -> ESPN team id, from the published team data files (the same files the team pages read)."""
    import glob
    out = {}
    for f in glob.glob(os.path.join(repo, "data", "team", "*.json")):
        d = json.loads(read(f))
        out[re.sub(r"['&]", "", d["name"].lower().replace(" ", "-"))] = str(d["id"])
    return out


def team_names(repo, slugs):
    out = {}
    for s in slugs:
        p = os.path.join(repo, s, "index.html")
        m = re.search(r'<meta property="og:title" content="([^"]+?) · DAWG Index"', read(p)) if os.path.isfile(p) else None
        out[s] = html.unescape(m.group(1)) if m else s.replace("-", " ").title()
    return out


# ---------------------------------------------------------------- validation
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
TWO_POINT_OH = re.compile(r"(?<![\d.])2\.0(?!\d)")


def validate(fm, body, src_dir, teams, mode):
    errs = []
    for k in REQUIRED:
        if fm.get(k) in (None, "", []) and not (k == "teams" and fm.get(k) == []):
            errs.append(f"missing {k}")
    slug = fm.get("slug", "")
    if slug and not SLUG.match(slug):
        errs.append(f"slug '{slug}' must be lowercase letters, digits and hyphens")
    if slug and os.path.basename(src_dir.rstrip("/")) != slug:
        errs.append(f"folder name must equal slug '{slug}'")
    if slug in NOT_TEAMS or slug in teams:
        errs.append(f"slug '{slug}' collides with an existing site folder")
    st = fm.get("status")
    if st not in ("draft", "published"):
        errs.append("status must be draft or published")
    if mode == "publish":
        if st != "published":
            errs.append("status is not 'published' (drafts don't belong in _editorial/stories/, which is public)")
        for k in PUBLISH_REQUIRED:
            if not fm.get(k):
                errs.append(f"missing {k}: a story is published only with Matthew's explicit approval on record")
    try:
        d = dt.date.fromisoformat(str(fm.get("date")))
        if d > dt.date.today() + dt.timedelta(days=1):
            errs.append("date is in the future (scheduled publishing isn't supported)")
    except ValueError:
        errs.append("date must be YYYY-MM-DD")
    for tm in fm.get("teams") or []:
        if tm not in teams:
            errs.append(f"unknown team slug '{tm}'")
    # the card picture: thumb.png, drawn by thumbs.py from the thumb: block (logos plus one number, a score or a short run of
    # results; never the headline, which the card prints underneath)
    if fm.get("thumb"):
        sys.path.insert(0, HERE)
        dwb, sys.dont_write_bytecode = sys.dont_write_bytecode, True   # validating must not leave a __pycache__ behind
        import thumbs
        sys.dont_write_bytecode = dwb
        errs += thumbs.check_spec(fm["thumb"])
        tp = os.path.join(src_dir, "thumb.png")
        if not os.path.isfile(tp) or png_size(tp) != (1200, 675):
            errs.append("thumb.png missing or not 1200x675: run python3 _editorial/thumbs.py " + src_dir)
        elif png_text(tp, "dawg-thumb") != spec_hash(fm["thumb"]):
            errs.append("thumb.png doesn't match the thumb: block in story.md: run python3 _editorial/thumbs.py " + src_dir)
    # optional: the detailed story graphic (kept as card.png for sharing; never used as the card picture)
    img = os.path.join(src_dir, str(fm.get("image", "")))
    if fm.get("image"):
        sz = png_size(img) if os.path.isfile(img) else None
        if not sz:
            errs.append(f"story graphic {fm['image']} missing or not a PNG")
        elif sz[0] < 1200 or abs(sz[0] / sz[1] - 16 / 9) > 0.02:
            errs.append(f"story graphic must be 16:9 and at least 1200 wide (is {sz[0]}x{sz[1]})")
    og = fm.get("og_image")
    if og:
        p = os.path.join(src_dir, og)
        if not os.path.isfile(p) or png_size(p) != (1200, 630):
            errs.append(f"og_image {og} must be a 1200x630 PNG")
    sb = fm.get("scoreboard")
    if sb:
        for k in ("label", "left", "right", "mid"):
            if k not in sb:
                errs.append(f"scoreboard needs {k}")
    if fm.get("format", "markdown") not in ("markdown", "html"):
        errs.append("format must be markdown or html")
    copy = " ".join(str(fm.get(k, "")) for k in ("title", "dek", "description", "social_description", "card_dek", "card_title", "tab")) + " " + str((fm.get("thumb") or {}).get("label", "")) + " " + re.sub(r"<[^>]+>", " ", body)
    if TWO_POINT_OH.search(copy):
        errs.append("'2.0' appears in the copy (internal name; never public)")
    if fm.get("card_style", "image") != "image":
        errs.append("card_style is retired: every card shows a simple thumbnail with the headline printed under it")
    if fm.get("card_teaser"):
        errs.append("card_teaser isn't shown on cards; remove it")
    if fm.get("card_title") and len(str(fm["card_title"])) > 60:
        errs.append("card_title over 60 characters (it's the short title on homepage and Stories cards)")
    if len(str(fm.get("description", ""))) > 200:
        errs.append("description over 200 characters")
    return errs


# ---------------------------------------------------------------- rendering
def render_body(fm, body):
    if fm.get("format", "markdown") == "html":
        return body
    import markdown
    md = lambda x: markdown.markdown(x, extensions=["tables", "sane_lists"], output_format="html")
    boxes = {}
    def box(m):
        kind, inner = m.group(1), m.group(2)
        if kind == "doesnt":
            h = ('<aside class="doesnt" aria-label="What this doesn\'t tell us">\n<h3>What this doesn\'t tell us</h3>\n'
                 + md(inner) + "\n</aside>")
        elif kind == "pull":
            h = '<div class="pull">' + re.sub(r"^<p>|</p>$", "", md(inner).strip()) + "</div>"
        else:
            raise BuildError(f"unknown block ::: {kind}")
        key = f"EDITORIALBOX{len(boxes)}X"
        boxes[key] = h
        return "\n" + key + "\n"
    src = re.sub(r"^::: *(\w+)\n(.*?)\n:::$", box, body, flags=re.S | re.M)
    out = md(src)
    for k, v in boxes.items():
        out = out.replace(f"<p>{k}</p>", v)
    out = re.sub(r"<table>", '<table class="tbl">', out)
    # first cell of each body row is the row label, as in the hand-made tables
    out = re.sub(r"<tbody>.*?</tbody>", lambda m: re.sub(r"<tr>\s*<td>(.*?)</td>", r'<tr>\n<th scope="row">\1</th>', m.group(0), flags=re.S), out, flags=re.S)
    out = out.replace("<thead>\n<tr>\n<th></th>", '<thead>\n<tr>\n<th scope="col"></th>')
    return "\n".join("      " + ln if ln.strip() else "" for ln in out.split("\n")) + "\n"


def article_head(fm):
    h = fm.get("headline") or {}
    big, sub = h.get("big") or fm["title"], h.get("sub")
    st = fm.get("stamp") or [nice_date(fm["date"])]
    L = [f'      <span class="tab">{t(fm["tab"])}</span>',
         f'      <h1><span class="big">{t(big)}</span>' + (f'<span class="sub">{t(sub)}</span>' if sub else "") + "</h1>",
         f'      <p class="dek">{t(fm["dek"])}</p>',
         f'      <div class="stamp"><b>{t(st[0])}</b>' + "".join(f" · {t(x)}" for x in st[1:]) + "</div>"]
    sb = fm.get("scoreboard")
    if sb:
        side = lambda s, r: (f'        <div class="side{" r" if r else ""}"><div class="nm">{t(s["name"])}</div>'
                             f'<div class="rk">{t(s.get("note", ""))}</div><div class="pts">{t(s["pts"])}</div></div>')
        mid = sb["mid"]
        L += [f'      <div class="score" role="img" aria-label="{a(sb["label"])}">', side(sb["left"], False),
              f'        <div class="mid">{t(mid[0])}' + (f"<span>{t(mid[1])}</span>" if len(mid) > 1 else "") + "</div>",
              side(sb["right"], True), "      </div>"]
        if sb.get("note"):
            L.append(f'      <p class="score-note">{t(sb["note"])}</p>')
    return "\n".join(L)


def story_page(fm, body, tpl_dir, preview=False):
    url = f"{SITE}/stories/{fm['slug']}/"
    og = url + "og.png"
    ld = {"@context": "https://schema.org", "@type": "NewsArticle", "headline": fm["title"], "datePublished": fm["date"],
          "author": {"@type": "Organization", "name": "DAWG Index"},
          "publisher": {"@type": "Organization", "name": "DAWG Index", "url": SITE}, "image": og, "mainEntityOfPage": url}
    if fm.get("updated"):
        ld["dateModified"] = fm["updated"]
    social = fm.get("social_description") or fm["description"]
    page = read(os.path.join(tpl_dir, "article.html"))
    rep = {"{{CSS}}": read(os.path.join(tpl_dir, "story.css")).rstrip("\n"), "{{TITLE}}": a(fm["title"]),
           "{{DESCRIPTION}}": a(fm["description"]), "{{URL}}": url, "{{SOCIAL}}": a(social), "{{OG}}": og,
           "{{DATE}}": fm["date"], "{{JSONLD}}": '<script type="application/ld+json">' + json.dumps(ld, ensure_ascii=False, separators=(",", ":")) + "</script>",
           "{{ROBOTS}}": '\n<meta name="robots" content="noindex, nofollow">' if preview else "",
           "{{ARTICLE_HEAD}}": article_head(fm), "{{BODY}}": render_body(fm, body).rstrip("\n")}
    for k, v in rep.items():
        page = page.replace(k, v)
    if preview:
        page = page.replace("<body>", '<body>\n<div style="background:#E5463A;color:#fff;font:700 14px/1.4 Barlow,sans-serif;letter-spacing:.08em;text-transform:uppercase;text-align:center;padding:10px 16px">Preview · not published · only Matthew can approve</div>', 1)
    if "{{" in page:
        raise BuildError("template placeholder left unfilled: " + re.search(r"\{\{[A-Z_]+\}\}", page).group(0))
    return page


def manifest_entry(fm, ids, names):
    base = f"/stories/{fm['slug']}/"
    h = fm.get("headline") or {}
    teams = list(fm.get("teams") or [])
    e = {"slug": fm["slug"], "status": "published", "url": base, "title": fm["title"], "card_title": fm.get("card_title") or fm["title"],
         "headline": {"big": h.get("big") or fm["title"], "sub": h.get("sub")},
         "tab": fm["tab"], "category": fm["category"], "date": fm["date"], "teams": teams,
         "team_ids": [ids[x] for x in teams if x in ids], "team_names": [names.get(x, x) for x in teams],
         "dek": fm.get("card_dek") or fm["dek"], "image": base + "thumb.png", "image_alt": fm["thumb"]["alt"], "og_image": base + "og.png"}
    if fm.get("published_at"):
        e["published_at"] = str(fm["published_at"])
    if fm.get("updated"):
        e["updated"] = fm["updated"]
    return e


def legacy_entry(repo, slug):
    """A live story with no source and no manifest entry (shouldn't happen, but never drop it): describe it from its own meta tags."""
    p = os.path.join(repo, "stories", slug, "index.html")
    s = read(p)
    g = lambda pat: (html.unescape(m.group(1)) if (m := re.search(pat, s)) else "")
    title = g(r'<meta property="og:title" content="([^"]*)"')
    base = f"/stories/{slug}/"
    return {"slug": slug, "status": "published", "url": base, "title": title, "card_title": title, "headline": {"big": title, "sub": None}, "tab": "", "category": "Story",
            "date": g(r'<meta property="article:published_time" content="([^"]*)"') or "1970-01-01", "teams": [], "team_ids": [], "team_names": [],
            "dek": g(r'<meta name="description" content="([^"]*)"'), "og_image": base + "og.png",
            "image": base + ("thumb.png" if os.path.isfile(os.path.join(repo, "stories", slug, "thumb.png")) else "card.png" if os.path.isfile(os.path.join(repo, "stories", slug, "card.png")) else "og.png"), "image_alt": title}


def index_page(entries, tpl_dir, names):
    page = read(os.path.join(tpl_dir, "index.html"))
    css = read(os.path.join(tpl_dir, "story.css")).rstrip("\n") + "\n" + read(os.path.join(tpl_dir, "index.css")).rstrip("\n")
    def logos(e):
        ids = [i for i in (e.get("team_ids") or []) if re.fullmatch(r"\d+", str(i))][:3]
        nm = e.get("team_names") or []
        return "".join(f'<img class="st-logo" src="/logos/{i}.png" alt="{a(nm[k]) if k < len(nm) else ""}" width="26" height="26" loading="lazy">' for k, i in enumerate(ids))
    def card(e, first):
        # every card: a simple thumbnail (never the headline), the short headline under it, then category, team logos and date
        art = f'<div class="st-art"><img src="{e["image"]}" alt="{a(e["image_alt"])}" width="1200" height="675" loading="{"eager" if first else "lazy"}"></div>'
        meta = (f'<div class="st-m"><span class="st-cat">{t(e["category"])}</span><span class="st-logos">{logos(e)}</span>'
                f'<time datetime="{e["date"]}">{t(nice_date(e["date"]))}</time></div>')
        return f'<a class="st-card" href="{e["url"]}">{art}<div class="st-body"><h2 class="st-t">{t(e.get("card_title") or e["title"])}</h2>{meta}</div></a>'
    if entries:
        cards = '<div class="st-grid">\n' + "\n".join(card(e, i < 3) for i, e in enumerate(entries)) + "\n</div>"
    else:
        cards = '<p class="st-empty">No stories yet.</p>'
    ld = {"@context": "https://schema.org", "@type": "CollectionPage", "name": "Beyond the score · DAWG Index", "url": SITE + "/stories/",
          "hasPart": [{"@type": "NewsArticle", "headline": e["title"], "url": SITE + e["url"], "datePublished": e["date"]} for e in entries]}
    rep = {"{{CSS}}": css, "{{CARDS}}": cards, "{{COUNT}}": str(len(entries)),
           "{{OG}}": SITE + (entries[0]["og_image"] if entries else "/og.png"),
           "{{JSONLD}}": '<script type="application/ld+json">' + json.dumps(ld, ensure_ascii=False, separators=(",", ":")) + "</script>"}
    for k, v in rep.items():
        page = page.replace(k, v)
    return page


def sitemap(entries):
    newest = max((e.get("updated") or e["date"]) for e in entries) if entries else None
    rows = [f"<url><loc>{SITE}/stories/</loc>" + (f"<lastmod>{newest}</lastmod>" if newest else "") + "</url>"]
    rows += [f"<url><loc>{SITE}{e['url']}</loc><lastmod>{e.get('updated') or e['date']}</lastmod></url>" for e in entries]
    return '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(rows) + "\n</urlset>\n"


def make_og(fm, out_png, tpl_dir):
    """Auto-generate a 1200x630 social card in the DAWG identity when a story has no custom og_image."""
    from playwright.sync_api import sync_playwright
    import requests
    h = fm.get("headline") or {}
    page = read(os.path.join(tpl_dir, "og.html"))
    for k, v in {"{{TAB}}": t(fm["tab"]), "{{BIG}}": t(h.get("big") or fm["title"]), "{{SUB}}": t(h.get("sub") or ""),
                 "{{DEK}}": t(fm.get("card_dek") or fm["dek"])}.items():
        page = page.replace(k, v)
    S = requests.Session()
    if os.path.exists(CA):
        S.verify = CA
    def route(r):
        u = r.request.url
        if u.startswith("https://og.local/"):
            return r.fulfill(status=200, body=page.encode(), headers={"content-type": "text/html"})
        if "fonts.googleapis.com" in u or "fonts.gstatic.com" in u:
            x = S.get(u, headers={"User-Agent": r.request.headers.get("user-agent", "")}, timeout=30)
            return r.fulfill(status=x.status_code, body=x.content, headers={"content-type": x.headers.get("content-type", "")})
        return r.fulfill(status=404, body=b"")
    with sync_playwright() as p:
        b = p.chromium.launch()
        c = b.new_context(viewport={"width": 1200, "height": 630}, device_scale_factor=1)
        c.route("**/*", route)
        pg = c.new_page()
        pg.goto("https://og.local/")
        pg.evaluate("document.fonts.ready")
        pg.evaluate("window.fit && window.fit()")
        pg.wait_for_timeout(300)
        if not pg.evaluate("document.fonts.check('900 40px \"Big Shoulders Display\"')"):
            raise BuildError("brand fonts didn't load for the social image")
        os.makedirs(os.path.dirname(out_png), exist_ok=True)
        pg.screenshot(path=out_png, clip={"x": 0, "y": 0, "width": 1200, "height": 630})
        b.close()


# ---------------------------------------------------------------- commands
def load_sources(src_root, teams, mode):
    stories, problems = [], []
    if not os.path.isdir(src_root):
        return stories, problems
    for name in sorted(os.listdir(src_root)):
        d = os.path.join(src_root, name)
        if not os.path.isdir(d):
            continue
        p = os.path.join(d, "story.md")
        if not os.path.isfile(p):
            problems.append(f"{name}: no story.md")
            continue
        try:
            fm, body = parse_story(p)
        except Exception as e:
            problems.append(f"{name}: {e}")
            continue
        errs = validate(fm, body, d, teams, mode)
        problems += [f"{name}: {e}" for e in errs]
        stories.append((d, fm, body))
    slugs = [fm.get("slug") for _, fm, _ in stories]
    for s in {x for x in slugs if slugs.count(x) > 1}:
        problems.append(f"duplicate slug {s}")
    return stories, problems


def build(repo, dry=False, quiet=False):
    tpl, src_root, out = os.path.join(repo, "_editorial", "templates"), os.path.join(repo, "_editorial", "stories"), os.path.join(repo, "stories")
    teams = team_slugs(repo)
    stories, problems = load_sources(src_root, teams, "publish")
    if problems:
        raise BuildError("build stopped, nothing written:\n  - " + "\n  - ".join(problems))
    log, notes = [], []
    # what is live now (never shrinks)
    old = {}
    mp = os.path.join(out, "stories.json")
    if os.path.isfile(mp):
        old = {e["slug"]: e for e in json.loads(read(mp)).get("stories", [])}
    live_dirs = {d for d in os.listdir(out) if os.path.isfile(os.path.join(out, d, "index.html"))} if os.path.isdir(out) else set()
    entries = {}
    ids, names = team_ids(repo), team_names(repo, teams)
    missing_ids = sorted(t for t in teams if t not in ids)
    if missing_ids:
        raise BuildError("no team id for: " + ", ".join(missing_ids) + " (data/team/*.json)")
    if dry:
        log.append(("check", f"{len(stories)} approved source(s) valid"))
    for d, fm, body in stories:
        slug = fm["slug"]
        entries[slug] = manifest_entry(fm, ids, names)
        if dry:
            continue
        dest = os.path.join(out, slug)
        write_if_changed(os.path.join(dest, "index.html"), story_page(fm, body, tpl), log)
        write_if_changed(os.path.join(dest, "thumb.png"), read(os.path.join(d, "thumb.png"), "rb"), log)
        if fm.get("image"):
            write_if_changed(os.path.join(dest, "card.png"), read(os.path.join(d, fm["image"]), "rb"), log)
        if fm.get("og_image"):
            write_if_changed(os.path.join(dest, "og.png"), read(os.path.join(d, fm["og_image"]), "rb"), log)
        elif not os.path.isfile(os.path.join(dest, "og.png")):
            make_og(fm, os.path.join(dest, "og.png"), tpl)
            log.append(("wrote", os.path.relpath(os.path.join(dest, "og.png")) + " (auto-generated)"))
    # rule 2: a live story whose source is gone stays exactly as it is
    for slug in sorted((set(old) | live_dirs) - set(entries)):
        if not os.path.isfile(os.path.join(out, slug, "index.html")):
            notes.append(f"{slug}: in the manifest but its page is missing; entry kept, page not touched")
        else:
            notes.append(f"{slug}: no source in _editorial/stories; kept live and untouched")
        entries[slug] = old.get(slug) or legacy_entry(repo, slug)
    ordered = sorted(entries.values(), key=lambda e: (e["date"], e.get("published_at", ""), e["slug"]), reverse=True)   # newest first; same day: latest published first
    if not dry:
        write_if_changed(os.path.join(out, "stories.json"), json.dumps({"version": 1, "stories": ordered}, ensure_ascii=False, indent=1) + "\n", log)
        write_if_changed(os.path.join(out, "index.html"), index_page(ordered, tpl, names), log)
        write_if_changed(os.path.join(out, "sitemap.xml"), sitemap(ordered), log)
    if not quiet:
        for kind, what in log:
            print(f"{kind:7} {what}")
        for n in notes:
            print("KEPT    " + n)
        print(f"{len(ordered)} live stor{'y' if len(ordered) == 1 else 'ies'}; {sum(1 for k, _ in log if k == 'wrote')} file(s) written; nothing deleted")
    return ordered, log, notes


def preview(repo, draft_dir, out_root=PREVIEWS, shots=True):
    draft_dir = os.path.abspath(draft_dir)
    out_root = os.path.abspath(out_root)
    if out_root == os.path.abspath(repo) or out_root.startswith(os.path.abspath(repo) + os.sep):
        raise BuildError("previews must be written outside the site repo (it is public)")
    tpl = os.path.join(repo, "_editorial", "templates")
    fm, body = parse_story(os.path.join(draft_dir, "story.md"))
    errs = validate(fm, body, draft_dir, team_slugs(repo), "preview")
    if errs:
        raise BuildError("preview stopped:\n  - " + "\n  - ".join(errs))
    dest = os.path.join(out_root, fm["slug"])
    log = []
    write_if_changed(os.path.join(dest, "index.html"), story_page(fm, body, tpl, preview=True), log)
    write_if_changed(os.path.join(dest, "thumb.png"), read(os.path.join(draft_dir, "thumb.png"), "rb"), log)
    if fm.get("image"):
        write_if_changed(os.path.join(dest, "card.png"), read(os.path.join(draft_dir, fm["image"]), "rb"), log)
    if fm.get("og_image"):
        write_if_changed(os.path.join(dest, "og.png"), read(os.path.join(draft_dir, fm["og_image"]), "rb"), log)
    else:
        make_og(fm, os.path.join(dest, "og.png"), tpl)
    # how the story's card will look on /stories/ (the homepage and team pages use the same card)
    teams = team_slugs(repo)
    e = manifest_entry(fm, team_ids(repo), team_names(repo, teams))
    e["image"] = "/thumb.png"
    write_if_changed(os.path.join(dest, "card-preview.html"), index_page([e], tpl, team_names(repo, teams)), log)
    if shots:
        screenshot_story(repo, os.path.join(dest, "index.html"), dest)
        screenshot_story(repo, os.path.join(dest, "card-preview.html"), dest, "preview-card")
    print(f"preview written to {dest} (private; not in the repo, marked noindex)")
    return dest


def screenshot_story(repo, page_path, dest, prefix="preview"):
    """Desktop and phone screenshots of a rendered page, with site assets served from the repo."""
    from playwright.sync_api import sync_playwright
    import mimetypes, requests
    S = requests.Session()
    if os.path.exists(CA):
        S.verify = CA
    page_dir, page_name = os.path.dirname(page_path), os.path.basename(page_path)
    def route(r):
        u = r.request.url
        if u.startswith("https://preview.local/"):
            path = u.split("https://preview.local/", 1)[1].split("?")[0].split("#")[0]
            for base in (page_dir if path in ("", page_name, "card.png", "og.png", "thumb.png") else None, repo):
                if not base:
                    continue
                f = os.path.join(base, path or page_name)
                if os.path.isdir(f):
                    f = os.path.join(f, "index.html")
                if os.path.isfile(f):
                    return r.fulfill(status=200, body=read(f, "rb"), headers={"content-type": mimetypes.guess_type(f)[0] or "application/octet-stream"})
            return r.fulfill(status=404, body=b"")
        if "fonts.g" in u:
            x = S.get(u, timeout=30)
            return r.fulfill(status=x.status_code, body=x.content, headers={"content-type": x.headers.get("content-type", "")})
        return r.fulfill(status=404, body=b"")
    with sync_playwright() as p:
        b = p.chromium.launch()
        for name, w, h, dsf, mob in (("desktop", 1280, 900, 1, False), ("phone", 390, 844, 2, True)):
            c = b.new_context(viewport={"width": w, "height": h}, device_scale_factor=dsf, is_mobile=mob, has_touch=mob)
            c.route("**/*", route)
            pg = c.new_page()
            pg.goto("https://preview.local/")
            pg.evaluate("document.fonts.ready")
            pg.wait_for_timeout(500)
            pg.screenshot(path=os.path.join(dest, f"{prefix}-{name}.png"), full_page=True)
            c.close()
        b.close()


def approve(repo, draft_dir, by):
    if not by or not by.strip():
        raise BuildError("approve needs --by (the person who approved it)")
    fm, body = parse_story(os.path.join(draft_dir, "story.md"))
    dest = os.path.join(repo, "_editorial", "stories", fm.get("slug", ""))
    if os.path.exists(dest):
        raise BuildError(f"{dest} already exists; edit it there instead")
    now = local_now()   # publication is stamped in DAWG's home time zone (Central), not the server's
    fm["status"], fm["approved_by"], fm["approved_at"] = "published", by.strip(), now.date().isoformat()
    fm["date"] = now.date().isoformat()                                   # the story's date is the day it goes live
    fm["published_at"] = now.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")   # orders same-day stories
    errs = validate(fm, body, draft_dir, team_slugs(repo), "publish")
    if errs:
        raise BuildError("not approved:\n  - " + "\n  - ".join(errs))
    shutil.copytree(draft_dir, dest, ignore=shutil.ignore_patterns("preview-*.png", ".*"))
    with open(os.path.join(dest, "story.md"), "w") as f:
        f.write("---\n" + yaml.safe_dump(fm, sort_keys=False, allow_unicode=True, width=10000) + "---\n" + body)
    print(f"approved: {fm['slug']} moved to {os.path.relpath(dest, repo)}; run build, then commit _editorial/ and stories/ only")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["build", "check", "preview", "approve"])
    ap.add_argument("path", nargs="?")
    ap.add_argument("--repo", default=os.path.dirname(HERE))
    ap.add_argument("--by")
    ap.add_argument("--out", default=PREVIEWS)
    ap.add_argument("--no-shots", action="store_true")
    o = ap.parse_args()
    try:
        if o.cmd == "build":
            build(o.repo)
        elif o.cmd == "check":
            build(o.repo, dry=True)
        elif o.cmd == "preview":
            if not o.path:
                ap.error("preview needs the draft folder")
            preview(o.repo, o.path, o.out, shots=not o.no_shots)
        elif o.cmd == "approve":
            if not o.path:
                ap.error("approve needs the draft folder")
            approve(o.repo, o.path, o.by)
    except BuildError as e:
        print("ERROR: " + str(e), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
