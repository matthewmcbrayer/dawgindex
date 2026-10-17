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
# the upper bound isn't published: no "ruled out" sizes and no ±N bound wording anywhere in a case's copy
RULED_OUT = re.compile(r"\bruled out\b|±\s*\d", re.I)


class LabError(B.BuildError):
    pass


def t(s): return B.t(s)
def a(s): return B.a(s)
def fmt(v):
    """one decimal, rounded exactly like the page script (JS toFixed: the exact binary value, ties away from zero); no "−0.0" """
    import decimal
    m = str(decimal.Decimal(abs(v)).quantize(decimal.Decimal("0.1"), rounding=decimal.ROUND_HALF_UP))
    return ("" if m == "0.0" else "+" if v > 0 else "−") + m
def read(p, mode="r"): return B.read(p, mode)
def jdump(o): return json.dumps(o, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


# ---------------------------------------------------------------- loading and validation
def load_case(d):
    m = CASE_DIR.match(os.path.basename(d.rstrip("/")))
    if not m:
        raise LabError(f"{d}: folder must be named NNN-slug (e.g. 001-playing-down)")
    try:
        oi = os.path.isfile(os.path.join(d, "case.json")) and json.loads(read(os.path.join(d, "case.json"))).get("type") == OI_TYPE
    except json.JSONDecodeError as e:
        raise LabError(f"{os.path.basename(d)}: invalid JSON: {e}")
    need = ["case.json", "case.md", "data.json"] + (["explorer.json"] if oi else ["plan.md"])
    miss = [f for f in need if not os.path.isfile(os.path.join(d, f))]
    if miss:
        raise LabError(f"{os.path.basename(d)}: missing " + ", ".join(miss))
    try:
        case = json.loads(read(os.path.join(d, "case.json")))
        data = json.loads(read(os.path.join(d, "data.json")))
        if oi:
            raw = read(os.path.join(d, "explorer.json"))
            data["_explorer"] = json.loads(raw)
            data["_explorer_raw"] = raw
            data["_explorer_sha256"] = "sha256:" + hashlib.sha256(raw.encode()).hexdigest()
    except json.JSONDecodeError as e:
        raise LabError(f"{os.path.basename(d)}: invalid JSON: {e}")
    return case, read(os.path.join(d, "case.md")), data, ("" if oi else read(os.path.join(d, "plan.md")))


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
    if case.get("type") == OI_TYPE:
        return validate_oi(case, md, data, d, site_teams, mode)
    errs = []
    name = os.path.basename(d.rstrip("/"))
    m = CASE_DIR.match(name)
    req = ["number", "slug", "type", "status", "title", "topic", "dek", "description", "version", "plan", "data_lock",
           "methods", "versions", "corrections", "presentation", "research_datasets", "verdict_record"]
    for k in req:
        if k not in case or case[k] in (None, ""):
            errs.append(f"missing {k}")
    if errs:
        return errs
    if m and (case["number"], case["slug"]) != (m.group(1), m.group(2)):
        errs.append(f"folder name must be {case['number']}-{case['slug']}")
    if case["type"] != "hypothesis-test":
        errs.append("type must be hypothesis-test or original-investigation")
    v = case.get("verdict") or {}
    if case["type"] == "hypothesis-test":
        if v.get("kind") not in VERDICTS:
            errs.append("verdict.kind must be one of " + ", ".join(VERDICTS))
        if not v.get("subtitle") or len(v["subtitle"]) > 32:
            errs.append("verdict.subtitle (written in the research plan) is required, 32 characters max")
        if not v.get("answer"):
            errs.append("verdict.answer (the 10-second answer) is required")
        if v.get("card_line") and len(v["card_line"]) > 90:
            errs.append("verdict.card_line (the link-preview line) is over 90 characters")
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
    for k in ("measure_short", "short_measure", "team_question", "team_min", "team_min_text"):
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
        errs.append("presentation.band_coverage (how often chance alone lands a program inside its expected range, from the research plan) must be a number from 50 to 99.9")
    if len(case["description"]) > 200:
        errs.append("description over 200 characters")
    # data: team-level summaries exactly as the research deliverable gives them (nothing derived here but arithmetic)
    teams = data.get("teams") or {}
    for slug, tm in teams.items():
        if slug not in site_teams:
            errs.append(f"data.json: unknown team slug '{slug}'")
        for k in ("hf_games", "other_games", "seasons", "eligible_seasons", "raw", "down", "up", "groups", "official", "research_games", "research_hf_games"):
            if k not in tm:
                errs.append(f"data.json {slug}: missing {k}")
        for g in tm.get("groups", []):
            if "n" not in g:
                errs.append(f"data.json {slug}: every group row needs its sample size (n)")
        if tm.get("groups") and all("n" in g for g in tm["groups"]) and sum(int(g["n"]) for g in tm["groups"]) != tm.get("hf_games", 0) + tm.get("other_games", 0):
            errs.append(f"data.json {slug}: the four groups add up to {sum(int(g['n']) for g in tm['groups'])} games, not hf_games + other_games")
        if "raw" in tm and "down" in tm and "up" in tm and abs(tm["raw"] - (tm["down"] - tm["up"])) > 1e-9:
            errs.append(f"data.json {slug}: raw gap must equal down part minus up part")
        mn_ = pres.get("team_min") or {}
        meets = tm.get("hf_games", 0) >= mn_.get("hf_games", 1e9) and tm.get("eligible_seasons", 0) >= mn_.get("seasons", 1e9)
        if meets:
            for k in ("range_lo", "range_hi", "outside"):
                if k not in tm:
                    errs.append(f"data.json {slug}: meets the display minimum but has no {k} (the expected range comes from the research deliverable)")
            if "range_lo" in tm and "range_hi" in tm and "outside" in tm:
                if not tm["range_lo"] < tm["range_hi"]:
                    errs.append(f"data.json {slug}: range_lo must be below range_hi")
                if bool(tm["outside"]) != (tm["raw"] < tm["range_lo"] or tm["raw"] > tm["range_hi"]):
                    errs.append(f"data.json {slug}: 'outside' doesn't match the raw gap and the expected range")
        elif any(k in tm for k in ("range_lo", "range_hi", "outside")):
            errs.append(f"data.json {slug}: below the display minimum, so no expected range may be shown")
        f = tm.get("finding")
        if f:
            for k in ("text", "confirmation", "correction", "plan_ref"):
                if not f.get(k):
                    errs.append(f"data.json {slug}: a team finding needs {k} (otherwise team results stay descriptive)")
        for k in ("adjusted", "shrunk", "band", "season_rows"):
            if k in tm:
                errs.append(f"data.json {slug}: '{k}' isn't part of the approved descriptive outputs")
    if any(tm.get("research_games") for tm in teams.values()) and not case["research_datasets"]:
        errs.append("research-only seasons appear in the data, but case.json lists no research dataset with its provenance")
    for rd in case["research_datasets"]:
        for k in ("name", "span", "provenance", "label", "label_short"):
            if not rd.get(k):
                errs.append(f"research dataset needs {k}")
    for rd_ in case["research_datasets"]:
        if rd_.get("span") and not re.match(r"^\d{4}\s*[–-]\s*\d{4}$", rd_["span"]):
            errs.append("research dataset span must look like 2014–2018")
    ps = data.get("persistence") or []
    if not ps or sum(1 for r in ps if r.get("primary")) != 1:
        errs.append("data.json: persistence must list the carryover estimates with exactly one marked as the plan's main test")
    for r in ps:
        for k in ("id", "label", "T", "SE", "pairs", "programs"):
            if k not in r:
                errs.append(f"data.json persistence row {r.get('id', '?')}: missing {k}")
        if r.get("includes_research") and not case["research_datasets"]:
            errs.append("a carryover estimate uses research grades, but case.json lists no research dataset")
    if "league" not in data:
        errs.append("data.json needs league")
    for k in ("cuts", "threshold", "carryover", "bound"):
        if k in data:
            errs.append(f"data.json: '{k}' belongs to the retired upper-bound layout; LAB pages don't show a ruled-out size")
    # the descriptive tables (spec §2, §7, §8), shown only as the deliverable gives them
    tb = data.get("tables")
    if "[[tables]]" in md and not tb:
        errs.append("case.md shows [[tables]] but data.json has no tables")
    if tb:
        def _scope(sc, where):
            if not sc.get("label") or not isinstance(sc.get("groups"), list) or not sc["groups"]:
                errs.append(f"data.json tables.{where}: needs a label and its groups")
                return
            for g in sc["groups"]:
                if not g.get("label") or not isinstance(g.get("n"), int) or not (g.get("avg") is None or isinstance(g["avg"], (int, float))):
                    errs.append(f"data.json tables.{where}: every group needs a label, its games (n) and an average")
        for i, sc in enumerate(tb.get("league") or []):
            _scope(sc, f"league[{i}]")
        if not tb.get("league"):
            errs.append("data.json tables.league: missing")
        for k in ("postseason", "season2026"):
            sc = tb.get(k)
            if not sc:
                errs.append(f"data.json tables.{k}: missing")
                continue
            _scope(sc, k)
            for f_ in ("title", "note", "programs"):
                if not sc.get(f_):
                    errs.append(f"data.json tables.{k}: missing {f_}")
            for slug in (sc.get("programs") or {}):
                if slug not in teams:
                    errs.append(f"data.json tables.{k}: unknown program '{slug}'")
        if tb.get("postseason") and "opt-out" not in tb["postseason"].get("note", "").lower():
            errs.append("data.json tables.postseason: the note must say opt-outs make postseason games less comparable")
        if tb.get("season2026") and "partial season" not in tb["season2026"].get("note", "").lower():
            errs.append("data.json tables.season2026: the note must label it a partial season")
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
    copy_all = " ".join(strings(case)) + " " + md + " " + " ".join(strings({k: v for k, v in data.items() if k != "teams"}))
    m_ = RULED_OUT.search(copy_all)
    if m_:
        errs.append(f"the copy says '{m_.group(0)}': no size is published as ruled out (the upper bound isn't used)")
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


def rng_text(lo, hi):
    return f"{fmt(lo)} to {fmt(hi)}"


def derive_teams(case, data, ids, names, site_teams):
    """Team copy for the strip, side card, pin, panel, cards and link previews. Descriptive only: it says what happened
    and where that sits against the program's expected range, never that a program has a lasting habit. The expected
    range and its coverage come from the research deliverable (presentation.band_coverage); the copy only restates them."""
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
        if not src or not src.get("hf_games"):
            row.update(state="none", hf_games=0, seasons=0, raw=0, groups=[], has_research=False, card=False,
                       sentence=f"{name} has no games that qualify for this investigation.",
                       band_text="", answer=headline(heads, "none", name), pin=headline(heads, "none", name),
                       short=f"{name}: {headline(heads, 'none', name)}",
                       none_text=((src or {}).get("none_reason") or f"{name} has no qualifying games in the seasons this investigation covers, so there’s nothing to read for it here.") + " The full sample is on the case page.")
            out[slug] = row
            continue
        hf, ns, es, raw = int(src["hf_games"]), int(src["seasons"]), int(src["eligible_seasons"]), float(src["raw"])
        ok = hf >= mn["hf_games"] and es >= mn["seasons"]
        rg, rgh = int(src.get("research_games") or 0), int(src.get("research_hf_games") or 0)
        tot = hf + int(src["other_games"])
        row.update(hf_games=hf, other_games=int(src["other_games"]), seasons=ns, eligible_seasons=es, raw=raw, down=float(src["down"]), up=float(src["up"]),
                   groups=src["groups"], official=src["official"], has_research=rg > 0, research_games=rg, research_hf_games=rgh)
        if rg and rd:
            row["research_text"] = (f"Includes research grades: {rg} of its {tot} games are from {rd['span']} ({rgh} of the {hf} {pres['measure_short']}), "
                                    "computed with the DAWG formula, not official DAWG grades.")
            row["research_short"] = f"incl. {short_span(rd['span'])} research grades"
            row["card_research"] = f"Includes {short_span(rd['span'])} research grades, not official DAWG grades."
        if src.get("finding"):
            f = src["finding"]
            row["finding"] = {"text": f["text"], "receipts": f"{f['confirmation']} · {f['correction']} · {f['plan_ref']}"}
        diff = "the same as" if fmt(raw) == "0.0" else f"{fmt(raw)[1:]} points {'below' if raw < 0 else 'above'}"
        row["sentence"] = f"Over {ns} seasons, {name}’s {hf} games {pres['measure_short']} graded {diff} its other games."
        if ok:
            lo, hi = float(src["range_lo"]), float(src["range_hi"])
            inside = not bool(src["outside"])
            if inside:
                bt = (f"That’s inside the range our no-lasting-tendency simulation gives for its mix of games. "
                      f"Expected range: {rng_text(lo, hi)}.")
            else:
                bt = (f"That’s outside the range our no-lasting-tendency simulation gives for its mix of games. "
                      f"Expected range: {rng_text(lo, hi)}. With 68 programs, about {expect} land outside a {cov_s}% range by chance alone. "
                      "Landing outside one is a description, not a finding.")
            row.update(state="ok", range_lo=lo, range_hi=hi, inside=inside, card=True, band_text=bt, coverage=cov_s,
                       answer=headline(heads, "within" if inside else "outside", name),
                       pin=f"{headline(heads, 'within' if inside else 'outside', name)} · {hf} games",
                       short=f"{name}: {headline(heads, 'within' if inside else 'outside', name)} · {hf} games")
        else:
            row.update(state="below", card=False, coverage=cov_s,
                       band_text=f"Too few games for an expected range: {hf} games {pres['measure_short']} and {es} eligible seasons. A range needs {pres['team_min_text']}.",
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


def all_below(ps):
    """a sentence only when the data says it"""
    return ("Every estimate came out below 0, so every row reads: no lasting spread detected (estimate at or below zero). "
            "Rows marked with a ring use 2014–18 research grades.") if ps and all(r["T"] < 0 for r in ps) else ""


def exhibit_html(kind, case, data, letter, teams=None):
    rd = case["research_datasets"][0] if case["research_datasets"] else None
    tag = '<span class="lb-tagS">Sample data</span>' if case.get("sample") else ""
    if kind == "persistence":
        ps = data["persistence"]
        h = (f'<div class="lb-exhibit" role="group" aria-label="Exhibit {letter}: does it carry over?" id="lb-carry-sec">'
             f'<div class="lb-ex-head"><span>Exhibit {letter} · Does it carry over?</span>{tag}</div>'
             '<div id="lb-persist" style="padding:6px 8px 0"></div>'
             '<div class="lb-ex-foot">Each row is one way of asking the question. Dot = the carryover estimate; bar = one standard error each way. '
             'Above 0 would mean a program’s big-favorite gap repeats from season to season; below 0 means it flips. '
             + all_below(ps) + '</div>')
        if any(r.get("includes_research") for r in ps) and rd:
            h += research_note(rd["label"])
        return h + "</div>"
    if kind == "programs":
        cov = f'{float(case["presentation"]["band_coverage"]):g}'
        h = (f'<div class="lb-exhibit" role="group" aria-label="Exhibit {letter}: every program" id="lb-programs-sec">'
             f'<div class="lb-ex-head"><span>Exhibit {letter} · All 68 programs</span>{tag}</div>'
             '<div id="lb-programs" style="padding:6px 8px 0"></div>'
             f'<div class="lb-ex-foot">Dot = the program’s big-favorite gap: its average DAWG grade {t(case["presentation"]["measure_short"])} minus its average in other games. '
             f'Bar = its {cov}% expected range. Expected range: where this program’s gap would usually land if it had no lasting tendency, under our simulation assumptions '
             '(same-season, same-spread grades from other programs; no carryover between seasons). Filled dots are outside their range. Alphabetical.</div>')
        if rd:
            h += research_note(rd["label"])
        return h + "</div>"
    if kind == "tables":
        return tables_html(case, data, letter, teams or {})
    raise LabError(f"unknown exhibit [[{kind}]]")


def _num(v, signed=True):
    return "—" if v is None else (fmt(v) if signed else f"{v:,}")


def tables_html(case, data, letter, teams):
    """The descriptive tables exactly as the research deliverable gives them (spec §2, §3, §7, §8): all 68 programs, sortable,
    alphabetical by default and never ranked; the league reference; postseason and 2026 kept separate."""
    tb = data.get("tables")
    if not tb:
        raise LabError("[[tables]] needs data.json tables (from the research deliverable)")
    pres = case["presentation"]
    cov = f'{float(pres["band_coverage"]):g}'
    rd = case["research_datasets"][0] if case["research_datasets"] else None
    tag = '<span class="lb-tagS">Sample data</span>' if case.get("sample") else ""
    glab = [g["label"] for g in (data.get("league") or {}).get("groups", [])]
    th = lambda label, kind="n", cls="": f'<th scope="col" class="{cls}" data-k="{kind}"><button type="button">{t(label)}</button></th>'
    head = ("<tr>" + th("Program", "s", "lb-tl") + th("Seasons") + th("Eligible seasons") + th("14+ fav. games") + th("Other games")
            + th("Gap") + th("Down part") + th("Up part") + th("Expected range") + th("Outside?", "s")
            + "".join(th(f"{g}: avg (games)") for g in glab) + th("2019+ official: gap (games)") + "</tr>")
    rows = []
    for slug, tm in sorted(teams.items(), key=lambda kv: kv[1]["name"]):
        if tm["state"] == "none":
            continue
        ok = tm["state"] == "ok"
        rng = rng_text(tm["range_lo"], tm["range_hi"]) if ok else "too few games"
        outside = ("yes" if not tm["inside"] else "no") if ok else "too few games"
        grp = "".join(f'<td data-v="{"" if g["avg"] is None else round(g["avg"], 6)}">{_num(g["avg"])} ({g["n"]})</td>' for g in tm["groups"])
        o = tm["official"]
        rows.append(f'<tr data-team="{slug}"><th scope="row" class="lb-tl" data-v="{a(tm["name"])}">{t(tm["name"])}</th>'
                    f'<td data-v="{tm["seasons"]}">{tm["seasons"]}</td><td data-v="{tm["eligible_seasons"]}">{tm["eligible_seasons"]}</td>'
                    f'<td data-v="{tm["hf_games"]}">{tm["hf_games"]}</td><td data-v="{tm["other_games"]}">{tm["other_games"]}</td>'
                    f'<td data-v="{round(tm["raw"], 6)}"><b>{fmt(tm["raw"])}</b></td><td data-v="{round(tm["down"], 6)}">{fmt(tm["down"])}</td><td data-v="{round(tm["up"], 6)}">{fmt(tm["up"])}</td>'
                    f'<td data-v="{round(tm["range_lo"], 6) if ok else ""}">{rng}</td><td data-v="{outside}">{outside}</td>{grp}'
                    f'<td data-v="{round(o["raw"], 6)}">{fmt(o["raw"])} ({o["hf_games"]} / {o["other_games"]})</td></tr>')
    rlab = (f'<p class="lb-tnote lb-tnr"><i class="lb-rring" aria-hidden="true"></i>{t(rd["label"])}</p>') if rd else ""
    h = (f'<div class="lb-exhibit" role="group" aria-label="Exhibit {letter}: the tables" id="lb-tables">'
         f'<div class="lb-ex-head"><span>Exhibit {letter} · The tables</span>{tag}</div>'
         '<div class="lb-tblock"><h3>Every program, 2014 to Oct. 10, 2026</h3>'
         '<p class="lb-tnote">Alphabetical. Tap a column to sort it; this isn’t a ranking. Points are DAWG grades; the gap is the average grade as a 14+ favorite minus the average in other games. '
         'Gap = down part − up part. The gap is a per-game average; the carryover estimate in Exhibit A uses season-by-season gaps, so the two are different numbers.</p>'
         f'<p class="lb-thint" aria-hidden="true">Scroll sideways for every column →</p><div class="lb-tscroll lb-tall" tabindex="0" role="region" aria-label="Every program, scrolls sideways"><table class="lb-tbl lb-sort" id="lb-prog-tbl"><thead>{head}</thead><tbody>{"".join(rows)}</tbody></table></div>'
         f'<p class="lb-tnote"><b>Expected range:</b> where this program’s gap would usually land if it had no lasting tendency, under our simulation assumptions '
         f'(same-season, same-spread grades from other programs; no carryover between seasons). {cov}% range; a range needs {t(pres["team_min_text"])}. '
         f'<b>Outside?</b> With 68 programs, about {round(68 * (100 - float(cov)) / 100)} land outside a {cov}% range by chance alone. Landing outside one is a description, not a finding.</p>'
         f'{rlab}</div>')
    lg = tb["league"]
    def grid(scopes, col_label):
        hd = "<tr><th scope=\"col\" class=\"lb-tl\">Group</th>" + "".join(f'<th scope="col">{t(sc["label"])}: avg (games)</th>' for sc in scopes) + "</tr>"
        labels = [g["label"] for g in scopes[0]["groups"]]
        body = "".join(f'<tr><th scope="row" class="lb-tl">{t(lb)}</th>' + "".join(f'<td>{_num(sc["groups"][i]["avg"])} ({sc["groups"][i]["n"]:,})</td>' for sc in scopes) + "</tr>"
                       for i, lb in enumerate(labels))
        hint = '<p class="lb-thint" aria-hidden="true">Scroll sideways for every column →</p>' if len(scopes) > 1 else ""
        return hint + f'<div class="lb-tscroll" tabindex="0" role="region" aria-label="{a(col_label)}"><table class="lb-tbl"><thead>{hd}</thead><tbody>{body}</tbody></table></div>'
    h += ('<div class="lb-tblock"><h3>The league, by kind of game</h3>'
          '<p class="lb-tnote">League-wide, DAWG averages about zero in every kind of game, by construction. The 2014–18 and 2019–26 columns split the full window by grade type.</p>'
          + grid(lg, "League by kind of game") + rlab + '</div>')
    ps = tb["postseason"]
    pcount = "".join(f'<li><span>{t(teams[s_]["name"])}</span><b>{n}</b></li>' for s_, n in sorted(ps["programs"].items(), key=lambda kv: teams[kv[0]]["name"]))
    h += (f'<div class="lb-tblock"><h3>{t(ps["title"])}</h3><p class="lb-tnote">{t(ps["note"])}</p>' + grid([ps], "Postseason")
          + f'<details class="lb-tdet"><summary>Postseason games as a 14+ favorite, by program</summary><ul class="lb-tlist">{pcount}</ul></details>' + rlab + '</div>')
    sn = tb["season2026"]
    keys = sn["group_keys"]
    srows = "".join(f'<tr><th scope="row" class="lb-tl">{t(teams[s_]["name"])}</th>' + "".join(f'<td>{c[k]}</td>' for k in keys) + "</tr>"
                    for s_, c in sorted(sn["programs"].items(), key=lambda kv: teams[kv[0]]["name"]))
    shd = '<tr><th scope="col" class="lb-tl">Program</th>' + "".join(f'<th scope="col">{t(g["label"])}</th>' for g in sn["groups"]) + "</tr>"
    h += (f'<div class="lb-tblock"><h3>{t(sn["title"])}</h3><p class="lb-tnote">{t(sn["note"])}</p>' + grid([sn], "2026 to date")
          + f'<details class="lb-tdet"><summary>2026 games so far, by program</summary><div class="lb-tscroll"><table class="lb-tbl"><thead>{shd}</thead><tbody>{srows}</tbody></table></div></details></div>')
    return h + "</div>"


def body_html(case, md, data, teams=None):
    letters = iter("BCDEFGH")
    src = re.sub(r"^::: *part\n(.*?)\n:::$", lambda m: "LBPART" + B.t(m.group(1).strip()).replace(" ", " ") + "LBEND", md, flags=re.S | re.M)
    out = B.render_body({"format": "markdown"}, src)
    out = re.sub(r"<p>LBPART(.*?)LBEND</p>", lambda m: f'<p class="lb-part">{m.group(1).replace(chr(160), " ")}</p>', out)
    out = re.sub(r"<p>\[\[([a-z-]+)\]\]</p>", lambda m: exhibit_html(m.group(1), case, data, next(letters), teams), out)
    if "[[" in out:
        raise LabError("unknown [[marker]] in case.md")
    return out


def receipts_html(case):
    p, dl, me = case["plan"], case["data_lock"], case["methods"]
    plan_url = f"/lab/{case['number']}-{case['slug']}/plan/"
    rows = [("Verdict record", t(case["verdict_record"]))] if case.get("verdict_record") else []
    rows += [("Plan locked", f'{t(B.nice_date(p["locked"]))} · plan {t(plan_label(case))} · <a href="{plan_url}">read the plan, including what was explored first</a>'),
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
    rd = case["research_datasets"][0] if case["research_datasets"] else {"label": "", "label_short": ""}
    return {"case": {"number": case["number"], "url": f"/lab/{case['number']}-{case['slug']}/"},
            "persistence": data["persistence"], "league": data["league"],
            "range": {"coverage": f'{float(case["presentation"]["band_coverage"]):g}', "measure": case["presentation"]["measure_short"]},
            "research": {"label": rd["label"], "label_short": rd["label_short"], "name": rd.get("name", ""), "span": rd.get("span", ""),
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
    lead = exhibit_html("persistence", case, data, "A").replace('id="lb-carry-sec"', 'id="lb-carry-sec" style="margin:0"')
    body = body_html(case, md, data, teams)
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
    if case.get("type") == OI_TYPE:
        return oi_landing_page(case, data, teams, docket, tpl, asset_v, preview)
    num, url = case["number"], f"/lab/{case['number']}-{case['slug']}/"
    v = case["verdict"]
    rnote = research_note(case["research_datasets"][0]["label"]) if (any(r.get("includes_research") for r in data["persistence"]) and case["research_datasets"]) else ""
    # the team picker is the page's main action: inside the case cover, between the answer and the chart on phones
    team = ('<div class="lb-home-team" role="group" aria-labelledby="lb-home-h">'
            '<div class="lb-ht-q"><span class="lb-label">Start with your team</span><label id="lb-home-h" for="lb-home-pick">What about my team?</label></div>'
            f'<select id="lb-home-pick" class="lb-select lb-select-xl">{team_options(teams, "Pick your team")}</select>'
            '<div class="lb-ht-res" aria-live="polite"><b id="lb-home-ans">All 68 programs are in the case file.</b>'
            '<span id="lb-home-line">Pick one to see what happened for it and where that sits against its expected range.</span>'
            '<span id="lb-home-rn" class="lb-ht-rn" hidden><i aria-hidden="true"></i><span></span></span></div>'
            f'<a id="lb-home-link" class="lb-btn lb-hot" href="{url}">Open the case file →</a></div>')
    feat = (f'<section aria-label="Latest case file" class="lb-feat"><span class="lb-tab" style="align-self:flex-start">LAB {num} · LATEST CASE</span>'
            '<div class="lb-card-cover"><div class="lb-cc-text">'
            f'<span class="lb-label">{t(case["topic"])} · Hypothesis Test</span><h2>{t(case["title"])}</h2>'
            f'<div style="display:flex;align-items:center;gap:24px;flex-wrap:wrap">{stamp(v)}<p class="lb-cc-ans">{t(v["answer"])}</p></div>'
            f'<a class="lb-open" href="{url}">Read the case file →</a>'
            f'<span class="lb-mono" style="font-size:12px;color:var(--lb-muted-d)">v{t(case["version"])} · {t(case["data_lock"]["label"])}</span></div>'
            + team +
            '<div class="lb-cc-ex"><div class="lb-exhibit"><div class="lb-ex-head"><span>Exhibit A · Does it carry over?</span>' + ('<span class="lb-tagS">Sample data</span>' if case.get("sample") else "") + '</div><div id="lb-home-ex" style="padding:6px 8px 4px"></div>'
            '<div class="lb-ex-foot">Above 0 would mean big-favorite gaps repeat from season to season. ' + all_below(data["persistence"]) + '</div>' + rnote + '</div></div></div></section>')
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
        rows.append(f"<url><loc>{case_url(case)}</loc><lastmod>{lm}</lastmod></url>")
        if case.get("type") != OI_TYPE:
            rows.append(f"<url><loc>{case_url(case)}plan/</loc><lastmod>{lm}</lastmod></url>")
    return '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(rows) + "\n</urlset>\n"


def manifest(cases):
    out = []
    for case, _, _ in cases:
        out.append({"number": case["number"], "slug": case["slug"], "url": f"/lab/{case['number']}-{case['slug']}/", "title": case["title"],
                    "type": case["type"], "verdict": (case.get("verdict") or {}).get("kind"), "version": case["version"],
                    "published": case.get("published"), "updated": case.get("updated"), "data_cutoff": case["data_lock"]["cutoff"],
                    "plan": plan_label(case) if case.get("type") != OI_TYPE else None})
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
            return (f'<div class="top"><span class="tab">LAB {num}</span>{LOCK}</div><div class="q" style="font-size:84px">{t(case["title"])}</div>'
                    f'<div style="display:flex;align-items:center;gap:36px">{st}<div class="sent" style="font-size:27px">{t(v["answer"])}</div></div>'
                    f'<div class="ex" style="min-height:0"><div class="h">Exhibit A · does it carry over?</div><div data-chart="persistence" style="flex:1;min-height:0"></div>{rn}</div>'
                    f'<div class="foot"><p>{DEF}</p><b>dawgindex.com/lab/{num}</b></div>')
        return (f'<div class="top"><span class="tab">LAB {num}</span>{LOCK}</div><div class="row"><div class="l"><div class="q">{t(case["title"])}</div>'
                f'<div style="display:flex;align-items:center;gap:22px">{st}</div></div>'
                f'<div class="r"><div class="ex"><div class="h">Exhibit A · does it carry over?</div><div data-chart="persistence" data-size="m" style="flex:1;min-height:0"></div>{rn}</div></div></div>'
                f'<div class="band"><span>{t(case["verdict"].get("card_line") or v["answer"])}</span><b>dawgindex.com/lab/{num}</b></div>')
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
                f'<div class="ex"><div class="h"><span>{t(tm["name"])} vs. its expected range</span>{tag}</div><div data-chart="strip" data-team="{tm["slug"]}" data-size="xl"></div>{rn}</div>'
                f'<div class="foot"><span class="desc">What happened · not a verdict</span><b>{t(tm["short_url"])}</b></div>')
    return (f'<div class="top"><span class="tab">LAB {num} · YOUR TEAM</span>{LOCK}</div>'
            f'<div class="row"><div class="l"><div class="who">{logo}<div><div class="tn">{t(tm["name"])}</div><div class="qs">{t(q)}</div></div></div>'
            f'<div class="hl">{t(tm["answer"])}</div>{ss}</div>'
            f'<div class="r"><div class="ex"><div class="h"><span>{t(tm["name"])} vs. its expected range</span>{tag}</div><div data-chart="strip" data-team="{tm["slug"]}" data-size="xl"></div>{rn}</div></div></div>'
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
    tpl_hash = hashlib.sha256(read(os.path.join(HERE, "templates", "lab", "card.html"), "rb") + read(os.path.join(HERE, "templates", "lab", "lab.js"), "rb")
                              + read(os.path.join(HERE, "templates", "lab", "lab-oi.js"), "rb")).hexdigest()[:12]
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
    oi = read(os.path.join(tpl, "lab", "lab-oi.js"), "rb")
    return css, js, hashlib.sha256(css + js + oi).hexdigest()[:10]


def render_tree(repo, out_root, cases, docket, log, preview=False, cards=True):
    """Write /lab/ for these cases under out_root (the repo for build, a private folder for preview)."""
    tpl = os.path.join(repo, "_editorial", "templates")
    css, js, av = assets(tpl)
    lab = os.path.join(out_root, "lab")
    B.write_if_changed(os.path.join(lab, "lab.css"), css, log)
    B.write_if_changed(os.path.join(lab, "lab.js"), js, log)
    oi_js = read(os.path.join(tpl, "lab", "lab-oi.js"), "rb")
    B.write_if_changed(os.path.join(lab, "lab-oi.js"), oi_js, log)
    jobs = []
    for case, md, data, plan, teams in cases:
        d = os.path.join(lab, f"{case['number']}-{case['slug']}")
        if case.get("type") == OI_TYPE:
            num = case["number"]
            B.write_if_changed(os.path.join(d, "index.html"), oi_case_page(case, md, data, teams, tpl, av, preview), log)
            B.write_if_changed(os.path.join(d, "data.json"), json.dumps(oi_js_data(case, data, teams), ensure_ascii=False, indent=1) + "\n", log)
            B.write_if_changed(os.path.join(d, "explorer.json"), data["_explorer_raw"], log)
            B.write_if_changed(os.path.join(lab, num, "index.html"),
                               redirect_page(case, f"LAB {num}: {case['title']}", case["description"], case_url(case) + "og.png", f"DAWG Lab case {num}",
                                             f"/lab/{num}-{case['slug']}/", case_url(case), f"{SITE}/lab/{num}/", preview), log)
            if cards:
                look = "production" if preview == "production" else "sample"
                jobs.append((oi_card_page(case, data, teams, "card", tpl, look), os.path.join(d, "card.png"), "card", "case"))
                jobs.append((oi_card_page(case, data, teams, "og", tpl, look), os.path.join(d, "og.png"), "og", "case"))
            continue
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
        render_cards(jobs, repo, {"lab/lab.js": js, "lab/lab-oi.js": oi_js, "lab/lab.css": css}, log)


APPROVAL_KEYS = ("approved_by", "approved_at", "published", "approved_hash")


def fingerprint(case, md, data, plan):
    """What Matthew approved: the whole case (copy, team headlines, verdict, references), its data and its plan. Any edit
    after approval changes this, and build refuses until the case is re-approved."""
    c = {k: v for k, v in case.items() if k not in APPROVAL_KEYS}
    dd = {k: v for k, v in data.items() if k not in ("_explorer", "_explorer_raw")}
    blob = json.dumps(c, sort_keys=True, ensure_ascii=False) + "\0" + json.dumps(dd, sort_keys=True, ensure_ascii=False) + "\0" + md + "\0" + plan
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
            try:
                if case.get("type") == OI_TYPE:
                    teams = oi_teams(names, ids, site_teams)
                    oi_body_html(case, md, data)
                else:
                    teams = derive_teams(case, data, ids, names, site_teams)
                    errs += team_copy_errors(teams)
                    body_html(case, md, data, teams)
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
    if not errs and tmp.get("type") != OI_TYPE:
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
    if not errs and case.get("type") != OI_TYPE:
        errs = team_copy_errors(derive_teams(case, data, B.team_ids(repo), B.team_names(repo, site), site))
    if errs:
        raise LabError("not re-approved:\n  - " + "\n  - ".join(errs))
    case["approved_hash"] = fingerprint(case, md, data, plan)
    with open(os.path.join(d, "case.json"), "w") as f:
        f.write(json.dumps(case, ensure_ascii=False, indent=1) + "\n")
    print(f"re-approved: LAB {case['number']} by {by.strip()}; run build")



# ================================================================ Original Investigations
# An Original Investigation answers a question by exploring the data, without a pre-registered plan, so it carries no
# verdict stamp and no plan page. It must say how it was checked and how its scope came about. LAB 001's version
# ("halves") splits each team-season's schedule into a tougher and an easier half; its explorer data ships beside the page.
OI_TYPE = "original-investigation"
OI_LABEL = "DAWG Lab / Original Investigation / {num}"
OI_MARKERS = ("illusion", "reveal", "explorer")
# verdict language belongs to hypothesis tests; an investigation without a plan can't carry it
OI_FORBIDDEN = re.compile(r"doesn.t hold up|\binconclusive\b|myth busted|proven false|\bholds up\b|mixed evidence|\bverdict\b", re.I)


def oi_halves(es):
    """es: spreads in schedule order. Returns 't' / 'e' / 'x' per game: tougher half (smallest expected margin), easier
    half, or neither (the odd middle game, and every game tied at a halfway boundary). Mirrors the research script."""
    n = len(es); h = n // 2
    order = sorted(range(n), key=lambda i: es[i])          # stable: ties keep schedule order (they're excluded anyway)
    v = [es[i] for i in order]
    flag = ["x"] * n
    for k, i in enumerate(order):
        if k < h:
            flag[i] = "t"
        elif k >= n - h:
            flag[i] = "e"
    bad = set()
    if 0 < h < n and v[h - 1] == v[h]:
        bad.add(v[h - 1])
    if 0 <= n - h - 1 and n - h < n and v[n - h - 1] == v[n - h]:
        bad.add(v[n - h])
    return ["x" if es[i] in bad else flag[i] for i in range(n)]


def validate_oi(case, md, data, d, site_teams, mode):
    errs = []
    name = os.path.basename(d.rstrip("/"))
    m = CASE_DIR.match(name)
    req = ["number", "slug", "type", "status", "title", "topic", "dek", "description", "short_answer", "card_line", "version",
           "data_lock", "methods", "checks", "scope_change", "versions", "corrections", "research_datasets"]
    for k in req:
        if k not in case or case[k] in (None, ""):
            errs.append(f"missing {k}")
    if errs:
        return errs
    if m and (case["number"], case["slug"]) != (m.group(1), m.group(2)):
        errs.append(f"folder name must be {case['number']}-{case['slug']}")
    for k in ("verdict", "verdict_record", "plan"):
        if k in case:
            errs.append(f"an Original Investigation has no {k} (it wasn't planned in advance, so it carries no verdict stamp)")
    if len(case["description"]) > 200:
        errs.append("description over 200 characters")
    if len(case["card_line"]) > 90:
        errs.append("card_line (the link-preview line) is over 90 characters")
    for k in ("snapshot", "cutoff", "label"):
        if not case["data_lock"].get(k):
            errs.append(f"data_lock.{k} is required")
    for k in ("dawg", "case"):
        if not case["methods"].get(k):
            errs.append(f"methods.{k} is required")
    if "exploratory" not in case["checks"].lower() or "independent" not in case["checks"].lower():
        errs.append("checks must say the work was exploratory and how it was independently reproduced")
    if not case["versions"] or case["versions"][-1].get("version") != case["version"]:
        errs.append("versions must end with an entry for the current version")
    for vv in case["versions"]:
        for k in ("version", "date", "change"):
            if not vv.get(k):
                errs.append(f"every version entry needs {k}")
    for c in case["corrections"]:
        if not (c.get("date") and c.get("text")):
            errs.append("every correction needs a date and text")
    for kind in OI_MARKERS:
        if md.count(f"[[{kind}]]") != 1:
            errs.append(f"case.md must place [[{kind}]] exactly once")
    other = set(re.findall(r"\[\[([a-z-]+)\]\]", md)) - set(OI_MARKERS)
    if other:
        errs.append("case.md has unknown exhibit markers: " + ", ".join(sorted(other)))
    copy_all = " ".join(strings(case)) + " " + md
    mf = OI_FORBIDDEN.search(copy_all)
    if mf:
        errs.append(f"the copy says '{mf.group(0)}': an Original Investigation carries no verdict language")
    mr = RULED_OUT.search(copy_all)
    if mr:
        errs.append(f"the copy says '{mr.group(0)}': no size is published as ruled out")
    if TWO_POINT_OH.search(copy_all):
        errs.append("'2.0' appears in the copy (internal name; never public)")
    rds = case["research_datasets"]
    for rd in rds:
        for k in ("name", "span", "provenance", "label", "label_short"):
            if not rd.get(k):
                errs.append(f"research dataset needs {k}")
    if mode == "publish":
        if case.get("sample"):
            errs.append("this case is marked sample: sample data never publishes")
        if case["status"] != "published":
            errs.append("status is not 'published'")
        for k in ("approved_by", "approved_at", "published"):
            if not case.get(k):
                errs.append(f"missing {k}: a case is published only with Matthew's explicit approval on record")
        if PLACEHOLDER.search(copy_all):
            errs.append("unfilled [placeholder] in the copy: " + PLACEHOLDER.search(copy_all).group(0))
        if SAMPLE_WORDS.search(copy_all):
            errs.append("sample/illustrative wording in published copy: " + SAMPLE_WORDS.search(copy_all).group(0))
    errs += oi_data_errors(case, data, site_teams)
    return errs


def oi_data_errors(case, data, site_teams):
    """The exhibits and the explorer must agree with each other: every number is checked against the game rows."""
    errs = []
    if data.get("kind") != "halves":
        return ["data.json: kind must be 'halves'"]
    il, rv = data.get("illusion") or {}, data.get("reveal") or {}
    for k in ("team_seasons", "tougher", "easier", "gap", "ci", "spread_apart", "by_season"):
        if k not in il:
            errs.append(f"data.json illusion: missing {k}")
    for k in ("team_seasons", "spread", "spread_home_removed", "opponent"):
        if k not in rv:
            errs.append(f"data.json reveal: missing {k}")
    if errs:
        return errs
    for nm, blk in (("illusion", il), ("reveal.spread", rv["spread"]), ("reveal.spread_home_removed", rv["spread_home_removed"]), ("reveal.opponent", rv["opponent"])):
        if not all(k in blk for k in ("tougher", "easier", "gap", "ci")):
            errs.append(f"data.json {nm}: needs tougher, easier, gap and ci")
            continue
        if abs((blk["tougher"] - blk["easier"]) - blk["gap"]) > 0.011:
            errs.append(f"data.json {nm}: gap must equal tougher minus easier")
        if not (blk["ci"][0] <= blk["gap"] <= blk["ci"][1]):
            errs.append(f"data.json {nm}: the interval must contain the estimate")
    ex = data.get("_explorer")
    if not ex:
        return errs + ["explorer.json is missing"]
    if data.get("explorer_sha256") != data.get("_explorer_sha256"):
        errs.append("explorer.json changed after data.json was written (hash mismatch)")
    teams = ex.get("teams") or {}
    if set(teams) != set(site_teams):
        errs.append(f"explorer.json must cover all {len(site_teams)} programs (missing: {sorted(set(site_teams) - set(teams))[:5]}, unknown: {sorted(set(teams) - set(site_teams))[:5]})")
    opps = ex.get("opps") or []
    mn, mh, rthru = ex.get("min_games", 8), ex.get("min_half", 3), ex.get("research_through")
    if rthru and not case["research_datasets"]:
        errs.append("explorer.json has research seasons, so the case needs its research dataset label")
    full = []
    for slug, tm in teams.items():
        for season, ts in (tm.get("seasons") or {}).items():
            g = ts.get("g") or []
            if ts.get("n") != len(g):
                errs.append(f"explorer {slug} {season}: n doesn't match its games")
                continue
            if any(len(r) != 6 or not (0 <= r[1] < len(opps)) or r[4] not in (-1, 0, 1) for r in g):
                errs.append(f"explorer {slug} {season}: malformed game row")
                continue
            es, ys, hs = [r[2] for r in g], [r[3] for r in g], [r[5] for r in g]
            if len(g) >= mn:
                want = oi_halves(es)
                tt = [y for y, f in zip(ys, want) if f == "t"]; ee = [y for y, f in zip(ys, want) if f == "e"]
                ok = len(tt) >= mh and len(ee) >= mh
            else:
                want, ok = [""] * len(g), False
            if not ok:
                if "T" in ts or "gap" in ts or any(h for h in hs):
                    errs.append(f"explorer {slug} {season}: below the minimum, so no halves may be shown")
                continue
            if hs != want:
                errs.append(f"explorer {slug} {season}: halves don't follow the tie rule")
                continue
            ty = sum(tt) / len(tt); ey = sum(ee) / len(ee)
            te = sum(e for e, f in zip(es, want) if f == "t") / len(tt); ee_ = sum(e for e, f in zip(es, want) if f == "e") / len(ee)
            exp = {"T": [len(tt), round(te, 2), round(ty, 2)], "E": [len(ee), round(ee_, 2), round(ey, 2)], "gap": round(ty - ey, 2)}
            got = {"T": ts.get("T"), "E": ts.get("E"), "gap": ts.get("gap")}
            if any(abs(a_ - b_) > 0.011 for k in ("T", "E") for a_, b_ in zip(exp[k], got[k] or [9e9] * 3)) or got["gap"] is None or abs(exp["gap"] - got["gap"]) > 0.011:
                errs.append(f"explorer {slug} {season}: half summaries don't match its games")
                continue
            full.append((int(season), ty, ey, ty - ey))
    # Exhibit 1 is the average over exactly these team-seasons
    full_hist = [f for f in full if f[0] <= max(int(s) for s in il["by_season"])]
    if len(full_hist) != il["team_seasons"]:
        errs.append(f"Exhibit 1 counts {il['team_seasons']} team-seasons but the explorer has {len(full_hist)} with halves")
    elif full_hist:
        n = len(full_hist)
        for k, i in (("tougher", 1), ("easier", 2), ("gap", 3)):
            if abs(sum(f[i] for f in full_hist) / n - il[k]) > 0.006:
                errs.append(f"Exhibit 1 {k} {il[k]} doesn't match the explorer's team-seasons ({sum(f[i] for f in full_hist) / n:.3f})")
        for season, v in il["by_season"].items():
            ss = [f[3] for f in full_hist if f[0] == int(season)]
            if not ss or abs(sum(ss) / len(ss) - v) > 0.006:
                errs.append(f"Exhibit 1 season {season} doesn't match the explorer")
    return errs


def oi_teams(names, ids, site_teams):
    return {s: {"name": names.get(s, s), "id": ids.get(s), "slug": s} for s in sorted(site_teams, key=lambda x: names.get(x, x))}


def oi_explorer_url(case, data):
    return f"/lab/{case['number']}-{case['slug']}/explorer.json?v={data['_explorer_sha256'][7:17]}"


def oi_exhibit_html(kind, case, data, num):
    rd = case["research_datasets"][0] if case["research_datasets"] else None
    rnote = research_note(rd["label"]) if rd else ""
    tag = '<span class="lb-tagS">Sample data</span>' if case.get("sample") else ""
    if kind == "illusion":
        il = data["illusion"]
        yrs = sorted(int(y) for y in il["by_season"])
        return (f'<figure class="lb-exhibit lb-oi-ex" id="lb-ex-illusion" aria-label="Exhibit {num}"><div class="lb-ex-head"><span>Exhibit {num} · Sorted by the spread</span>{tag}</div>'
                '<p class="lb-ex-title">Teams look better against the tougher half of their schedule</p>'
                '<div id="lb-illusion" class="lb-oi-chart"></div>'
                f'<p class="lb-ex-sub">The gap, season by season ({yrs[0]}–{yrs[-1]})</p><div id="lb-seasons" class="lb-oi-chart"></div>'
                f'<figcaption class="lb-ex-foot">{il["team_seasons"]} team-seasons with 8 or more games, {yrs[0]}–{yrs[-1]}. Each schedule is split in half by that game’s point spread; '
                f'the halves average {il["spread_apart"]:.0f} points of spread apart. Bars show the average DAWG grade in each half. {DEF}</figcaption>{rnote}</figure>')
    if kind == "reveal":
        rv = data["reveal"]
        return (f'<figure class="lb-exhibit lb-oi-ex lb-oi-reveal" id="lb-ex-reveal" aria-label="Exhibit {num}"><div class="lb-ex-head"><span>Exhibit {num} · Same games, two ways to rank opponents</span>{tag}</div>'
                '<p class="lb-ex-title">Sort by the opponent instead of the spread, and the gap disappears</p>'
                '<dl class="lb-oi-key"><div><dt>That game’s spread</dt><dd>Vegas’s prediction for this one game</dd></div>'
                '<div><dt>Opponent’s strength before kickoff</dt><dd>How good the opponent had looked in its earlier games, home field taken out</dd></div></dl>'
                '<div id="lb-reveal" class="lb-oi-chart"></div>'
                f'<figcaption class="lb-ex-foot">The same {rv["team_seasons"]} team-seasons and the same games in both rows: games against Power 4 opponents once both teams had played two games. '
                f'Each line shows the range the average would likely fall in (95%). With home field taken out of the spread, the top row is still {fmt(rv["spread_home_removed"]["gap"])}. '
                'What we see: the gap follows the spread, not the opponent. Why: not established.</figcaption>' + rnote + '</figure>')
    if kind == "explorer":
        return (f'<section class="lb-exhibit lb-oi-ex lb-oi-explorer" id="your-team" aria-label="Exhibit {num}: your team"><div class="lb-ex-head"><span>Exhibit {num} · Your team, season by season</span>{tag}</div>'
                '<div class="lb-xp-pick"><label><span class="lb-label">Team</span><select id="lb-xp-team" class="lb-select"><option value="">Pick a team</option></select></label>'
                '<label><span class="lb-label">Season</span><select id="lb-xp-season" class="lb-select" disabled></select></label></div>'
                '<div id="lb-xp-lead" class="lb-xp-lead" aria-live="polite"><p class="lb-xp-empty">Pick a team to see its tougher and easier halves, season by season.</p></div>'
                '<div id="lb-xp-chart" class="lb-oi-chart" hidden></div><p id="lb-xp-tap" class="lb-xp-tap" aria-live="polite" hidden></p>'
                '<details id="lb-xp-list" class="lb-xp-list" hidden><summary>Show every game this season ▾</summary><div class="lb-tscroll"><table class="lb-tbl"><thead><tr><th scope="col" class="lb-tl">Game</th><th scope="col">Spread</th><th scope="col">DAWG</th><th scope="col">Half</th></tr></thead><tbody id="lb-xp-rows"></tbody></table></div></details>'
                f'<p class="lb-ex-foot">Spreads are from the team’s side. Research seasons (2014–18) use research grades, not official DAWG grades. {DEF}</p></section>')
    raise LabError(f"unknown exhibit [[{kind}]]")


def oi_body_html(case, md, data):
    nums = iter(range(1, 10))
    out = B.render_body({"format": "markdown"}, md)
    out = re.sub(r"<p>\[\[([a-z-]+)\]\]</p>", lambda m: oi_exhibit_html(m.group(1), case, data, next(nums)), out)
    if "[[" in out:
        raise LabError("unknown [[marker]] in case.md")
    return out


def oi_receipts_html(case):
    dl, me = case["data_lock"], case["methods"]
    rows = [("How it was checked", t(case["checks"])),
            ("How this case changed", t(case["scope_change"])),
            ("Data", f'{t(dl["label"])} · snapshot <span class="lb-mono" style="font-size:13px">{t(dl["snapshot"][:19])}</span>'),
            ("Method", f'DAWG {t(me["dawg"])} · case method v{t(me["case"])}')]
    for rd in case["research_datasets"]:
        rows.append(("Research-only data", f'<b>{t(rd["name"])}</b>: {t(rd["provenance"])} <span class="lb-note" style="display:block;margin:2px 0 0">{t(rd["label"])}</span>'))
    dl_html = "".join(f"<dt>{t(k)}</dt><dd>{v}</dd>" for k, v in rows)
    vers = "".join(f'<li>v{t(v["version"])} · {t(B.nice_date(v["date"]))} · {t(v["change"])}</li>' for v in reversed(case["versions"]))
    corr = "".join(f'<div class="lb-corr"><b>Correction, {t(B.nice_date(c["date"]))}:</b> {t(c["text"])}</div>' for c in case["corrections"])
    return ('<h2 id="lb-receipts">Receipts</h2>' + (corr or "") + f'<dl class="lb-receipts">{dl_html}</dl>'
            '<h2 style="font-size:28px">Version history</h2>' + f'<ul class="lb-versions">{vers}</ul>'
            + ('<p class="lb-note">No corrections. Any correction is dated here and on <a href="/lab/corrections/">the corrections page</a>.</p>' if not corr else ""))


def oi_js_data(case, data, teams):
    rd = case["research_datasets"][0] if case["research_datasets"] else {"label": "", "label_short": ""}
    return {"case": {"number": case["number"], "url": f"/lab/{case['number']}-{case['slug']}/", "type": OI_TYPE},
            "illusion": data["illusion"], "reveal": data["reveal"], "variation": data.get("variation"),
            "explorer": oi_explorer_url(case, data), "research": {"label": rd["label"], "label_short": rd.get("label_short", ""), "through": 2018 if case["research_datasets"] else None},
            "teams": {s: tm["name"] for s, tm in teams.items()}}


def oi_cover(case, h1=True):
    num = case["number"]
    return (f'<section class="lb-cover" aria-label="Case cover"><div class="lb-cover-in">'
            f'<nav class="lb-crumb" aria-label="Breadcrumb"><a href="/lab/">DAWG Lab</a> / Original Investigation / {num}</nav>'
            f'<div class="lb-meta"><span class="lb-tab">LAB {num}</span><span class="lb-mono">Original Investigation · v{t(case["version"])} · {t(case["data_lock"]["label"])}</span></div>'
            f'<h1>{t(case["title"])}</h1><p class="lb-dek">{t(case["dek"])}</p>'
            f'<div class="lb-oi-answer"><span class="lb-label">The short version</span><p>{t(case["short_answer"])}</p>'
            '<a class="lb-open" href="#your-team">Find your team ↓</a></div>'
            "</div></section>")


def oi_case_page(case, md, data, teams, tpl, asset_v, preview=False):
    url = case_url(case)
    num = case["number"]
    body = oi_body_html(case, md, data)
    rail = ('<div class="lb-sec" style="font-size:15px"><span class="lb-label">In this case</span><a href="#lb-ex-illusion">Exhibit 1 · Sorted by the spread</a>'
            '<a href="#lb-ex-reveal">Exhibit 2 · Two ways to rank opponents</a><a href="#your-team">Exhibit 3 · Your team</a><a href="#lb-receipts">Receipts</a></div>'
            '<div class="lb-sec" style="font-size:15px"><span class="lb-label">Related</span><a href="/lab/">All Lab case files</a><a href="/lab/corrections/">Corrections</a></div>')
    content = (oi_cover(case) + '<main class="lb-main lb-oi">'
               '<div class="lb-cols"><article class="lb-article"><div class="body">' + body + oi_receipts_html(case) + "</div></article>"
               f'<aside class="lb-rail" aria-label="In this case">{rail}</aside></div></main>')
    data_js = oi_js_data(case, data, teams)
    ld = {"@context": "https://schema.org", "@type": "Article", "headline": case["title"], "datePublished": case.get("published") or case["versions"][0]["date"],
          "dateModified": case.get("updated") or case["versions"][-1]["date"], "author": {"@type": "Organization", "name": "DAWG Index"},
          "publisher": {"@type": "Organization", "name": "DAWG Index", "url": SITE}, "image": url + "og.png", "mainEntityOfPage": url}
    rep = head_rep(tpl, f"LAB {num}: {case['title']} · DAWG Lab", case["description"], url, url, f"LAB {num}: {case['title']}",
                   case.get("social_description") or case["description"], url + "og.png", f"DAWG Lab case {num}: {case['title']}", preview=preview, jsonld=ld)
    rep.update({"ASSET_V": asset_v, "LAB_CURRENT": ' aria-current="page"', "BODY_ATTR": "", "BANNERS": banners(case, preview), "CONTENT": content,
                "SCRIPTS": f'<script id="lab-data" type="application/json">{jdump(data_js)}</script>\n<script src="/lab/lab-oi.js?v={asset_v}"></script>'})
    return page(tpl, rep)


def oi_feat(case, data, teams):
    num, url = case["number"], f"/lab/{case['number']}-{case['slug']}/"
    team = ('<div class="lb-home-team" role="group" aria-labelledby="lb-home-h">'
            '<div class="lb-ht-q"><span class="lb-label">Start with your team</span><label id="lb-home-h" for="lb-home-pick">What about my team?</label></div>'
            f'<select id="lb-home-pick" class="lb-select lb-select-xl">{team_options(teams, "Pick your team")}</select>'
            '<div class="lb-ht-res" aria-live="polite"><b id="lb-home-ans">Every Power 4 team-season since 2014 is in the case file.</b>'
            '<span id="lb-home-line">Pick your team to see its tougher and easier halves, season by season.</span></div>'
            f'<a id="lb-home-link" class="lb-btn lb-hot" href="{url}#your-team">Open the case file →</a></div>')
    return (f'<section aria-label="Latest case file" class="lb-feat"><span class="lb-tab" style="align-self:flex-start">LAB {num} · LATEST CASE</span>'
            '<div class="lb-card-cover"><div class="lb-cc-text">'
            f'<span class="lb-label">Original Investigation · {t(case["topic"])}</span><h2>{t(case["title"])}</h2>'
            f'<p class="lb-cc-ans">{t(case["dek"])}</p><p class="lb-cc-ans" style="color:var(--lb-cream)">{t(case["short_answer"])}</p>'
            f'<a class="lb-open" href="{url}">Read the investigation →</a>'
            f'<span class="lb-mono" style="font-size:12px;color:var(--lb-muted-d)">v{t(case["version"])} · {t(case["data_lock"]["label"])}</span></div>'
            + team +
            '<div class="lb-cc-ex"><div class="lb-exhibit"><div class="lb-ex-head"><span>Exhibit 2 · Two ways to rank opponents</span></div>'
            '<div id="lb-home-ex" class="lb-oi-chart" style="padding:6px 8px 4px"></div>'
            '<div class="lb-ex-foot">Tougher half minus easier half of each schedule, in DAWG points. Same games in both rows.</div></div></div></div></section>')


def oi_card_inner(case, size):
    num = case["number"]
    rd = case["research_datasets"][0] if case["research_datasets"] else None
    rn = f'<div class="rn"><i></i>{t(rd["label"])}</div>' if rd else ""
    if size == "card":
        return (f'<div class="top"><span class="tab">LAB {num} · ORIGINAL INVESTIGATION</span>{LOCK}</div><div class="q" style="font-size:88px">{t(case["title"])}</div>'
                f'<div class="sent" style="font-size:29px">{t(case["dek"])}</div>'
                '<div class="ex" style="min-height:0"><div class="h">Exhibit 2 · Same games, two ways to rank opponents</div><div data-chart="reveal" style="flex:1;min-height:0"></div>' + rn + '</div>'
                f'<div class="foot"><p>{DEF}</p><b>dawgindex.com/lab/{num}</b></div>')
    return (f'<div class="top"><span class="tab">LAB {num} · ORIGINAL INVESTIGATION</span>{LOCK}</div><div class="row"><div class="l"><div class="q">{t(case["title"])}</div>'
            f'<div class="sent">{t(case["dek"])}</div></div>'
            '<div class="r"><div class="ex"><div class="h">Same games, two ways to rank opponents</div><div data-chart="reveal" data-size="m" style="flex:1;min-height:0"></div></div></div></div>'
            f'<div class="band"><span>{t(case["card_line"])}</span><b>dawgindex.com/lab/{num}</b></div>')


def oi_card_page(case, data, teams, size, tpl, look="sample"):
    pg = read(os.path.join(tpl, "lab", "card.html")).replace('<script src="/lab/lab.js"></script>', '<script src="/lab/lab-oi.js"></script>')
    sample = '<span class="sample">SAMPLE</span>' if (case.get("sample") and look != "production") else ""
    for k, v in {"{{SIZE}}": size, "{{SAMPLE}}": sample, "{{INNER}}": oi_card_inner(case, size), "{{DATA}}": jdump(oi_js_data(case, data, teams))}.items():
        pg = pg.replace(k, v)
    return pg


def oi_landing_page(case, data, teams, docket, tpl, asset_v, preview=False):
    url = f"/lab/{case['number']}-{case['slug']}/"
    feat = oi_feat(case, data, teams)
    links = ('<section class="lb-links"><a href="/#method">How DAWG works</a><a href="/lab/corrections/">Corrections</a>'
             '<span>Got a theory about your team? Reply to @dawgindex with <b>#AskTheLab</b>.</span></section>')
    head = ('<section class="lb-home-head"><div class="lb-lockup"><span class="lb-labtag">LAB</span><h1>Every fan base has a theory. We test them.</h1></div>'
            '<p>College football arguments, checked against the data.</p></section>')
    content = f'<main class="lb-main lb-home" style="padding-top:0">{head}{feat}{links}<p class="lb-note" style="margin-top:20px">{DEF}</p></main>'
    rep = head_rep(tpl, "The DAWG Lab · DAWG Index", "College football arguments, checked against the data.", SITE + "/lab/", SITE + "/lab/",
                   "The DAWG Lab: every fan base has a theory. We test them.", "College football arguments, checked against the data.",
                   SITE + url + "og.png", "The DAWG Lab", og_type="website", preview=preview)
    rep.update({"ASSET_V": asset_v, "LAB_CURRENT": ' aria-current="page"', "BODY_ATTR": "", "BANNERS": banners(case, preview), "CONTENT": content,
                "SCRIPTS": f'<script id="lab-data" type="application/json">{jdump(oi_js_data(case, data, teams))}</script>\n<script src="/lab/lab-oi.js?v={asset_v}"></script>'})
    return page(tpl, rep)

# ---------------------------------------------------------------- a clearly marked SAMPLE case for building the pages
def sample(repo, out_root):
    """Writes 001-playing-down with SAMPLE numbers (random, seeded) for all 68 programs. It carries sample: true, so it can
    never be approved or built into the site. Real copy and data come from the research session once its plan is locked."""
    rnd = random.Random(1001)
    site = sorted(B.team_slugs(repo))
    d = os.path.join(out_root, "001-playing-down")
    os.makedirs(d, exist_ok=True)
    below = {"kansas": (6, 3), "purdue": (7, 3), "georgia-tech": (5, 2)}
    labels = ["14+ favorite", "3.5–13.5 favorite", "Within 3", "3.5+ underdog"]
    teams = {}
    for s in site:
        if s in below:
            hf, es = below[s]
        else:
            hf, es = rnd.randint(9, 40), rnd.randint(3, 11)
        n_mf, n_ev, n_dog = rnd.randint(20, 50), rnd.randint(12, 35), rnd.randint(20, 70)
        down, dog_avg = round(rnd.gauss(0, 3), 6), round(rnd.gauss(0, 1.5), 6)
        share = n_dog / (n_mf + n_ev + n_dog)
        up = share * dog_avg
        raw = down - up
        rg = rnd.randint(30, 60)
        tm = {"hf_games": hf, "other_games": n_mf + n_ev + n_dog, "seasons": 13, "eligible_seasons": es, "raw": raw, "down": down, "up": up,
              "groups": [{"label": labels[0], "avg": round(rnd.gauss(0, 2), 3), "n": hf}, {"label": labels[1], "avg": round(rnd.gauss(0, 1.5), 3), "n": n_mf},
                         {"label": labels[2], "avg": round(rnd.gauss(0, 1.5), 3), "n": n_ev}, {"label": labels[3], "avg": round(rnd.gauss(0, 1.5), 3), "n": n_dog}],
              "official": {"hf_games": max(0, hf - 4), "other_games": n_mf + n_ev + n_dog - 25, "raw": round(raw + rnd.gauss(0, 1), 3)},
              "research_games": rg, "research_hf_games": min(hf, 4)}
        if hf >= 8 and es >= 3:
            half = 1.96 * 12.5 / math.sqrt(hf)
            tm.update(range_lo=round(-half + rnd.gauss(0, 0.2), 3), range_hi=round(half + rnd.gauss(0, 0.2), 3))
            tm["outside"] = tm["raw"] < tm["range_lo"] or tm["raw"] > tm["range_hi"]
        teams[s] = tm
    rows = [("c", "All seasons, 2014–26 (the plan’s main test)", True, True), ("a", "2019–26 (explored first)", False, False),
            ("b", "2014–18 (held out, research grades)", False, True), ("p4", "Vs. Power 4 only", False, True), ("no1416", "Without 2014–16", False, False)]
    persistence = [{"id": i, "label": l, "primary": pr, "includes_research": res, "T": round(rnd.gauss(-1, 2), 3), "SE": round(rnd.uniform(1, 3.5), 3),
                    "pairs": rnd.randint(300, 2800), "programs": rnd.randint(40, 68), "card": i in ("c", "a", "b")} for i, l, pr, res in rows]
    data = {"sample": True,
            "league": {"groups": [{"label": "14+ favorite", "avg": -0.1, "n": 2700}, {"label": "3.5–13.5 favorite", "avg": 0.1, "n": 2500},
                                  {"label": "Within 3", "avg": 0.1, "n": 1700}, {"label": "3.5+ underdog", "avg": 0.0, "n": 3300}]},
            "persistence": persistence, "teams": teams}
    case = {"number": "001", "slug": "playing-down", "type": "hypothesis-test", "status": "draft", "sample": True,
            "title": "Does your team play down to its competition?", "topic": "Favorites & underdogs",
            "dek": "Every fan base swears its team sleepwalks against weak opponents. We checked whether it carries over, program by program.",
            "description": "Every fan base swears its team plays down to weak opponents. The DAWG Lab checked all 68 programs, season after season.",
            "verdict": {"kind": "inconclusive", "subtitle": "Sample · reason from the plan", "answer": "Sample answer. The published case states the verdict in one plain sentence here.",
                        "card_line": "Sample line for the link preview"},
            "verdict_record": "Sample: the pre-registered rule's verdict and any later editorial decision are recorded here.",
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
                             "team_min": {"hf_games": 8, "seasons": 3}, "band_coverage": 95,
                             "team_headlines": {"within": "Inside the expected range", "outside": "Outside the expected range", "below": "Too few games to compare", "none": "No qualifying games"},
                             "team_min_text": "8 games as a 14+ point favorite and 3 eligible seasons"}}
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

Sample text. The published case says what the carryover estimates show and what they can't tell apart.

## Every program

[[programs]]

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
