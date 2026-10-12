#!/usr/bin/env python3
"""Story card thumbnails: one simple picture per story, drawn from a few lines in story.md.

The card shows the headline under the picture, so the picture never repeats it. One idea per thumbnail:
team logos plus one number, a score, or a short run of results. No charts with tiny labels, no source lines.

  python3 _editorial/thumbs.py STORY_DIR            render STORY_DIR/thumb.png (1200x675) from the thumb: block in its story.md
  python3 _editorial/thumbs.py STORY_DIR --check    say whether thumb.png matches the thumb: block, render nothing

Works on a private draft folder (/home/claude/editorial-drafts/<slug>) or an approved story in _editorial/stories/.
Team logos and colours come from ESPN once and are cached in _editorial/thumbs/ (not served by GitHub Pages).

Layouts (teams are site slugs such as oregon, or ESPN ids for teams without a DAWG page):

  thumb:
    layout: stat                 # logos + one big number and a short label
    teams: [oregon, ucla]        # the first team owns the number; the second is the opponent (optional)
    stat: '7'
    label: Turnovers
    alt: Oregon and UCLA logos with the number 7 and the word turnovers.

  thumb:
    layout: score                # final score, with an optional second row (yards, first downs ...)
    teams: [oklahoma, texas]
    score: [27, 24]
    row: {label: Yards, values: [238, 382]}       # optional
    alt: ...

  thumb:
    layout: games                # one team's logo and a short run of DAWG (or other) results as bars
    team: florida
    label: DAWG, last three games
    games: [{opp: ole-miss, value: 19.6}, {opp: missouri, value: -34.0}, {opp: south-carolina, value: -36.2}]
    alt: ...
"""
import argparse, hashlib, html, json, os, re, struct, sys, zlib
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
CACHE = os.path.join(HERE, "thumbs")
CA = "/root/.ccr/ca-bundle.crt"
W, H = 1200, 675
LAYOUTS = ("stat", "score", "games")
FONTS = ("https://fonts.googleapis.com/css2?family=Big+Shoulders+Display:wght@800;900"
         "&family=Barlow+Condensed:wght@700;800&display=swap")

sys.path.insert(0, HERE)
sys.dont_write_bytecode = True   # leave no __pycache__ in the repo
import build as B   # team slug -> id map, story parsing (same rules as the site build)


class ThumbError(Exception):
    pass


def spec_hash(spec):
    return hashlib.sha256(json.dumps(spec, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


def png_text(path, key):
    """Read one tEXt chunk from a PNG (no image library needed; build.py uses this too)."""
    try:
        with open(path, "rb") as f:
            d = f.read()
    except OSError:
        return None
    if d[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    i = 8
    while i + 8 <= len(d):
        n, typ = struct.unpack(">I4s", d[i:i + 8])
        if typ == b"tEXt":
            k, _, v = d[i + 8:i + 8 + n].partition(b"\0")
            if k.decode("latin-1") == key:
                return v.decode("latin-1")
        if typ == b"IEND":
            break
        i += 12 + n
    return None


def add_png_text(data, key, value):
    body = key.encode("latin-1") + b"\0" + value.encode("latin-1")
    chunk = struct.pack(">I", len(body)) + b"tEXt" + body + struct.pack(">I", zlib.crc32(b"tEXt" + body) & 0xffffffff)
    end = 8 + 12 + struct.unpack(">I", data[8:12])[0]   # right after IHDR
    return data[:end] + chunk + data[end:]


# ---------------------------------------------------------------- teams (logo + colour), cached
def _session():
    import requests
    s = requests.Session()
    if os.path.exists(CA):
        s.verify = CA
    return s


def team(ref, ids):
    """ref: site slug or ESPN id -> {id, name, short, color, alt, logo (path to a 500px PNG)}."""
    tid = str(ref) if re.fullmatch(r"\d+", str(ref)) else ids.get(str(ref))
    if not tid:
        raise ThumbError(f"unknown team '{ref}' (use a site slug like oregon, or an ESPN team id)")
    os.makedirs(CACHE, exist_ok=True)
    meta_p, logo_p = os.path.join(CACHE, f"{tid}.json"), os.path.join(CACHE, f"{tid}.png")
    if not (os.path.isfile(meta_p) and os.path.isfile(logo_p)):
        s = _session()
        t = s.get(f"https://site.api.espn.com/apis/site/v2/sports/football/college-football/teams/{tid}", timeout=30).json()["team"]
        meta = {"id": tid, "name": t.get("location") or t["displayName"], "short": t.get("abbreviation", ""),
                "color": "#" + (t.get("color") or "131210"), "alt": "#" + (t.get("alternateColor") or "6E6557")}
        r = s.get(f"https://a.espncdn.com/i/teamlogos/ncaa/500/{tid}.png", timeout=30)
        if r.status_code != 200 or r.content[:8] != b"\x89PNG\r\n\x1a\n":
            raise ThumbError(f"couldn't fetch the logo for team {tid}")
        with open(logo_p, "wb") as f:
            f.write(r.content)
        with open(meta_p, "w") as f:
            json.dump(meta, f, indent=1)
    meta = json.load(open(meta_p))
    meta["logo"] = logo_p
    return meta


# ---------------------------------------------------------------- layouts (HTML at 1200x675)
def esc(s):
    return html.escape(str(s), quote=True)


def logo(tm, size, extra=""):
    return f'<img class="lg" src="/team/{tm["id"]}.png" style="width:{size}px;height:{size}px{extra}" alt="">'


def fmt_val(v):
    v = float(v)
    s = f"{abs(v):.1f}"
    return ("+" if v > 0 else "−" if v < 0 else "") + s


def stripe(colors):
    return '<div class="stripe">' + "".join(f'<i style="background:{c}"></i>' for c in colors) + "</div>"


def lay_stat(sp, ids):
    tms = [team(x, ids) for x in sp["teams"]]
    me, opp = tms[0], (tms[1] if len(tms) > 1 else None)
    return f"""
<div class="stat">
  <div class="own">{logo(me, 300)}</div>
  <div class="num"><b>{esc(sp["stat"])}</b><span>{esc(sp["label"])}</span></div>
  {f'<div class="opp"><em>vs</em>{logo(opp, 190)}</div>' if opp else ''}
</div>{stripe([me["color"]] + ([opp["color"]] if opp else []))}"""


def lay_score(sp, ids):
    a, b = (team(x, ids) for x in sp["teams"])
    sa, sb = sp["score"]
    row = sp.get("row")
    win = 0 if sa > sb else 1 if sb > sa else -1
    def side(tm, sc, i):
        return f'<div class="side s{i}">{logo(tm, 230)}<b class="{"w" if win == i else "l" if win >= 0 else ""}">{esc(sc)}</b></div>'
    r = ""
    if row:
        va, vb = row["values"]
        # the row highlights whichever side "lost" it relative to the scoreboard, which is the point of showing it
        r = (f'<div class="row"><b class="{"hi" if win == 0 and va < vb else ""}">{esc(va)}</b>'
             f'<span>{esc(row["label"])}</span><b class="{"hi" if win == 1 and vb < va else ""}">{esc(vb)}</b></div>')
    return f"""
<div class="score">
  <div class="fin">Final</div>
  <div class="sides">{side(a, sa, 0)}<i class="dash"></i>{side(b, sb, 1)}</div>
  {r}
</div>{stripe([a["color"], b["color"]])}"""


def lay_games(sp, ids):
    me = team(sp["team"], ids)
    gs = [(team(g["opp"], ids), float(g["value"])) for g in sp["games"]]
    if not 2 <= len(gs) <= 4:
        raise ThumbError("games layout takes 2 to 4 games")
    top, bot, val_h, lg = 150, 632, 88, 88          # chart area, value label height, opponent logo size
    up = max([v for _, v in gs if v > 0] or [0])
    dn = max([-v for _, v in gs if v < 0] or [0])
    room = bot - top - 2 * val_h - 12
    sc = room / ((up + dn) or 1)
    above = max(up * sc + val_h, lg + 16) if up else lg + 16
    below = max(dn * sc + val_h, lg + 16) if dn else lg + 16
    zero = top + above + (bot - top - above - below) / 2
    n = len(gs)
    x0, x1 = 440, 1160
    colw = (x1 - x0) / n
    bars = []
    for i, (o, v) in enumerate(gs):
        cx = x0 + colw * i + colw / 2
        h = abs(v) * sc
        pos = v >= 0
        cls = "p" if pos else "n"
        y = zero - h if pos else zero
        vy = (y - val_h) if pos else (zero + h)
        ly = (zero + 14) if pos else (zero - 14 - lg)
        bars.append(f'<i class="bar {cls}" style="left:{cx - 75:.0f}px;top:{y:.0f}px;height:{max(h, 4):.0f}px"></i>'
                    f'<b class="val {cls}" style="left:{cx - colw / 2:.0f}px;width:{colw:.0f}px;top:{vy:.0f}px">{fmt_val(v)}</b>'
                    f'<img class="lg" src="/team/{o["id"]}.png" alt="" style="left:{cx - lg / 2:.0f}px;top:{ly:.0f}px;width:{lg}px;height:{lg}px;position:absolute">')
    return f"""
<div class="games">
  <div class="own">{logo(me, 300)}</div>
  <div class="lab" style="left:{x0}px;width:{x1 - x0}px">{esc(sp["label"])}</div>
  <i class="zero" style="left:{x0}px;width:{x1 - x0}px;top:{zero:.0f}px"></i>
  {"".join(bars)}
</div>{stripe([me["color"], me["alt"]])}"""


CSS = """
*{box-sizing:border-box}html,body{margin:0}
body{width:1200px;height:675px;overflow:hidden;position:relative;background:#F4EAD2;color:#131210;font-family:"Barlow Condensed",sans-serif}
.lg{display:block;object-fit:contain}
.stripe{position:absolute;left:0;right:0;bottom:0;height:16px;display:flex}.stripe i{flex:1}
/* stat */
.stat{position:absolute;inset:0 0 16px;display:flex;align-items:center;justify-content:center;gap:28px;padding:0 60px}
.stat .num{display:flex;flex-direction:column;align-items:center;margin:0 10px}
.stat .num b{font-family:"Big Shoulders Display";font-weight:900;font-size:470px;line-height:.78;color:#E5463A;letter-spacing:-.02em}
.stat .num span{font-weight:800;font-size:58px;letter-spacing:.2em;text-transform:uppercase;margin-top:26px;padding-left:.2em}
.stat .opp{display:flex;flex-direction:column;align-items:center;gap:10px;padding-left:40px;border-left:4px solid #131210;align-self:stretch;justify-content:center;margin:110px 0}
.stat .opp em{font-style:normal;font-weight:800;font-size:40px;letter-spacing:.16em;text-transform:uppercase;color:#6E6557}
/* score */
.score{position:absolute;inset:0 0 16px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:22px}
.score .fin{font-weight:800;font-size:40px;letter-spacing:.22em;text-transform:uppercase;background:#131210;color:#F4EAD2;padding:6px 18px 4px 22px}
.score .sides{display:flex;align-items:center;gap:30px}
.score .side{display:flex;align-items:center;gap:28px}.score .s1{flex-direction:row-reverse}
.score .side b{font-family:"Big Shoulders Display";font-weight:900;font-size:230px;line-height:.8;min-width:250px;text-align:center}
.score .side b.l{color:#8f8676}
.score .dash{display:block;width:44px;height:12px;background:#131210}
.score .row{display:grid;grid-template-columns:1fr auto 1fr;align-items:center;gap:30px;width:760px;border-top:4px solid #131210;padding-top:18px}
.score .row b{font-family:"Big Shoulders Display";font-weight:900;font-size:92px;line-height:.85;text-align:center}
.score .row b.hi{color:#E5463A}
.score .row span{font-weight:800;font-size:44px;letter-spacing:.2em;text-transform:uppercase;color:#6E6557}
/* games */
.games{position:absolute;inset:0 0 16px}
.games .own{position:absolute;left:30px;top:0;bottom:0;width:370px;display:flex;align-items:center;justify-content:center;border-right:4px solid #131210;margin:70px 0}
.games .lab{position:absolute;top:58px;text-align:center;font-weight:800;font-size:46px;letter-spacing:.16em;text-transform:uppercase;color:#3B362E}
.games .zero{position:absolute;height:5px;margin-top:-2px;background:#131210}
.games .bar{position:absolute;width:150px}
.games .bar.p{background:#1E7A50}.games .bar.n{background:#D13A2F}
.games .val{position:absolute;height:88px;display:flex;align-items:center;justify-content:center;font-family:"Big Shoulders Display";font-weight:900;font-size:80px;line-height:1}
.games .val.p{color:#1E7A50}.games .val.n{color:#D13A2F}
"""


def page_html(sp, ids):
    lay = sp.get("layout")
    if lay not in LAYOUTS:
        raise ThumbError(f"thumb layout must be one of {', '.join(LAYOUTS)}")
    body = {"stat": lay_stat, "score": lay_score, "games": lay_games}[lay](sp, ids)
    return (f'<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="{FONTS}">'
            f"<style>{CSS}</style></head><body>{body}</body></html>")


def check_spec(sp):
    if not isinstance(sp, dict):
        return ["story.md needs a thumb: block (see _editorial/thumbs.py)"]
    errs = []
    lay = sp.get("layout")
    if lay not in LAYOUTS:
        errs.append(f"thumb layout must be one of {', '.join(LAYOUTS)}")
    if len(str(sp.get("alt", ""))) < 20:
        errs.append("thumb needs alt text (what the picture shows, 20+ characters)")
    need = {"stat": ("teams", "stat", "label"), "score": ("teams", "score"), "games": ("team", "label", "games")}.get(lay, ())
    errs += [f"thumb ({lay}) needs {k}" for k in need if sp.get(k) in (None, "", [])]
    if lay == "stat" and len(str(sp.get("stat", ""))) > 4:
        errs.append("thumb stat is one short number (4 characters max)")
    if lay == "score" and (len(sp.get("teams") or []) != 2 or len(sp.get("score") or []) != 2):
        errs.append("thumb score needs two teams and two scores")
    for k in ("label",):
        if sp.get(k) and len(str(sp[k])) > 24:
            errs.append(f"thumb {k} over 24 characters (keep it to a word or two; it has to read on a phone)")
    return errs


def render(story_dir, check_only=False):
    fm, _ = B.parse_story(os.path.join(story_dir, "story.md"))
    sp = fm.get("thumb")
    errs = check_spec(sp)
    if errs:
        raise ThumbError("; ".join(errs))
    out = os.path.join(story_dir, "thumb.png")
    want = spec_hash(sp)
    if check_only:
        have = png_text(out, "dawg-thumb")
        print("thumb.png " + ("matches story.md" if have == want else "is missing or out of date: run thumbs.py " + story_dir))
        return have == want
    ids = B.team_ids(REPO)
    page = page_html(sp, ids)
    from playwright.sync_api import sync_playwright
    S = _session()
    def route(r):
        u = r.request.url
        if u == "https://thumb.local/":
            return r.fulfill(status=200, body=page.encode(), headers={"content-type": "text/html"})
        m = re.match(r"https://thumb\.local/team/(\d+)\.png$", u)
        if m:
            return r.fulfill(status=200, body=open(os.path.join(CACHE, m.group(1) + ".png"), "rb").read(), headers={"content-type": "image/png"})
        if "fonts.googleapis.com" in u or "fonts.gstatic.com" in u:
            x = S.get(u, headers={"User-Agent": r.request.headers.get("user-agent", "")}, timeout=30)
            return r.fulfill(status=x.status_code, body=x.content, headers={"content-type": x.headers.get("content-type", "")})
        return r.fulfill(status=404, body=b"")
    with sync_playwright() as p:
        b = p.chromium.launch()
        c = b.new_context(viewport={"width": W, "height": H}, device_scale_factor=1)
        c.route("**/*", route)
        pg = c.new_page()
        pg.goto("https://thumb.local/")
        pg.evaluate("document.fonts.ready")
        pg.wait_for_timeout(300)
        if not pg.evaluate("document.fonts.check('900 40px \"Big Shoulders Display\"') && document.fonts.check('800 40px \"Barlow Condensed\"')"):
            raise ThumbError("brand fonts didn't load")
        if pg.evaluate("[...document.images].some(i => !i.complete || !i.naturalWidth)"):
            raise ThumbError("a team logo didn't load")
        over = pg.evaluate("[...document.querySelectorAll('body *')].some(e => {const r = e.getBoundingClientRect(); return r.width && (r.left < -1 || r.right > 1201 || r.top < -1 || r.bottom > 676)})")
        if over:
            raise ThumbError("something in the thumbnail runs off the edge; shorten the label or number")
        png = pg.screenshot(clip={"x": 0, "y": 0, "width": W, "height": H})
        b.close()
    with open(out, "wb") as f:
        f.write(add_png_text(png, "dawg-thumb", want))
    print(f"wrote {out} ({W}x{H}, {sp['layout']})")
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("story_dir")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    try:
        ok = render(os.path.abspath(a.story_dir), a.check)
    except (ThumbError, B.BuildError) as e:
        print("thumbs: " + str(e), file=sys.stderr)
        sys.exit(1)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
