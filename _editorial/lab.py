#!/usr/bin/env python3
"""DAWG Lab build. Turns approved Lab cases into the public /lab/ pages. Same rules as the Stories build.

Kept apart from the V3 grading pipeline: it reads only _editorial/ and the site's own team list (sitemap.xml, data/team,
team pages), and writes only under lab/. It never deletes anything.

  python3 _editorial/lab.py check                 validate approved cases in _editorial/lab/; writes nothing
  python3 _editorial/lab.py build                 render every approved case into lab/ (writes nothing while no case is approved)
  python3 _editorial/lab.py preview DRAFT_DIR     render one draft privately (outside the repo), marked noindex, with screenshots
  python3 _editorial/lab.py approve DRAFT_DIR --by "Matthew McBrayer"
                                                  move a draft into _editorial/lab/ as published (only after Matthew's explicit OK)
  python3 _editorial/lab.py reapprove NNN-slug --by "Matthew McBrayer"
                                                  re-approve an approved case after an edit (build refuses edited cases until then)
  python3 _editorial/lab.py sample OUT_DIR        write a clearly marked SAMPLE case draft for building and previewing the pages

A case folder is named NNN-slug and holds case.json (metadata, verdict, plan and data references, versions, corrections),
case.md (the reading column), data.json (team-level summaries only) and plan.md (the approved research plan, published).

Rules this script enforces, on top of the Stories rules:
  1. No empty Lab: with no approved case, build writes nothing.
  2. Canonical URLs never change: a published case number keeps its slug; a case whose source goes missing stays live.
  3. Team copy is descriptive: team text can't call a habit or trait confirmed unless the case carries a team finding
     with its receipts (confirmation data, correction for everything tried, the plan reference).
  4. Research-only values are labeled: research seasons need a research dataset entry; pages and cards print the label.
  5. Sample data never publishes: approve and build refuse a case marked sample, and published copy can't hold
     [placeholders] or "sample"/"illustrative" text.
"""
import argparse, copy, datetime as dt, glob, hashlib, html, json, math, os, random, re, shutil, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True
import build as B   # noqa: E402  (shared helpers: escaping, team lists, write_if_changed, markdown)

SITE = B.SITE
DRAFTS = "/home/claude/lab-drafts"
PREVIEWS = "/home/claude/lab-preview"
CASE_DIR = re.compile(r"^(\d{3})-([a-z0-9]+(?:-[a-z0-9]+)*)$")
VERDICTS = {"holds-up": ("Holds up", "holds"), "doesnt-hold-up": ("Doesn’t hold up", "not"),
            "mixed": ("Mixed evidence", "mixed"), "inconclusive": ("Inconclusive", "inc")}
ICONS = {"holds": '<path d="M4 12.5l5 5L20 6.5"/>', "not": '<path d="M6 6l12 12M18 6L6 18"/>',
         "mixed": '<circle cx="12" cy="12" r="8"/><path d="M12 4a8 8 0 0 1 0 16z" fill="currentColor" stroke="none"/>',
         "inc": '<path d="M9 9a3 3 0 1 1 4.5 2.6c-1 .6-1.5 1.2-1.5 2.4"/><path d="M12 18h.01"/>'}
# words that would turn a team description into a claim about a lasting trait (allowed only with a team finding)
TRAIT = re.compile(r"\b(plays? down|played down|always|never|habits?|tends? to|consistently|persistent(ly)?|traits?|known for|reliably)\b", re.I)
PLACEHOLDER = re.compile(r"(?<!\[)\[(?!\[)[^\]\n]+\](?!\()")       # [like this], but not [[markers]] or [links](...)
SAMPLE_WORDS = re.compile(r"\b(sample|illustrative|placeholder|lorem)\b", re.I)


class LabError(B.BuildError):
    pass


def t(s): return B.t(s)
def a(s): return B.a(s)
def fmt(v): return ("+" if v > 0 else "−" if v < 0 else "") + f"{abs(v):.1f}"
def read(p, mode="r"): return B.read(p, mode)
def jdump(o): return json.dumps(o, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


# ---------------------------------------------------------------- loading and validation
def load_case(d):
    m = CASE_DIR.match(os.path.basename(d.rstrip("/")))
    if not m:
        raise LabError(f"{d}: folder must be named NNN-slug (e.g. 001-playing-down)")
    need = ["case.json", "case.md", "data.json", "plan.md"]
    miss = [f for f in need if not os.path.isfile(os.path.join(d, f))]
    if miss:
        raise LabError(f"{os.path.basename(d)}: missing " + ", ".join(miss))
    try:
        case = json.loads(read(os.path.join(d, "case.json")))
        data = json.loads(read(os.path.join(d, "data.json")))
    except json.JSONDecodeError as e:
        raise LabError(f"{os.path.basename(d)}: invalid JSON: {e}")
    return case, read(os.path.join(d, "case.md")), data, read(os.path.join(d, "plan.md"))


def strings(o):
    if isinstance(o, str):
        yield o
    elif isinstance(o, dict):
        for v in o.values():
            yield from strings(v)
    elif isinstance(o, list):
        for v in o:
            yield from strings(v)


def validate(case, md, data, plan, d, site_teams, mode):
    errs = []
    name = os.path.basename(d.rstrip("/"))
    m = CASE_DIR.match(name)
    req = ["number", "slug", "type", "status", "title", "topic", "dek", "description", "version", "plan", "data_lock",
           "methods", "versions", "corrections", "presentation", "research_datasets"]
    for k in req:
        if k not in case or case[k] in (None, ""):
            errs.append(f"missing {k}")
    if errs:
        return errs
    if m and (case["number"], case["slug"]) != (m.group(1), m.group(2)):
        errs.append(f"folder name must be {case['number']}-{case['slug']}")
    if case["type"] == "original-investigation":
        errs.append("Original Investigation pages aren't built in v0 (the fallback template comes only if LAB 001 is delayed)")
    elif case["type"] != "hypothesis-test":
        errs.append("type must be hypothesis-test")
    v = case.get("verdict") or {}
    if case["type"] == "hypothesis-test":
        if v.get("kind") not in VERDICTS:
            errs.append("verdict.kind must be one of " + ", ".join(VERDICTS))
        if not v.get("subtitle") or len(v["subtitle"]) > 32:
            errs.append("verdict.subtitle (written in the research plan) is required, 32 characters max")
        if not v.get("answer"):
            errs.append("verdict.answer (the 10-second answer) is required")
    p = case["plan"]
    for k in ("version", "locked"):
        if not p.get(k):
            errs.append(f"plan.{k} is required (every case keeps its research-plan reference)")
    if not plan.strip():
        errs.append("plan.md is empty: the approved research plan is published with the case")
    dl = case["data_lock"]
    for k in ("snapshot", "cutoff", "label"):
        if not dl.get(k):
            errs.append(f"data_lock.{k} is required")
    for k in ("dawg", "case"):
        if not case["methods"].get(k):
            errs.append(f"methods.{k} is required")
    if not case["versions"] or case["versions"][-1].get("version") != case["version"]:
        errs.append("versions must end with an entry for the current version")
    for vv in case["versions"]:
        for k in ("version", "date", "change"):
            if not vv.get(k):
                errs.append(f"every version entry needs {k}")
    for c in case["corrections"]:
        if not (c.get("date") and c.get("text")):
            errs.append("every correction needs a date and text")
    pres = case["presentation"]
    for k in ("measure_short", "short_measure", "team_question", "team_min", "team_min_text", "x_label", "y_label"):
        if not pres.get(k):
            errs.append(f"presentation.{k} is required")
    hd = pres.get("team_headlines")
    if not isinstance(hd, dict) or any(not (hd.get(k) or "").strip() for k in HEADLINE_STATES):
        errs.append("presentation.team_headlines needs a headline for each team state (" + ", ".join(HEADLINE_STATES) +
                    "), written for this investigation and approved with the research")
    else:
        longest = max(site_teams, key=len).replace("-", " ").title()   # the longest program name the headline must fit
        for k in HEADLINE_STATES:
            n = len(hd[k].replace("{team}", longest))
            if n > HEADLINE_MAX:
                errs.append(f"team headline '{k}' runs {n} characters with the longest team name; share cards fit {HEADLINE_MAX}")
            m = TRAIT.search(hd[k])
            if m:
                errs.append(f"team headline '{k}' says '{m.group(0)}', which reads as a confirmed trait")
    try:
        cv = float(pres.get("band_coverage"))
        if not 50 <= cv < 100:
            raise ValueError
    except (TypeError, ValueError):
        errs.append("presentation.band_coverage (how often luck alone lands inside the luck range, from the research plan) must be a number from 50 to 99.9")
    if len(case["description"]) > 200:
        errs.append("description over 200 characters")
    # data
    teams = data.get("teams") or {}
    for slug, tm in teams.items():
        if slug not in site_teams:
            errs.append(f"data.json: unknown team slug '{slug}'")
        for k in ("hf_games", "seasons", "raw", "groups", "season_rows"):
            if k not in tm:
                errs.append(f"data.json {slug}: missing {k}")
        for g in tm.get("groups", []):
            if "n" not in g:
                errs.append(f"data.json {slug}: every group row needs its sample size (n)")
        for r in tm.get("season_rows", []):
            if "n" not in r:
                errs.append(f"data.json {slug}: every season row needs its sample size (n)")
        if tm.get("season_rows") and all("n" in r for r in tm["season_rows"]) and sum(int(r["n"]) for r in tm["season_rows"]) != tm.get("hf_games"):
            errs.append(f"data.json {slug}: season rows add up to {sum(int(r['n']) for r in tm['season_rows'])} games, not hf_games {tm.get('hf_games')}")
        if len({r.get("season") for r in tm.get("season_rows", [])}) != tm.get("seasons", -1) and tm.get("season_rows"):
            errs.append(f"data.json {slug}: {len(tm['season_rows'])} season rows but seasons is {tm.get('seasons')}")
        f = tm.get("finding")
        if f:
            for k in ("text", "confirmation", "correction", "plan_ref"):
                if not f.get(k):
                    errs.append(f"data.json {slug}: a team finding needs {k} (otherwise team results stay descriptive)")
    research_seasons = {r["season"] for tm in teams.values() for r in tm.get("season_rows", []) if r.get("research")}
    if (research_seasons or (data.get("carryover") or {}).get("includes_research")) and not case["research_datasets"]:
        errs.append("research-only seasons appear in the data, but case.json lists no research dataset with its provenance")
    for rd in case["research_datasets"]:
        for k in ("name", "span", "provenance", "label", "label_short"):
            if not rd.get(k):
                errs.append(f"research dataset needs {k}")
    for rd_ in case["research_datasets"]:
        if rd_.get("span") and not re.match(r"^\d{4}\s*[–-]\s*\d{4}$", rd_["span"]):
            errs.append("research dataset span must look like 2014–2018")
    if research_seasons and case["research_datasets"]:
        m_ = re.match(r"^(\d{4})\s*[–-]\s*(\d{4})$", case["research_datasets"][0].get("span") or "")
        if m_ and not all(int(m_.group(1)) <= y <= int(m_.group(2)) for y in research_seasons):
            errs.append("a season marked research falls outside the research dataset's span")
        if m_:
            lo, hi = int(m_.group(1)), int(m_.group(2))
            for slug_, tm_ in teams.items():
                for r_ in tm_.get("season_rows", []):
                    if lo <= int(r_.get("season", 0)) <= hi and not r_.get("research"):
                        errs.append(f"data.json {slug_}: season {r_['season']} is inside the research span but isn't marked research")
    if not data.get("cuts") or sum(1 for c in data["cuts"] if c.get("plan")) != 1:
        errs.append("data.json: cuts must include exactly one marked as the plan's choice")
    if "carryover" not in data or "threshold" not in data or "league" not in data:
        errs.append("data.json needs carryover, threshold and league")
    shown = copy.deepcopy(case)
    shown["plan"].pop("version", None)
    if TWO_POINT_OH.search(" ".join(strings(shown)) + md + plan):
        errs.append("'2.0' appears in the copy (internal name; never public)")
    if TWO_POINT_OH.search(str(p.get("version", ""))) and not p.get("label"):
        errs.append("plan.version contains '2.0', which never appears publicly; set plan.label (how the page names the plan version)")
    if mode == "publish":
        if case.get("sample"):
            errs.append("this case is marked sample: sample data never publishes")
        if case["status"] != "published":
            errs.append("status is not 'published'")
        for k in ("approved_by", "approved_at", "published"):
            if not case.get(k):
                errs.append(f"missing {k}: a case is published only with Matthew's explicit approval on record")
        copytext = " ".join(strings(case)) + " " + md + " " + " ".join(strings({k: v for k, v in data.items() if k != "teams"}))
        if PLACEHOLDER.search(copytext):
            errs.append("unfilled [placeholder] in the copy: " + PLACEHOLDER.search(copytext).group(0))
        if SAMPLE_WORDS.search(copytext):
            errs.append("sample/illustrative wording in published copy: " + SAMPLE_WORDS.search(copytext).group(0))
    return errs


TWO_POINT_OH = B.TWO_POINT_OH


# ---------------------------------------------------------------- team states and copy (descriptive by default)
def short_span(span):
    """2014–2018 -> 2014–18"""
    m = re.match(r"^(\d{4})\s*[–-]\s*(\d{4})$", span or "")
    return f"{m.group(1)}–{m.group(2)[2:]}" if m and m.group(1)[:2] == m.group(2)[:2] else (span or "")


HEADLINE_STATES = ("within", "outside", "below", "none")
HEADLINE_MAX = 40


def headline(heads, state, name):
    return heads[state].replace("{team}", name)


def derive_teams(case, data, ids, names, site_teams):
    """Team copy for the strip, side card, pin, panel, cards and link previews. Descriptive only: it says what happened
    and how it compares with luck, never that a program has a lasting habit. The luck range's coverage comes from the
    research plan (presentation.band_coverage); the copy only restates it."""
    pres = case["presentation"]
    mn = pres["team_min"]
    num = case["number"]
    cov = float(pres["band_coverage"])
    cov_s = f"{cov:g}"
    expect = round(68 * (100 - cov) / 100)
    rd = case["research_datasets"][0] if case["research_datasets"] else None
    heads = pres["team_headlines"]   # written for this investigation and approved with the research
    out = {}
    for slug in sorted(site_teams, key=lambda s: names.get(s, s)):
        src = (data.get("teams") or {}).get(slug)
        name = names.get(slug, slug)
        row = {"name": name, "id": ids.get(slug), "slug": slug, "share": f"{SITE}/lab/{num}/{slug}/", "short_url": f"dawgindex.com/lab/{num}/{slug}",
               "card_png": f"/lab/{num}-{case['slug']}/cards/{slug}.png", "n_label": f"games {pres['measure_short']}",
               "research_games": 0, "research_text": "", "research_short": "", "card_research": ""}
        if not src or not src.get("hf_games") or not src.get("seasons"):
            row.update(state="none", hf_games=0, seasons=0, raw=0, groups=[], season_rows=[], has_research=False, card=False,
                       sentence=f"{name} has no games that qualify for this investigation.",
                       band_text="", answer=headline(heads, "none", name), pin=headline(heads, "none", name),
                       short=f"{name}: {headline(heads, 'none', name)}",
                       none_text=((src or {}).get("none_reason") or f"{name} has no qualifying games in the seasons this investigation covers, so there’s nothing to read for it here.") + " The full sample is on the case page.")
            out[slug] = row
            continue
        hf, ns, raw = int(src["hf_games"]), int(src["seasons"]), float(src["raw"])
        ok = hf >= mn["hf_games"] and ns >= mn["seasons"]
        rg = sum(int(r["n"]) for r in src["season_rows"] if r.get("research"))
        row.update(hf_games=hf, seasons=ns, raw=raw, groups=src["groups"], season_rows=src["season_rows"], has_research=rg > 0, research_games=rg)
        if rg and rd:
            row["research_text"] = (f"{rg} of these {hf} games are from {rd['span']} and use research grades: computed with the DAWG formula, "
                                    "not official DAWG grades.")
            row["research_short"] = f"incl. {short_span(rd['span'])} research grades"
            row["card_research"] = f"{rg} of {hf} games use {short_span(rd['span'])} research grades, not official DAWG grades."
        if src.get("finding"):
            f = src["finding"]
            row["finding"] = {"text": f["text"], "receipts": f"{f['confirmation']} · {f['correction']} · {f['plan_ref']}"}
        diff = "the same" if raw == 0 else f"{abs(raw):.1f} points {'worse' if raw < 0 else 'better'}"
        row["sentence"] = f"{name} graded {diff} {pres['measure_short']} than in its other games, over {hf} games in {ns} seasons."
        if ok:
            band, adj = float(src["band"]), float(src["adjusted"])
            inside = abs(raw) < band
            if inside:
                bt = (f"That’s within the luck range: luck alone lands a program inside it {cov_s} times in 100 over {hf} games. "
                      f"A gap this size can’t be told apart from luck.")
            else:
                bt = (f"That’s outside the luck range: luck alone lands a program inside it {cov_s} times in 100 over {hf} games. "
                      f"Luck alone would still put about {expect} of 68 programs out here, so this describes these games, not what comes next.")
            row.update(state="ok", band=band, adjusted=adj, card=True, band_text=bt, coverage=cov_s,
                       answer=headline(heads, "within" if inside else "outside", name),
                       pin=f"{headline(heads, 'within' if inside else 'outside', name)} · {hf} games",
                       short=f"{name}: {headline(heads, 'within' if inside else 'outside', name)} · {hf} games")
        else:
            row.update(state="below", card=False, coverage=cov_s,
                       band_text=f"Too few games to compare with luck: {hf} games in {ns} seasons. A comparison needs {pres['team_min_text']}.",
                       answer=headline(heads, "below", name), pin=f"{headline(heads, 'below', name)} · {hf} games",
                       short=f"{name}: {headline(heads, 'below', name)} · {hf} games")
            row["below_text"] = row["band_text"]
        out[slug] = row
    return out


def team_copy_errors(teams):
    errs = []
    for slug, tm in teams.items():
        if tm.get("finding"):
            continue
        for k in ("sentence", "band_text", "answer", "pin", "short", "none_text", "below_text", "research_text", "research_short", "card_research"):
            m = TRAIT.search(tm.get(k) or "")
            if m:
                errs.append(f"{slug}: team text '{k}' says '{m.group(0)}', which reads as a confirmed trait; team results are descriptive unless the research supports a team finding")
    return errs


# ---------------------------------------------------------------- page pieces
def page(tpl, rep):
    s = read(os.path.join(tpl, "lab", "base.html"))
    for k, v in rep.items():
        s = s.replace("{{" + k + "}}", v)
    left = re.search(r"\{\{[A-Z_]+\}\}", s)
    if left:
        raise LabError("template placeholder left unfilled: " + left.group(0))
    return s


def head_rep(tpl, title, desc, canonical, og_url, og_title, og_desc, og_image, og_alt, og_type="article", preview=False, jsonld=None):
    return {"TITLE": a(title), "DESCRIPTION": a(desc), "CANONICAL": canonical, "OG_TYPE": og_type, "OG_URL": og_url, "OG_TITLE": a(og_title),
            "OG_DESCRIPTION": a(og_desc), "OG_IMAGE": og_image, "OG_ALT": a(og_alt),
            "ROBOTS": '\n<meta name="robots" content="noindex, nofollow">' if preview else "",
            "JSONLD": ('<script type="application/ld+json">' + jdump(jsonld) + "</script>") if jsonld else "",
            "CSS": read(os.path.join(tpl, "story.css")).rstrip("\n")}


def banners(case, preview):
    if preview == "production":   # private preview made to look like the live site: no banners, still noindex
        return ""
    b = []
    if preview:
        b.append('<div class="lb-preview">Preview · not published · only Matthew can approve</div>')
    if case and case.get("sample"):
        b.append('<div class="lb-sample">Sample data · not research results · for building and reviewing the pages only</div>')
    return "\n".join(b) + ("\n" if b else "")


def stamp(v):
    word, cls = VERDICTS[v["kind"]]
    return (f'<div class="lb-stamp lb-v-{cls}"><div class="lb-stamp-in"><div class="lb-stamp-row">'
            f'<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" aria-hidden="true">{ICONS[cls]}</svg>'
            f'<span class="lb-stamp-word">{t(word)}</span></div><span class="lb-stamp-sub">{t(v["subtitle"])}</span></div></div>')


def team_options(teams, first_label=None):
    o = [f'<option value="">{t(first_label)}</option>'] if first_label else []
    o += [f'<option value="{s}">{t(tm["name"])}</option>' for s, tm in teams.items()]
    return "".join(o)


def research_note(label):
    return f'<div class="lb-research-note"><i aria-hidden="true"></i>{t(label)}</div>'


def exhibit_html(kind, case, data, letter):
    rd = case["research_datasets"][0] if case["research_datasets"] else None
    if kind == "carryover":
        co = data["carryover"]
        h = (f'<div class="lb-exhibit" role="group" aria-label="Exhibit {letter}: does it carry over?" id="lb-carry-sec">'
             f'<div class="lb-ex-head"><span>Exhibit {letter} · Does it carry over?</span>' + ('<span class="lb-tagS">Sample data</span>' if case.get("sample") else "") + "</div>"
             '<div id="lb-carry" style="padding:6px 8px 0"></div>'
             f'<div class="lb-ex-foot">Each dot is one program: its gap in {t(co["x_label_long"])} across, against {t(co["y_label_long"])} up. Your team is red.</div>')
        if co.get("includes_research") and rd:
            h += research_note(rd["label"])
        return h + "</div>"
    if kind == "bound":
        return (f'<div class="lb-exhibit" role="group" aria-label="Exhibit {letter}: what the data rules out">'
                f'<div class="lb-ex-head"><span>Exhibit {letter} · What the data rules out</span>' + ('<span class="lb-tagS">Sample data</span>' if case.get("sample") else "") + "</div>"
                '<div id="lb-bound" style="padding:4px 8px 0"></div>'
                f'<div class="lb-ex-foot">The hatched part is ruled out. The red line is the size that matters, set in the research plan before the analysis.</div></div>')
    if kind == "cuts":
        btn = "".join(f'<button type="button" data-cut="{a(c["id"])}" aria-pressed="{"true" if c.get("plan") else "false"}">{t(c["label"])}</button>' for c in data["cuts"])
        plan_cut = [c for c in data["cuts"] if c.get("plan")][0]
        return (f'<div class="lb-cuts" role="group" aria-label="Other ways to cut it">{btn}</div>'
                f'<p class="lb-cut-note" id="lb-cut-note">{t(plan_cut["note"])}</p>')
    raise LabError(f"unknown exhibit [[{kind}]]")


def body_html(case, md, data):
    letters = iter("BCDEFGH")
    def part(m):
        return f'<p class="lb-part">{t(m.group(1).strip())}</p>'
    src = re.sub(r"^::: *part\n(.*?)\n:::$", lambda m: "LBPART" + B.t(m.group(1).strip()).replace(" ", " ") + "LBEND", md, flags=re.S | re.M)
    out = B.render_body({"format": "markdown"}, src)
    out = re.sub(r"<p>LBPART(.*?)LBEND</p>", lambda m: f'<p class="lb-part">{m.group(1).replace(chr(160), " ")}</p>', out)
    out = re.sub(r"<p>\[\[([a-z-]+)\]\]</p>", lambda m: exhibit_html(m.group(1), case, data, next(letters) if m.group(1) in ("carryover", "bound") else ""), out)
    if "[[" in out:
        raise LabError("unknown [[marker]] in case.md")
    return out


def receipts_html(case):
    p, dl, me = case["plan"], case["data_lock"], case["methods"]
    plan_url = f"/lab/{case['number']}-{case['slug']}/plan/"
    rows = [("Plan locked", f'{t(B.nice_date(p["locked"]))} · plan {t(plan_label(case))} · <a href="{plan_url}">read the plan, including what was explored first</a>'),
            ("Data", f'{t(dl["label"])} · snapshot <span class="lb-mono" style="font-size:13px">{t(dl["snapshot"][:19])}</span>'),
            ("Method", f'DAWG {t(me["dawg"])} · case method v{t(me["case"])}'),
            ("Second check", t(case.get("second_check") or "Reproduced independently before publishing"))]
    for rd in case["research_datasets"]:
        rows.append(("Research-only data", f'<b>{t(rd["name"])}</b>: {t(rd["provenance"])} <span class="lb-note" style="display:block;margin:2px 0 0">{t(rd["label"])}</span>'))
    dl_html = "".join(f"<dt>{t(k)}</dt><dd>{v}</dd>" for k, v in rows)
    vers = "".join(f'<li>v{t(v["version"])} · {t(B.nice_date(v["date"]))} · {t(v["change"])}' + (f' · verdict: {t(VERDICTS[v["verdict"]][0])}' if v.get("verdict") in VERDICTS else "") + "</li>" for v in reversed(case["versions"]))
    corr = "".join(f'<div class="lb-corr"><b>Correction, {t(B.nice_date(c["date"]))}:</b> {t(c["text"])}</div>' for c in case["corrections"])
    return ('<h2 id="lb-receipts">Receipts</h2>' + (corr or "") + f'<dl class="lb-receipts">{dl_html}</dl>'
            '<h2 style="font-size:28px">Version history</h2>' + f'<ul class="lb-versions">{vers}</ul>'
            + ('<p class="lb-note">No corrections. Any correction is dated here and on <a href="/lab/corrections/">the corrections page</a>.</p>' if not corr else ""))


def js_data(case, data, teams):
    pres = case["presentation"]
    rd = case["research_datasets"][0] if case["research_datasets"] else {"label": "", "label_short": ""}
    co = dict(data["carryover"])
    co["x_label"], co["y_label"] = pres["x_label"], pres["y_label"]
    cuts = []
    for c in data["cuts"]:
        c2 = dict(c)
        if c2.get("carryover"):
            c2["carryover"] = dict(c2["carryover"], x_label=pres["x_label"], y_label=pres["y_label"])
        cuts.append(c2)
    return {"case": {"number": case["number"], "url": f"/lab/{case['number']}-{case['slug']}/"}, "threshold": data["threshold"],
            "carryover": co, "cuts": cuts, "league": data["league"], "research": {"label": rd["label"], "label_short": rd["label_short"], "name": rd.get("name", ""), "span": rd.get("span", ""),
                         "provenance": rd.get("provenance", ""), "receipts": "#lb-receipts"},
            "teams": teams}


def plan_label(case):
    p = case["plan"]
    return p.get("label") or f"v{p['version']}"


def case_url(case): return f"{SITE}/lab/{case['number']}-{case['slug']}/"


def case_page(case, md, data, teams, tpl, asset_v, preview=False):
    url = case_url(case)
    num = case["number"]
    v = case.get("verdict")
    cover = (f'<section class="lb-cover" aria-label="Case cover"><div class="lb-cover-in">'
             f'<nav class="lb-crumb" aria-label="Breadcrumb"><a href="/lab/">The Lab</a> / {t(case["topic"])}</nav>'
             f'<div class="lb-meta"><span class="lb-tab">LAB {num}</span><span class="lb-mono">Hypothesis Test · v{t(case["version"])} · {t(case["data_lock"]["label"])}</span></div>'
             f'<h1>{t(case["title"])}</h1><p class="lb-dek">{t(case["dek"])}</p>'
             f'<div class="lb-verdict">{stamp(v)}<div class="lb-answer"><span class="lb-label">The 10-second answer</span><p>{t(v["answer"])}</p></div></div>'
             "</div></section>")
    strip = ('<div id="lb-notice" class="lb-notice" role="status" hidden></div>'
             '<section class="lb-team-strip" id="lb-strip" aria-label="Your team">'
             f'<div class="lb-pick"><label class="lb-label" for="lb-pick">What about my team?</label><select id="lb-pick" class="lb-select">{team_options(teams, "Pick a team")}</select></div>'
             '<div class="lb-res" id="lb-strip-res" aria-live="polite"><b>Pick a team to see what happened for it.</b><span>Every chart on the page will highlight it.</span></div>'
             '<div style="display:flex;gap:10px;flex-wrap:wrap"><button id="lb-open-panel" class="lb-btn lb-solid" type="button" hidden>Full breakdown →</button>'
             '<button id="lb-share" class="lb-btn" type="button" hidden>Share card</button></div></section>')
    lead = exhibit_html("carryover", case, data, "A").replace('id="lb-carry-sec"', 'id="lb-carry-sec" style="margin:0"')
    body = body_html(case, md, data)
    side = ('<div id="lb-side" class="lb-sidecard" hidden><div class="lb-sidecard-h"><span class="lb-mono">YOUR TEAM · LAB ' + num + '</span><b id="lb-side-name"></b></div>'
            '<div class="lb-sidecard-b"><span class="lb-big" id="lb-side-val"></span><span id="lb-side-txt"></span><span id="lb-side-n" class="lb-note" style="margin:0"></span>'
            '<button id="lb-side-open" class="lb-btn lb-solid" type="button">Full breakdown →</button></div></div>'
            '<div class="lb-sec" style="font-size:15px"><span class="lb-label">Related</span><a href="/lab/">All Lab case files</a>'
            f'<a href="/lab/{num}-{case["slug"]}/plan/">The research plan</a><a href="/lab/corrections/">Corrections</a></div>')
    panel = ('<div id="lb-scrim" class="lb-scrim" hidden></div>'
             '<aside id="lb-panel" class="lb-panel" role="dialog" aria-modal="true" aria-labelledby="lb-p-name" hidden>'
             '<div class="lb-panel-h"><div class="lb-panel-top"><button class="lb-back" type="button"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" aria-hidden="true"><path d="M15 5l-7 7 7 7"/></svg>Back to the case</button>'
             f'<span class="lb-mono">LAB {num} · YOUR TEAM</span>'
             '<button class="lb-close" type="button" aria-label="Close"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg></button></div>'
             '<div class="lb-panel-id"><img id="lb-p-logo" alt="" hidden><div><b id="lb-p-name"></b><span id="lb-p-q"></span></div></div>'
             f'<label class="lb-label" for="lb-p-pick">Switch team</label><select id="lb-p-pick" class="lb-select">{team_options(teams)}</select></div>'
             '<div class="lb-panel-b" id="lb-p-body"></div>'
             '<div class="lb-panel-f"><button id="lb-p-share" class="lb-btn lb-solid" type="button">Share card</button><a id="lb-p-team" class="lb-btn" href="/">Team page</a></div></aside>'
             '<button id="lb-pin" class="lb-pin" type="button" hidden aria-label="Open your team’s results"><b id="lb-pin-n"></b><span class="lb-mono" id="lb-pin-v"></span><span class="lb-pin-t" id="lb-pin-t"></span><em>Open</em></button>')
    content = (cover + '<main class="lb-main">' + strip + lead +
               '<div class="lb-cols"><article class="lb-article"><div class="body">' + body + receipts_html(case) + "</div></article>"
               f'<aside class="lb-rail" aria-label="Your team and related">{side}</aside></div></main>' + panel)
    data_js = js_data(case, data, teams)
    ld = {"@context": "https://schema.org", "@type": "Article", "headline": case["title"], "datePublished": case.get("published") or case["versions"][0]["date"],
          "dateModified": case.get("updated") or case["versions"][-1]["date"], "author": {"@type": "Organization", "name": "DAWG Index"},
          "publisher": {"@type": "Organization", "name": "DAWG Index", "url": SITE}, "image": url + "og.png", "mainEntityOfPage": url}
    rep = head_rep(tpl, f"LAB {num}: {case['title']} · DAWG Lab", case["description"], url, url, f"LAB {num}: {case['title']}",
                   case.get("social_description") or case["description"], url + "og.png", f"DAWG Lab case {num}: {case['title']}", preview=preview, jsonld=ld)
    rep.update({"ASSET_V": asset_v, "LAB_CURRENT": ' aria-current="page"', "BODY_ATTR": "", "BANNERS": banners(case, preview), "CONTENT": content,
                "SCRIPTS": f'<script id="lab-data" type="application/json">{jdump(data_js)}</script>\n<script src="/lab/lab.js?v={asset_v}"></script>'})
    return page(tpl, rep)


def plan_page(case, plan, tpl, asset_v, preview=False):
    url = case_url(case) + "plan/"
    num = case["number"]
    p = case["plan"]
    cover = (f'<section class="lb-cover"><div class="lb-cover-in"><nav class="lb-crumb" aria-label="Breadcrumb"><a href="/lab/">The Lab</a> / <a href="/lab/{num}-{case["slug"]}/">LAB {num}</a> / Research plan</nav>'
             f'<div class="lb-meta"><span class="lb-tab">LAB {num} · PLAN</span><span class="lb-mono">Plan {t(plan_label(case))} · locked {t(B.nice_date(p["locked"]))}</span></div>'
             f'<h1 style="font-size:clamp(36px,5vw,60px)">The research plan</h1><p class="lb-dek">Written and locked before the results. Published in full, including what was explored before it was locked.</p></div></section>')
    content = cover + '<main class="lb-main lb-plan"><article class="col"><div class="body">' + B.render_body({"format": "markdown"}, plan) + f'<p><a href="/lab/{num}-{case["slug"]}/">← Back to the case</a></p></div></article></main>'
    rep = head_rep(tpl, f"Research plan · LAB {num} · DAWG Lab", f"The approved research plan for LAB {num}: {case['title']}", url, url,
                   f"Research plan · LAB {num}", f"The approved research plan for LAB {num}, published in full.", case_url(case) + "og.png", f"DAWG Lab case {num}", preview=preview)
    rep.update({"ASSET_V": asset_v, "LAB_CURRENT": ' aria-current="page"', "BODY_ATTR": "", "BANNERS": banners(case, preview), "CONTENT": content, "SCRIPTS": ""})
    return page(tpl, rep)


def landing_page(cases, docket, tpl, asset_v, preview=False):
    """cases: [(case, data, teams)] newest first. Never rendered with zero cases (no empty Lab)."""
    case, data, teams = cases[0]
    num, url = case["number"], f"/lab/{case['number']}-{case['slug']}/"
    v = case["verdict"]
    rnote = research_note(case["research_datasets"][0]["label"]) if (data["carryover"].get("includes_research") and case["research_datasets"]) else ""
    # the team picker is the page's main action: inside the case cover, between the answer and the chart on phones
    team = ('<div class="lb-home-team" role="group" aria-labelledby="lb-home-h">'
            '<div class="lb-ht-q"><span class="lb-label">Start with your team</span><label id="lb-home-h" for="lb-home-pick">What about my team?</label></div>'
            f'<select id="lb-home-pick" class="lb-select lb-select-xl">{team_options(teams, "Pick your team")}</select>'
            '<div class="lb-ht-res" aria-live="polite"><b id="lb-home-ans">All 68 programs are in the case file.</b>'
            '<span id="lb-home-line">Pick one to see what happened for it and how that compares with luck.</span>'
            '<span id="lb-home-rn" class="lb-ht-rn" hidden><i aria-hidden="true"></i><span></span></span></div>'
            f'<a id="lb-home-link" class="lb-btn lb-hot" href="{url}">Open the case file →</a></div>')
    feat = (f'<section aria-label="Latest case file" class="lb-feat"><span class="lb-tab" style="align-self:flex-start">LAB {num} · LATEST CASE</span>'
            '<div class="lb-card-cover"><div class="lb-cc-text">'
            f'<span class="lb-label">{t(case["topic"])} · Hypothesis Test</span><h2>{t(case["title"])}</h2>'
            f'<div style="display:flex;align-items:center;gap:24px;flex-wrap:wrap">{stamp(v)}<p class="lb-cc-ans">{t(v["answer"])}</p></div>'
            f'<a class="lb-open" href="{url}">Read the case file →</a>'
            f'<span class="lb-mono" style="font-size:12px;color:var(--lb-muted-d)">v{t(case["version"])} · {t(case["data_lock"]["label"])}</span></div>'
            + team +
            '<div class="lb-cc-ex"><div class="lb-exhibit"><div class="lb-ex-head"><span>Exhibit A · 68 programs</span>' + ('<span class="lb-tagS">Sample data</span>' if case.get("sample") else "") + '</div><div id="lb-home-ex" style="padding:6px 8px 4px"></div>' + rnote + '</div></div></div></section>')
    dk = ""
    if docket:
        items = "".join(f'<div><span class="lb-status">{t(i["status"])}</span><b>{t(i["question"])}</b></div>' for i in docket)
        dk = ('<section class="lb-docket"><div style="display:flex;justify-content:space-between;align-items:baseline;gap:14px;flex-wrap:wrap"><h2>On the docket</h2>'
              '<span style="font-size:15px;color:var(--ink-2)">Questions in progress. No verdicts until the work is done.</span></div>'
              f'<div class="lb-docket-list">{items}</div></section>')
    links = ('<section class="lb-links"><a href="/#method">How DAWG works</a><a href="/lab/corrections/">Corrections</a>'
             f'<a href="{url}plan/">LAB {num} research plan</a><span>Got a theory about your team? Reply to @dawgindex with <b>#AskTheLab</b>.</span></section>')
    head = ('<section class="lb-home-head"><div class="lb-lockup"><span class="lb-labtag">LAB</span><h1>Every fan base has a theory. We test them.</h1></div>'
            '<p>College football arguments, checked against the data. The plan is written before the results.</p></section>')
    content = f'<main class="lb-main lb-home" style="padding-top:0">{head}{feat}{dk}{links}<p class="lb-note" style="margin-top:20px">DAWG = points better or worse than Vegas expected, garbage time removed.</p></main>'
    data_js = js_data(case, data, teams)
    rep = head_rep(tpl, "The DAWG Lab · DAWG Index", "College football arguments, checked against the data.", SITE + "/lab/", SITE + "/lab/",
                   "The DAWG Lab: every fan base has a theory. We test them.", "College football arguments, checked against the data. The plan is written before the results.",
                   SITE + url + "og.png", "The DAWG Lab", og_type="website", preview=preview)
    rep.update({"ASSET_V": asset_v, "LAB_CURRENT": ' aria-current="page"', "BODY_ATTR": "", "BANNERS": banners(case, preview), "CONTENT": content,
                "SCRIPTS": f'<script id="lab-data" type="application/json">{jdump(data_js)}</script>\n<script src="/lab/lab.js?v={asset_v}"></script>'})
    return page(tpl, rep)


def corrections_page(cases, tpl, asset_v, preview=False):
    rows = []
    for case, _, _ in cases:
        for c in case["corrections"]:
            rows.append((c["date"], f'<div class="lb-corr"><b>{t(B.nice_date(c["date"]))} · <a href="/lab/{case["number"]}-{case["slug"]}/">LAB {case["number"]}</a>:</b> {t(c["text"])}</div>'))
    body = "".join(r for _, r in sorted(rows, reverse=True)) or "<p>No corrections yet. Any correction to a Lab case is dated here and on the case itself.</p>"
    content = ('<section class="lb-cover"><div class="lb-cover-in"><nav class="lb-crumb" aria-label="Breadcrumb"><a href="/lab/">The Lab</a> / Corrections</nav>'
               '<h1 style="font-size:clamp(36px,5vw,60px)">Corrections</h1><p class="lb-dek">Every change to a published finding, dated. Nothing is edited silently, and nothing is deleted.</p></div></section>'
               f'<main class="lb-main"><article class="col"><div class="body">{body}</div></article></main>')
    rep = head_rep(tpl, "Corrections · DAWG Lab", "Every correction to a DAWG Lab case, dated.", SITE + "/lab/corrections/", SITE + "/lab/corrections/",
                   "DAWG Lab corrections", "Every correction to a DAWG Lab case, dated.", SITE + "/og.png", "DAWG Index", og_type="website", preview=preview)
    rep.update({"ASSET_V": asset_v, "LAB_CURRENT": ' aria-current="page"', "BODY_ATTR": "", "BANNERS": banners(cases[0][0], preview), "CONTENT": content, "SCRIPTS": ""})
    return page(tpl, rep)


def redirect_page(case, title, desc, image, alt, target, canonical, og_url, preview=False):
    """A static redirect GitHub Pages can serve: instant meta refresh (search engines read it as permanent), a canonical
    link, and a script that keeps ?query and #hash. It carries its own preview tags so a pasted link shows the right card."""
    robots = '<meta name="robots" content="noindex, follow">'
    return ("<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
            f"<title>{a(title)}</title>\n<meta name=\"description\" content=\"{a(desc)}\">\n<link rel=\"canonical\" href=\"{canonical}\">\n{robots}\n"
            f"<meta property=\"og:type\" content=\"article\">\n<meta property=\"og:site_name\" content=\"DAWG Index\">\n<meta property=\"og:url\" content=\"{og_url}\">\n"
            f"<meta property=\"og:title\" content=\"{a(title)}\">\n<meta property=\"og:description\" content=\"{a(desc)}\">\n"
            f"<meta property=\"og:image\" content=\"{image}\">\n<meta property=\"og:image:width\" content=\"1200\"><meta property=\"og:image:height\" content=\"630\">\n"
            f"<meta property=\"og:image:alt\" content=\"{a(alt)}\">\n<meta name=\"twitter:card\" content=\"summary_large_image\">\n<meta name=\"twitter:site\" content=\"@dawgindex\">\n"
            f"<meta name=\"twitter:title\" content=\"{a(title)}\">\n<meta name=\"twitter:description\" content=\"{a(desc)}\">\n<meta name=\"twitter:image\" content=\"{image}\">\n"
            f"<meta http-equiv=\"refresh\" content=\"0; url={target}\">\n"
            "<script>(function(){var t=" + json.dumps(target) + ";var q=location.search;if(q&&t.indexOf('?')>-1){q='&'+q.slice(1);}location.replace(t+q+location.hash);})();</script>\n"
            f"</head>\n<body style=\"background:#131210;color:#F4EAD2;font:16px Barlow,system-ui,sans-serif;padding:24px\">\n<p><a href=\"{target}\" style=\"color:#F4EAD2\">{t(title)}</a></p>\n</body>\n</html>\n")


def team_stub(case, tm, preview=False):
    num, base = case["number"], case_url(case)
    q = case["presentation"]["team_question"].replace("{team}", tm["name"])
    title = f"{q} · DAWG Lab {num}"
    # never truncated: the descriptive tag at the end must survive in every preview
    desc = " ".join(x for x in (tm["sentence"], tm["band_text"], tm["research_text"], f"What happened, not a verdict on {tm['name']}.") if x)
    img = f"{base}og/{tm['slug']}.png" if tm["card"] else base + "og.png"
    return redirect_page(case, title, desc, img, f"{tm['name']} in DAWG Lab case {num}", f"/lab/{num}-{case['slug']}/?team={tm['slug']}",
                         f"{base}?team={tm['slug']}", f"{SITE}/lab/{num}/{tm['slug']}/", preview)


def sitemap(cases):
    rows = [f"<url><loc>{SITE}/lab/</loc></url>", f"<url><loc>{SITE}/lab/corrections/</loc></url>"]
    for case, _, _ in cases:
        lm = case.get("updated") or case["versions"][-1]["date"]
        rows += [f"<url><loc>{case_url(case)}</loc><lastmod>{lm}</lastmod></url>", f"<url><loc>{case_url(case)}plan/</loc><lastmod>{lm}</lastmod></url>"]
    return '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(rows) + "\n</urlset>\n"


def manifest(cases):
    out = []
    for case, _, _ in cases:
        out.append({"number": case["number"], "slug": case["slug"], "url": f"/lab/{case['number']}-{case['slug']}/", "title": case["title"],
                    "type": case["type"], "verdict": (case.get("verdict") or {}).get("kind"), "version": case["version"],
                    "published": case.get("published"), "updated": case.get("updated"), "data_cutoff": case["data_lock"]["cutoff"],
                    "plan": plan_label(case)})
    return json.dumps({"version": 1, "cases": out}, ensure_ascii=False, indent=1) + "\n"


# ---------------------------------------------------------------- share cards and preview images
LOCK = ('<div class="lock"><svg viewBox="0 -0.8 334.3 126.0" aria-hidden="true"><path fill="#F4EAD2" fill-rule="evenodd" d="M0,0 H40.9 C51.70,0.00 58.90,10.40 58.90,26.00 V98.1 C58.90,113.70 50.90,124.10 38.90,124.10 H0 Z M26.2,25.3 H29.3 Q32.3,25.3 32.3,28.3 V95.1 Q32.3,98.1 29.3,98.1 H26.2 Z M70.45,0 H105.25 L116.95,124.1 H93.35 L91.55,102.9 H83.25 L81.55,124.1 H59.25 Z M87.45,43 L90.35,77.3 H84.55 Z M110.15,0 H133.35 L136.65,50.8 L140.85,0 H160.9 L164.65,52.4 L167.8,0 H190.25 L180.65,124.1 H156.15 L150.65,77.1 L145.15,124.1 H120.45 Z M189.9,23.2 C189.90,8.98 196.70,-0.50 206.90,-0.50 H228.9 C239.10,-0.50 245.90,8.98 245.90,23.20 V45.1 H220.5 V27.1 A2.6,2.6 0 0 0 215.3,27.1 V96.9 A2.6,2.6 0 0 0 220.5,96.9 V76.3 H217.8 V52.3 H245.9 V124.1 H229.9 V119.2 C229.9,122.6 225.2,124.6 217.5,124.6 H206.9 C196.70,124.60 189.90,115.24 189.90,101.20 Z"/>'
        '<path fill="#2F64C0" d="M246.2,0.00 H334.28 L323.16,37.57 H252.2 V19.6 C252.2,12 248.6,4 246.2,0.00 Z"/><path fill="#F5C030" d="M252.2,43.27 H321.47 L310.35,80.83 H252.2 Z"/><path fill="#E5463A" d="M252.2,86.53 H308.67 L297.55,124.10 H252.2 Z"/></svg><span>LAB</span></div>')
DEF = "DAWG = points better or worse than Vegas expected, garbage time removed."


def card_inner(case, tm, size, look="sample"):
    num = case["number"]
    rd = case["research_datasets"][0] if case["research_datasets"] else None
    if tm is None:
        v = case["verdict"]
        word, cls = VERDICTS[v["kind"]]
        st = f'<div class="stamp v-{cls}"><i><b>{t(word)}</b><small>{t(v["subtitle"])}</small></i></div>'
        rn = f'<div class="rn"><i></i>{t(rd["label"])}</div>' if rd else ""
        if size == "card":
            return (f'<div class="top"><span class="tab">LAB {num}</span>{LOCK}</div><div class="q">{t(case["title"])}</div>'
                    f'<div style="display:flex;align-items:center;gap:36px">{st}<div class="sent">{t(v["answer"])}</div></div>'
                    f'<div class="ex"><div class="h">Exhibit A · each dot is one of 68 programs</div><div data-chart="carryover" style="flex:1;min-height:0"></div>{rn}</div>'
                    f'<div class="foot"><p>{DEF}</p><b>dawgindex.com/lab/{num}</b></div>')
        return (f'<div class="top"><span class="tab">LAB {num}</span>{LOCK}</div><div class="row"><div class="l"><div class="q">{t(case["title"])}</div>'
                f'<div style="display:flex;align-items:center;gap:22px">{st}</div></div>'
                f'<div class="r"><div class="ex"><div class="h">Exhibit A · 68 programs</div><div data-chart="carryover" style="flex:1;min-height:0"></div>{rn}</div></div></div>'
                f'<div class="band"><span>{t(v["answer"])[:110]}</span><b>dawgindex.com/lab/{num}</b></div>')
    # team cards: built to read at timeline size on X. Headline, sample size and chart; nothing else competes with them.
    q = case["presentation"]["team_question"].replace("{team}", tm["name"])
    logo = f'<img src="/logos/{tm["id"]}-dark.png" onerror="this.onerror=null;this.src=\'/logos/{tm["id"]}.png\'" alt="">' if tm.get("id") else ""
    rn = f'<div class="rn"><i></i>{t(tm["card_research"])}</div>' if (rd and tm["has_research"]) else ""
    tag = '<span class="stag">Sample data</span>' if (case.get("sample") and look == "production") else ""
    ss = (f'<div class="ss"><b>{tm["hf_games"]}</b><span>games {t(case["presentation"]["measure_short"])}<br>'
          f'across {tm["seasons"]} seasons</span></div>')
    if size == "card":
        return (f'<div class="top"><span class="tab">LAB {num} · YOUR TEAM</span>{LOCK}</div>'
                f'<div class="who">{logo}<div><div class="tn">{t(tm["name"])}</div><div class="qs">{t(q)}</div></div></div>'
                f'<div class="hl">{t(tm["answer"])}</div>{ss}'
                f'<div class="ex"><div class="h"><span>{t(tm["name"])} vs. luck</span>{tag}</div><div data-chart="strip" data-team="{tm["slug"]}" data-size="xl"></div>{rn}</div>'
                f'<div class="foot"><span class="desc">What happened · not a verdict</span><b>{t(tm["short_url"])}</b></div>')
    return (f'<div class="top"><span class="tab">LAB {num} · YOUR TEAM</span>{LOCK}</div>'
            f'<div class="row"><div class="l"><div class="who">{logo}<div><div class="tn">{t(tm["name"])}</div><div class="qs">{t(q)}</div></div></div>'
            f'<div class="hl">{t(tm["answer"])}</div>{ss}</div>'
            f'<div class="r"><div class="ex"><div class="h"><span>{t(tm["name"])} vs. luck</span>{tag}</div><div data-chart="strip" data-team="{tm["slug"]}" data-size="xl"></div>{rn}</div></div></div>'
            f'<div class="band"><span>What happened · not a verdict on {t(tm["name"])}</span><b>{t(tm["short_url"])}</b></div>')


def card_page(case, data, teams, tm, size, tpl, look="sample"):
    pg = read(os.path.join(tpl, "lab", "card.html"))
    d = js_data(case, data, {tm["slug"]: tm} if tm else {})
    sample = '<span class="sample">SAMPLE</span>' if (case.get("sample") and look != "production") else ""
    for k, v in {"{{SIZE}}": size, "{{SAMPLE}}": sample, "{{INNER}}": card_inner(case, tm, size, look), "{{DATA}}": jdump(d)}.items():
        pg = pg.replace(k, v)
    return pg


def render_cards(jobs, repo, extra_files, log):
    """jobs: [(html, out_png, size, team_slug_or_case)]. Re-renders only when the input changed (hash stamped into the PNG).
    Each PNG also carries which team it shows (tEXt dawg-lab-team), so tests can prove every preview image is the right team's."""
    import thumbs
    tpl_hash = hashlib.sha256(read(os.path.join(HERE, "templates", "lab", "card.html"), "rb") + read(os.path.join(HERE, "templates", "lab", "lab.js"), "rb")).hexdigest()[:12]
    todo = []
    for h, out, size, who in jobs:
        key = hashlib.sha256((tpl_hash + h).encode()).hexdigest()[:16]
        if os.path.isfile(out) and B.png_text(out, "dawg-lab-card") == key and B.png_text(out, "dawg-lab-team") == who:
            continue
        todo.append((h, out, size, key, who))
    if not todo:
        return
    from playwright.sync_api import sync_playwright
    import mimetypes, requests
    S = requests.Session()
    if os.path.exists(B.CA):
        S.verify = B.CA
    font_cache = {}
    pages = {}
    def route(r):
        u = r.request.url
        if u.startswith("https://card.local/"):
            path = u.split("https://card.local/", 1)[1].split("?")[0]
            if path in pages:
                return r.fulfill(status=200, body=pages[path].encode(), headers={"content-type": "text/html"})
            if path in extra_files:
                return r.fulfill(status=200, body=extra_files[path], headers={"content-type": mimetypes.guess_type(path)[0] or "application/octet-stream"})
            f = os.path.join(repo, path)
            if os.path.isfile(f):
                return r.fulfill(status=200, body=read(f, "rb"), headers={"content-type": mimetypes.guess_type(f)[0] or "application/octet-stream"})
            return r.fulfill(status=404, body=b"")
        if "fonts.googleapis.com" in u or "fonts.gstatic.com" in u:
            if u not in font_cache:
                x = S.get(u, headers={"User-Agent": r.request.headers.get("user-agent", "")}, timeout=30)
                font_cache[u] = (x.status_code, x.content, x.headers.get("content-type", ""))
            st, body, ct = font_cache[u]
            return r.fulfill(status=st, body=body, headers={"content-type": ct})
        return r.fulfill(status=404, body=b"")
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = {}
        for i, (h, out, size, key, who) in enumerate(todo):
            w, hgt = (1080, 1350) if size == "card" else (1200, 630)
            if size not in ctx:
                ctx[size] = b.new_context(viewport={"width": w, "height": hgt}, device_scale_factor=1)
                ctx[size].route("**/*", route)
            name = f"c{i}.html"
            pages[name] = h
            pg = ctx[size].new_page()
            pg.goto("https://card.local/" + name)
            pg.wait_for_function("document.body.getAttribute('data-ready')==='1'", timeout=15000)
            pg.evaluate("document.fonts.ready")
            pg.wait_for_timeout(120)
            if not pg.evaluate("document.fonts.check('900 40px \"Big Shoulders Display\"')"):
                raise LabError("brand fonts didn't load for a share card")
            png = pg.screenshot(clip={"x": 0, "y": 0, "width": w, "height": hgt})
            pg.close()
            B.write_if_changed(out, thumbs.add_png_text(thumbs.add_png_text(png, "dawg-lab-card", key), "dawg-lab-team", who), log)
        b.close()


# ---------------------------------------------------------------- the whole tree for a set of cases
def assets(tpl):
    css, js = read(os.path.join(tpl, "lab", "lab.css"), "rb"), read(os.path.join(tpl, "lab", "lab.js"), "rb")
    return css, js, hashlib.sha256(css + js).hexdigest()[:10]


def render_tree(repo, out_root, cases, docket, log, preview=False, cards=True):
    """Write /lab/ for these cases under out_root (the repo for build, a private folder for preview)."""
    tpl = os.path.join(repo, "_editorial", "templates")
    css, js, av = assets(tpl)
    lab = os.path.join(out_root, "lab")
    B.write_if_changed(os.path.join(lab, "lab.css"), css, log)
    B.write_if_changed(os.path.join(lab, "lab.js"), js, log)
    jobs = []
    for case, md, data, plan, teams in cases:
        d = os.path.join(lab, f"{case['number']}-{case['slug']}")
        B.write_if_changed(os.path.join(d, "index.html"), case_page(case, md, data, teams, tpl, av, preview), log)
        B.write_if_changed(os.path.join(d, "plan", "index.html"), plan_page(case, plan, tpl, av, preview), log)
        B.write_if_changed(os.path.join(d, "data.json"), json.dumps(js_data(case, data, teams), ensure_ascii=False, indent=1) + "\n", log)
        num = case["number"]
        B.write_if_changed(os.path.join(lab, num, "index.html"),
                           redirect_page(case, f"LAB {num}: {case['title']}", case["description"], case_url(case) + "og.png", f"DAWG Lab case {num}",
                                         f"/lab/{num}-{case['slug']}/", case_url(case), f"{SITE}/lab/{num}/", preview), log)
        for slug, tm in teams.items():
            B.write_if_changed(os.path.join(lab, num, slug, "index.html"), team_stub(case, tm, preview), log)
        if cards:
            look = "production" if preview == "production" else "sample"
            jobs.append((card_page(case, data, teams, None, "card", tpl, look), os.path.join(d, "card.png"), "card", "case"))
            jobs.append((card_page(case, data, teams, None, "og", tpl, look), os.path.join(d, "og.png"), "og", "case"))
            for slug, tm in teams.items():
                if tm["card"]:
                    jobs.append((card_page(case, data, teams, tm, "card", tpl, look), os.path.join(d, "cards", slug + ".png"), "card", slug))
                    jobs.append((card_page(case, data, teams, tm, "og", tpl, look), os.path.join(d, "og", slug + ".png"), "og", slug))
    simple = [(c, d_, tm) for c, _, d_, _, tm in cases]
    B.write_if_changed(os.path.join(lab, "index.html"), landing_page(simple, docket, tpl, av, preview), log)
    B.write_if_changed(os.path.join(lab, "corrections", "index.html"), corrections_page(simple, tpl, av, preview), log)
    B.write_if_changed(os.path.join(lab, "lab.json"), manifest(simple), log)
    B.write_if_changed(os.path.join(lab, "sitemap.xml"), sitemap(simple), log)
    if jobs:
        render_cards(jobs, repo, {"lab/lab.js": js, "lab/lab.css": css}, log)


APPROVAL_KEYS = ("approved_by", "approved_at", "published", "approved_hash")


def fingerprint(case, md, data, plan):
    """What Matthew approved: the whole case (copy, team headlines, verdict, references), its data and its plan. Any edit
    after approval changes this, and build refuses until the case is re-approved."""
    c = {k: v for k, v in case.items() if k not in APPROVAL_KEYS}
    blob = json.dumps(c, sort_keys=True, ensure_ascii=False) + "\0" + json.dumps(data, sort_keys=True, ensure_ascii=False) + "\0" + md + "\0" + plan
    return "sha256:" + hashlib.sha256(blob.encode()).hexdigest()


def prepare(repo, dirs, mode):
    site_teams = B.team_slugs(repo)
    ids, names = B.team_ids(repo), B.team_names(repo, site_teams)
    cases, problems = [], []
    for d in dirs:
        name = os.path.basename(d.rstrip("/"))
        try:
            case, md, data, plan = load_case(d)
        except LabError as e:
            problems.append(str(e))
            continue
        errs = validate(case, md, data, plan, d, site_teams, mode)
        if not errs:
            teams = derive_teams(case, data, ids, names, site_teams)
            errs += team_copy_errors(teams)
            try:
                body_html(case, md, data)
            except LabError as e:
                errs.append(str(e))
        if mode == "publish" and case.get("approved_hash") != fingerprint(case, md, data, plan):
            errs.append("edited after approval (copy, headlines, data or plan no longer match what was approved); "
                        "re-approve with: lab.py reapprove " + name + " --by NAME")
        problems += [f"{name}: {e}" for e in errs]
        if not errs:
            cases.append((case, md, data, plan, teams))
    nums = [c[0]["number"] for c in cases]
    for n in {x for x in nums if nums.count(x) > 1}:
        problems.append(f"duplicate case number {n}")
    cases.sort(key=lambda c: (c[0].get("published") or "", c[0]["number"]), reverse=True)
    return cases, problems


def build(repo, dry=False, quiet=False):
    src = os.path.join(repo, "_editorial", "lab")
    dirs = sorted(d for d in glob.glob(os.path.join(src, "*")) if os.path.isdir(d))
    cases, problems = prepare(repo, dirs, "publish")
    # rule 2: a published case number keeps its slug forever; a live case whose source is gone stays live
    mp = os.path.join(repo, "lab", "lab.json")
    old = {c["number"]: c for c in json.loads(read(mp)).get("cases", [])} if os.path.isfile(mp) else {}
    present = set()
    for d in dirs:   # read every source, valid or not, so a renamed case is caught whatever else is wrong with it
        m = CASE_DIR.match(os.path.basename(d))
        if not m:
            continue
        present.add(m.group(1))
        o = old.get(m.group(1))
        if o and o["slug"] != m.group(2):
            problems.insert(0, f"LAB {m.group(1)}: slug changed from '{o['slug']}' to '{m.group(2)}'; published URLs never change")
    nums = [CASE_DIR.match(os.path.basename(d)).group(1) for d in dirs if CASE_DIR.match(os.path.basename(d))]
    for n in sorted({x for x in nums if nums.count(x) > 1}):
        if f"duplicate case number {n}" not in problems:
            problems.insert(0, f"duplicate case number {n}: two folders in _editorial/lab/ claim LAB {n}")
    missing = sorted(set(old) - present)
    if missing and not problems:
        problems.append("published case(s) " + ", ".join(missing) + " have no source in _editorial/lab/; restore the source (live cases are never removed or rebuilt without it)")
    if problems:
        raise LabError("build stopped, nothing written:\n  - " + "\n  - ".join(problems))
    log = []
    if not cases:
        if not quiet:
            print("no approved Lab case: the Lab stays unpublished (nothing written)")
        return [], log
    if dry:
        if not quiet:
            print(f"check  {len(cases)} approved case(s) valid")
        return cases, log
    dk = os.path.join(src, "docket.json")
    docket = json.loads(read(dk)) if os.path.isfile(dk) else []
    render_tree(repo, repo, cases, docket, log)
    # the Stories pages gain their Lab nav link in the same build (build.py adds it once lab/lab.json exists)
    sres = B.build(repo, quiet=True)
    log += sres[1] if sres else []
    if not quiet:
        for k, w in log:
            print(f"{k:7} {w}")
        print(f"{len(cases)} live case(s); {len(log)} file(s) written; nothing deleted")
    return cases, log


def preview(repo, draft_dir, out_root=PREVIEWS, shots=True, cards=True, look="sample"):
    draft_dir, out_root = os.path.abspath(draft_dir), os.path.abspath(out_root)
    if out_root == os.path.abspath(repo) or out_root.startswith(os.path.abspath(repo) + os.sep):
        raise LabError("previews must be written outside the site repo (it is public)")
    cases, problems = prepare(repo, [draft_dir], "preview")
    if problems:
        raise LabError("preview stopped:\n  - " + "\n  - ".join(problems))
    dk = os.path.join(os.path.dirname(draft_dir), "docket.json")
    docket = json.loads(read(dk)) if os.path.isfile(dk) else []
    log = []
    render_tree(repo, out_root, cases, docket, log, preview="production" if look == "production" else True, cards=cards)
    print(f"preview written to {out_root}/lab (private; not in the repo; every page marked noindex)")
    return out_root


def approve(repo, draft_dir, by):
    if not by or not by.strip():
        raise LabError("approve needs --by (the person who approved it)")
    case, md, data, plan = load_case(draft_dir)
    if case.get("sample"):
        raise LabError("this case is marked sample: sample data never publishes")
    dest = os.path.join(repo, "_editorial", "lab", os.path.basename(draft_dir.rstrip("/")))
    if os.path.exists(dest):
        raise LabError(f"{dest} already exists; publish a new version there instead")
    now = B.local_now()
    case.update(status="published", approved_by=by.strip(), approved_at=now.date().isoformat(), published=now.date().isoformat())
    case["versions"][-1]["date"] = now.date().isoformat()
    tmp = copy.deepcopy(case)
    site = B.team_slugs(repo)
    errs = validate(tmp, md, data, plan, draft_dir, site, "publish")
    if not errs:
        errs = team_copy_errors(derive_teams(tmp, data, B.team_ids(repo), B.team_names(repo, site), site))
    if errs:
        raise LabError("not approved:\n  - " + "\n  - ".join(errs))
    case["approved_hash"] = fingerprint(case, md, data, plan)
    shutil.copytree(draft_dir, dest, ignore=shutil.ignore_patterns("*.png", ".*"))
    with open(os.path.join(dest, "case.json"), "w") as f:
        f.write(json.dumps(case, ensure_ascii=False, indent=1) + "\n")
    print(f"approved: LAB {case['number']} moved to {os.path.relpath(dest, repo)}; run build, then commit _editorial/ and lab/ only")


def reapprove(repo, case_dir, by):
    """After an approved case is edited (a correction, a new version, revised headlines), Matthew re-approves it."""
    if not by or not by.strip():
        raise LabError("reapprove needs --by (the person who approved the change)")
    d = case_dir if os.path.isdir(case_dir) else os.path.join(repo, "_editorial", "lab", case_dir)
    case, md, data, plan = load_case(d)
    if not os.path.abspath(d).startswith(os.path.join(os.path.abspath(repo), "_editorial", "lab") + os.sep):
        raise LabError("reapprove is for cases already in _editorial/lab/; new drafts use approve")
    if case.get("sample"):
        raise LabError("this case is marked sample: sample data never publishes")
    case.update(approved_by=by.strip(), approved_at=B.local_now().date().isoformat())
    site = B.team_slugs(repo)
    errs = validate(copy.deepcopy(case), md, data, plan, d, site, "publish")
    if not errs:
        errs = team_copy_errors(derive_teams(case, data, B.team_ids(repo), B.team_names(repo, site), site))
    if errs:
        raise LabError("not re-approved:\n  - " + "\n  - ".join(errs))
    case["approved_hash"] = fingerprint(case, md, data, plan)
    with open(os.path.join(d, "case.json"), "w") as f:
        f.write(json.dumps(case, ensure_ascii=False, indent=1) + "\n")
    print(f"re-approved: LAB {case['number']} by {by.strip()}; run build")


# ---------------------------------------------------------------- a clearly marked SAMPLE case for building the pages
def sample(repo, out_root):
    """Writes 001-playing-down with SAMPLE numbers (random, seeded) for all 68 programs. It carries sample: true, so it can
    never be approved or built into the site. Real copy and data come from the research session once its plan is locked."""
    rnd = random.Random(1001)
    site = sorted(B.team_slugs(repo))
    d = os.path.join(out_root, "001-playing-down")
    os.makedirs(d, exist_ok=True)
    below = {"kansas": (6, 3), "purdue": (7, 3), "georgia-tech": (5, 2)}
    teams, points = {}, []
    for s in site:
        if s in below:
            hf, ns = below[s]
            ns_n = [hf // ns + (1 if i < hf % ns else 0) for i in range(ns)]
        else:
            ns = rnd.randint(3, 13)
            ns_n = [rnd.randint(2, 6) for _ in range(ns)]
            hf = sum(ns_n)
        se = 12.0 / math.sqrt(hf)
        raw = round(rnd.gauss(0, se), 1)
        band = round(1.96 * 12.5 / math.sqrt(hf), 1)
        adj = round(raw * (1.0 / (1.0 + se * se)), 1)
        yrs = sorted(rnd.sample(range(2014, 2027), ns))
        srows = [{"season": y, "gap": round(rnd.gauss(0, 7), 1), "n": n, "research": y <= 2018} for y, n in zip(yrs, ns_n)]
        labels = ["14+ favorite", "3.5–13.5 favorite", "Within 3", "3.5+ underdog"]
        groups = [{"label": labels[0], "avg": round(raw / 2 + rnd.gauss(0, 1), 1), "n": hf}] + \
                 [{"label": l, "avg": round(rnd.gauss(0, 1.5), 1), "n": rnd.randint(4, 40)} for l in labels[1:]]
        teams[s] = {"hf_games": hf, "seasons": ns, "raw": raw, "band": band, "adjusted": adj, "groups": groups, "season_rows": srows}
        points.append({"t": s, "x": round(rnd.gauss(0, 3.2), 1), "y": round(rnd.gauss(0, 3.2), 1)})
    data = {"sample": True, "threshold": 2,
            "league": {"groups": [{"label": "14+ favorite", "avg": -0.1, "n": 2700}, {"label": "3.5–13.5 favorite", "avg": 0.1, "n": 2500},
                                  {"label": "Within 3", "avg": 0.1, "n": 1700}, {"label": "3.5+ underdog", "avg": 0.0, "n": 3300}]},
            "carryover": {"band": 3.2, "includes_research": True, "points": points,
                          "x_label_long": "its earlier seasons (2014–2019)", "y_label_long": "its later seasons (2020–2026)"},
            "cuts": [{"id": "plan", "label": "All games (the plan’s choice)", "plan": True, "U": 2.4, "note": "Sample number. The plan’s choice: habits bigger than ±2.4 per big-favorite game are ruled out."},
                     {"id": "p4", "label": "Vs. Power 4 only", "U": 3.1, "note": "Sample number. This cut rules out habits bigger than ±3.1. The verdict always uses the plan’s choice."},
                     {"id": "month", "label": "Aug–Sep vs. non-Power 4", "U": 3.4, "note": "Sample number. This cut rules out habits bigger than ±3.4. The verdict always uses the plan’s choice."},
                     {"id": "no1416", "label": "Without 2014–16", "U": 2.7, "note": "Sample number. Without the earliest research-grade seasons: habits bigger than ±2.7 are ruled out."},
                     {"id": "ats", "label": "Final score vs. spread", "U": 2.9, "note": "Sample number. The same test on final scores (a football stat, not a DAWG grade): ±2.9."}],
            "teams": teams}
    case = {"number": "001", "slug": "playing-down", "type": "hypothesis-test", "status": "draft", "sample": True,
            "title": "Does your team play down to its competition?", "topic": "Favorites & underdogs",
            "dek": "Every fan base swears its team sleepwalks against weak opponents. We checked whether the habit is real, program by program.",
            "description": "Every fan base swears its team plays down to weak opponents. The DAWG Lab checked all 68 programs, season after season.",
            "verdict": {"kind": "inconclusive", "subtitle": "Sample · reason from the plan", "answer": "Sample answer. The published case states the verdict in one plain sentence here."},
            "version": "1.0", "plan": {"version": "2.0", "label": "v2", "locked": "2026-10-20"},
            "data_lock": {"snapshot": "sha256:sample000000000000000000", "cutoff": "2026-10-18", "label": "Data through Week 8, 2026"},
            "methods": {"dawg": "V3.0", "case": "1.0"},
            "second_check": "Sample: the independent rerun is recorded here",
            "research_datasets": [{"name": "2014–18 research grades", "span": "2014–2018", "provenance": "Sample provenance line: the formula, the frozen fits used, and the reproduction check go here.",
                                   "label": "Includes research grades for 2014–2018: computed with the DAWG formula, not official DAWG grades.",
                                   "label_short": "research grade (2014–2018), not an official DAWG grade"}],
            "versions": [{"version": "1.0", "date": "2026-10-20", "change": "First published", "verdict": "inconclusive"}],
            "corrections": [],
            "presentation": {"measure_short": "as a 14+ point favorite", "short_measure": "as a big favorite",
                             "team_question": "Does {team} play down to its competition?",
                             "team_min": {"hf_games": 8, "seasons": 3}, "band_coverage": 95, "team_headlines": {"within": "Within the luck range", "outside": "Outside the luck range", "below": "Too few games to judge", "none": "No qualifying games"}, "team_min_text": "8 games as a 14+ point favorite across 3 eligible seasons",
                             "x_label": "Earlier seasons", "y_label": "Later seasons"}}
    md = """::: part
Part 1 · description only
:::

## What happened

Every program plays a few games a year as a heavy favorite. Fans remember the close calls: a one-score win as a four-touchdown favorite feels like a warning sign, even when the team was in control most of the night.

Sample text. The published case describes, in plain numbers, how programs graded as big favorites compared with their other games. This part makes no claim that anything repeats.

::: part
Part 2 · the verdict covers only this part
:::

## Is it a pattern?

A bad September doesn't make a habit. The question is whether a program that plays down one season does it again in another. If it does, the dots in Exhibit A line up along the diagonal. If not, they scatter around the flat line.

[[bound]]

Sample text. The published case says what the data rules out, what it doesn't, and what would settle it.

## Other ways to cut it

The research plan named these cuts in advance. The verdict always uses the plan's choice, and another cut can only weaken a verdict, never strengthen it.

[[cuts]]

::: doesnt
- Why a team played the way it did. Effort, focus and coaching aren't measured.
- Anything Vegas already prices in. DAWG measures play against the closing line.
- Sample: the limits from the research plan go here.
:::
"""
    plan = "## Sample plan\n\nSample text. The approved research plan for this case is published here in full, including its exploration disclosure, once the research session locks it.\n"
    with open(os.path.join(d, "case.json"), "w") as f:
        f.write(json.dumps(case, ensure_ascii=False, indent=1) + "\n")
    with open(os.path.join(d, "data.json"), "w") as f:
        f.write(json.dumps(data, ensure_ascii=False, indent=1) + "\n")
    with open(os.path.join(d, "case.md"), "w") as f:
        f.write(md)
    with open(os.path.join(d, "plan.md"), "w") as f:
        f.write(plan)
    docket = [{"status": "IN RESEARCH", "question": "Do big favorites win by less than they should?"},
              {"status": "ON THE DOCKET", "question": "Is winning close games a skill?"},
              {"status": "ON THE DOCKET", "question": "Do bye weeks actually help?"}]
    with open(os.path.join(out_root, "docket.json"), "w") as f:
        f.write(json.dumps(docket, ensure_ascii=False, indent=1) + "\n")
    print(f"sample case written to {d} (marked sample: it can't be approved or published)")
    return d


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["build", "check", "preview", "approve", "reapprove", "sample"])
    ap.add_argument("path", nargs="?")
    ap.add_argument("--repo", default=os.path.dirname(HERE))
    ap.add_argument("--by")
    ap.add_argument("--out", default=PREVIEWS)
    ap.add_argument("--no-shots", action="store_true")
    ap.add_argument("--no-cards", action="store_true")
    ap.add_argument("--look", choices=["sample", "production"], default="sample",
                    help="production: a private preview without the Preview/Sample banners or card ribbon, to judge the live look (still noindex, still sample data)")
    o = ap.parse_args()
    try:
        if o.cmd == "build":
            build(o.repo)
        elif o.cmd == "check":
            build(o.repo, dry=True)
        elif o.cmd == "preview":
            if not o.path:
                ap.error("preview needs the draft folder")
            preview(o.repo, o.path, o.out, shots=not o.no_shots, cards=not o.no_cards, look=o.look)
        elif o.cmd == "approve":
            if not o.path:
                ap.error("approve needs the draft folder")
            approve(o.repo, o.path, o.by)
        elif o.cmd == "reapprove":
            if not o.path:
                ap.error("reapprove needs the case folder")
            reapprove(o.repo, o.path, o.by)
        elif o.cmd == "sample":
            sample(o.repo, o.path or DRAFTS)
    except B.BuildError as e:
        print("ERROR: " + str(e), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
