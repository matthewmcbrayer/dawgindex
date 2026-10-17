#!/usr/bin/env python3
"""Demonstrates the Lab's publishing safeguards end to end, on a throwaway copy of the repo.

Each scenario puts an approved case into _editorial/lab/ (or tries to approve one), runs the real `lab.py build`, and
records whether it was refused, why, and whether anything was written to the site. The last scenario is a valid approved
case: it must build, and its research-only values must carry their label and provenance everywhere they appear.

The fixtures are the SAMPLE case with its sample markings swapped for test text. Their numbers are random, not research,
and they only ever exist inside the throwaway copy.

  python3 _editorial/lab_safeguards.py [REPORT.md]
"""
import copy, html, json, os, re, shutil, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True
import build as B
import lab as L
from test_lab import copy_repo, make_fixture, run, rd, wj


def site_tree(root):
    out = {}
    for d, dirs, fs in os.walk(root):
        rel = os.path.relpath(d, root)
        if rel.startswith((".git", "_editorial")) or "__pycache__" in rel:
            continue
        for f in fs:
            p = os.path.join(d, f)
            st = os.stat(p)
            out[os.path.relpath(p, root)] = (st.st_size, st.st_mtime_ns)
    return out


def first_reason(out):
    lines = [l.strip()[2:] if l.strip().startswith("- ") else l.strip() for l in out.splitlines()]
    lines = [l for l in lines if l and not l.startswith(("ERROR: build stopped", "ERROR: not approved"))]
    return lines[0].replace("ERROR: ", "") if lines else out.strip()[:200]


def main():
    report_path = sys.argv[1] if len(sys.argv) > 1 else None
    r = copy_repo()
    src = os.path.join(r, "_editorial", "lab")
    fx_root = tempfile.mkdtemp(prefix="labfx-")
    draft = make_fixture(fx_root)

    # the valid approved case every invalid scenario starts from
    code, out = run(r, "approve", draft, "--by", "Test Approver")
    assert code == 0, out
    base = os.path.join(tempfile.mkdtemp(prefix="labbase-"), "001-playing-down")
    shutil.move(os.path.join(src, "001-playing-down"), base)

    rows = []

    def scenario(name, mutate, expect):
        shutil.rmtree(src, ignore_errors=True); os.makedirs(src)
        d = os.path.join(src, "001-playing-down")
        shutil.copytree(base, d)
        c, data = json.loads(rd(os.path.join(d, "case.json"))), json.loads(rd(os.path.join(d, "data.json")))
        md, plan = rd(os.path.join(d, "case.md")), rd(os.path.join(d, "plan.md"))
        res = mutate(c, data, md, plan)
        if isinstance(res, tuple) and len(res) == 4:
            c, data, md, plan = res
        wj(os.path.join(d, "case.json"), c); wj(os.path.join(d, "data.json"), data)
        open(os.path.join(d, "case.md"), "w").write(md); open(os.path.join(d, "plan.md"), "w").write(plan)
        before = site_tree(r)
        code, out = run(r, "build")
        wrote = site_tree(r) != before
        ok = code != 0 and not wrote and expect.lower() in out.lower()
        rows.append((name, "refused" if code != 0 else "BUILT", "nothing" if not wrote else "FILES WRITTEN", first_reason(out) if code else "", ok))

    def team(data, slug="baylor"): return data["teams"][slug]

    S = scenario
    S("Case still marked sample", lambda c, d, m, p: c.update(sample=True), "marked sample")
    S("Sample wording left in the copy", lambda c, d, m, p: (c, d, m + "\nSample text.\n", p), "sample/illustrative")
    S("'Illustrative' wording in the copy", lambda c, d, m, p: (c, d, m + "\nAn illustrative example.\n", p), "sample/illustrative")
    S("Unfilled [placeholder]", lambda c, d, m, p: (c, d, m + "\nThe gap was [X] points.\n", p), "placeholder")
    S("No approval on record", lambda c, d, m, p: c.pop("approved_by"), "approved_by")
    S("Status still draft", lambda c, d, m, p: c.update(status="draft"), "status")
    S("Research-plan version missing", lambda c, d, m, p: c["plan"].pop("version"), "plan.version")
    S("Research plan not published with the case", lambda c, d, m, p: (c, d, m, " \n"), "plan.md is empty")
    S("Data cutoff missing", lambda c, d, m, p: c["data_lock"].pop("cutoff"), "data_lock.cutoff")
    S("Method version missing", lambda c, d, m, p: c["methods"].update(dawg=""), "methods.dawg")
    S("Version history out of step", lambda c, d, m, p: c["versions"][-1].update(version="0.9"), "versions must end")
    S("Correction without its text", lambda c, d, m, p: c.update(corrections=[{"date": "2026-10-20"}]), "correction")
    S("Research seasons with no research dataset", lambda c, d, m, p: c.update(research_datasets=[]), "research-only seasons")
    S("Research dataset without provenance", lambda c, d, m, p: c["research_datasets"][0].update(provenance=""), "provenance")
    S("Research dataset without its public label", lambda c, d, m, p: c["research_datasets"][0].update(label=""), "label")
    S("Research dataset without its span", lambda c, d, m, p: c["research_datasets"][0].pop("span"), "span")
    S("Research-span season not marked research", lambda c, d, m, p: [r.update(research=False) for r in team(d)["season_rows"] if r["season"] <= 2018] and None, "isn't marked research")
    S("Season marked research outside the span", lambda c, d, m, p: team(d)["season_rows"][-1].update(research=True), "outside the research dataset")
    S("Season rows don't add up to the games", lambda c, d, m, p: team(d)["season_rows"][0].update(n=team(d)["season_rows"][0]["n"] + 1), "add up")
    S("Team row without a sample size", lambda c, d, m, p: team(d)["groups"][0].pop("n"), "sample size")
    S("Team finding without its criteria", lambda c, d, m, p: team(d).update(finding={"text": "Baylor plays down."}), "team finding needs")
    S("Habit language in team copy", lambda c, d, m, p: c["presentation"].update(measure_short="as a favorite, which it always is"), "confirmed trait")
    S("Luck-range coverage missing", lambda c, d, m, p: c["presentation"].pop("band_coverage"), "band_coverage")
    S("Unknown team slug", lambda c, d, m, p: d["teams"].update({"not-a-team": team(d)}), "unknown team slug")
    S("Two cuts marked as the plan's choice", lambda c, d, m, p: [x.update(plan=True) for x in d["cuts"]] and None, "exactly one")
    S("'2.0' in the copy", lambda c, d, m, p: (c, d, m + "\nDAWG 2.0 says so.\n", p), "'2.0'")
    S("Plan version '2.0' with no public label", lambda c, d, m, p: c["plan"].pop("label"), "plan.label")
    S("Original Investigation (not built in v0)", lambda c, d, m, p: c.update(type="original-investigation"), "original investigation")
    S("Unknown [[marker]] in the article", lambda c, d, m, p: (c, d, m + "\n[[funnel]]\n", p), "[[funnel]]")
    S("Verdict without its plan-written subtitle", lambda c, d, m, p: c["verdict"].update(subtitle=""), "verdict.subtitle")
    S("Team headlines missing for a state", lambda c, d, m, p: c["presentation"]["team_headlines"].pop("below"), "team_headlines")
    S("Team headline claims a habit", lambda c, d, m, p: c["presentation"]["team_headlines"].update(outside="{team} plays down"), "confirmed trait")
    S("Team headline too long for a share card", lambda c, d, m, p: c["presentation"]["team_headlines"].update(within="{team} sits comfortably inside the luck range"), "share cards fit")
    S("Headline edited after approval (otherwise valid)", lambda c, d, m, p: c["presentation"]["team_headlines"].update(within="Inside the luck range"), "edited after approval")
    S("Data edited after approval (otherwise valid)", lambda c, d, m, p: d["teams"]["baylor"].update(raw=d["teams"]["baylor"]["raw"] + 0.1), "edited after approval")

    # duplicate case number
    shutil.rmtree(src); os.makedirs(src)
    shutil.copytree(base, os.path.join(src, "001-playing-down")); shutil.copytree(base, os.path.join(src, "001-playing-again"))
    cc = json.loads(rd(os.path.join(src, "001-playing-again", "case.json"))); cc["slug"] = "playing-again"; wj(os.path.join(src, "001-playing-again", "case.json"), cc)
    before = site_tree(r); code, out = run(r, "build")
    rows.append(("Two cases with the same number", "refused" if code else "BUILT", "nothing" if site_tree(r) == before else "FILES WRITTEN", first_reason(out) if code else "", code != 0 and "duplicate" in out))

    # approve path
    sd = L.sample(REPO, tempfile.mkdtemp(prefix="labsample-"))
    shutil.rmtree(src); os.makedirs(src)
    code, out = run(r, "approve", sd, "--by", "Test")
    rows.append(("Approving the SAMPLE case", "refused" if code else "APPROVED", "nothing" if not os.listdir(src) else "FILES WRITTEN", first_reason(out) if code else "", code != 0 and not os.listdir(src)))
    code, out = run(r, "approve", draft)
    rows.append(("Approving without a name", "refused" if code else "APPROVED", "nothing" if not os.listdir(src) else "FILES WRITTEN", first_reason(out) if code else "", code != 0 and not os.listdir(src)))
    code, out = run(r, "build")
    rows.append(("Build with no approved case (no empty Lab)", "nothing to build" if code == 0 else "error", "nothing" if not os.path.exists(os.path.join(r, "lab")) else "FILES WRITTEN",
                 out.strip().splitlines()[-1] if out.strip() else "", code == 0 and not os.path.exists(os.path.join(r, "lab"))))

    # ---- the valid case
    shutil.copytree(base, os.path.join(src, "001-playing-down"))
    code, out = run(r, "build")
    lab = os.path.join(r, "lab"); case_d = os.path.join(lab, "001-playing-down")
    n_files = sum(len(f) for _, _, f in os.walk(lab)) if os.path.isdir(lab) else 0
    rows.append(("Valid approved case", "BUILT" if code == 0 else "refused", f"{n_files} files under lab/" if code == 0 else "nothing", "" if code == 0 else first_reason(out), code == 0 and n_files > 200))

    # published-site safeguards on top of the valid build
    live = os.path.join(src, "001-playing-down"); moved = os.path.join(src, "001-down")
    os.rename(live, moved); cc = json.loads(rd(os.path.join(moved, "case.json"))); cc["slug"] = "down"; wj(os.path.join(moved, "case.json"), cc)
    before = site_tree(r); code, out = run(r, "build")
    rows.append(("Changing a published case's slug", "refused" if code else "BUILT", "nothing" if site_tree(r) == before else "FILES WRITTEN", first_reason(out) if code else "", code != 0 and site_tree(r) == before))
    shutil.rmtree(moved)
    before = site_tree(r); code, out = run(r, "build")
    rows.append(("Removing a published case's source", "refused" if code else "BUILT", "nothing (page stays live)" if site_tree(r) == before else "FILES WRITTEN", first_reason(out) if code else "",
                 code != 0 and os.path.isfile(os.path.join(case_d, "index.html"))))
    shutil.copytree(base, live)

    # ---- research-only values: label and provenance everywhere they appear, in the valid build
    c = json.loads(rd(os.path.join(live, "case.json"))); data = json.loads(rd(os.path.join(live, "data.json")))
    rdset = c["research_datasets"][0]
    teams = L.derive_teams(c, data, B.team_ids(REPO), B.team_names(REPO, B.team_slugs(REPO)), B.team_slugs(REPO))
    res_teams = [s for s, tm in teams.items() if tm["has_research"]]
    page = rd(os.path.join(case_d, "index.html")); home = rd(os.path.join(lab, "index.html"))
    pub = json.loads(rd(os.path.join(case_d, "data.json")))
    checks = []
    def chk(where, ok, detail=""): checks.append((where, ok, detail))
    chk("Article, Exhibit A: research label under the chart", rdset["label"] in page.split('id="lb-carry-sec"', 1)[1].split('<div class="lb-cols">', 1)[0])
    chk("Article, receipts: research dataset named with its provenance", f"<b>{html.escape(rdset['name'], quote=False)}</b>: {html.escape(rdset['provenance'], quote=False)}" in page)
    chk("Article, receipts anchor the panel links to", 'id="lb-receipts"' in page)
    chk("Lab homepage, Exhibit A: research label", rdset["label"] in home)
    chk("Published data.json: label, span and provenance travel with the numbers",
        all(pub["research"].get(k) == rdset[k] for k in ("label", "span", "provenance")))
    chk("Published data.json: every 2014–2018 season row is flagged research",
        all(r["research"] == (2014 <= r["season"] <= 2018) for tm in pub["teams"].values() for r in tm.get("season_rows", [])))
    bad = []
    for s in res_teams:
        tm = teams[s]
        stub = rd(os.path.join(lab, "001", s, "index.html"))
        if html.escape(tm["research_text"], quote=False).replace('"', "&quot;") not in stub: bad.append(f"{s}: link preview")
        if tm["card"]:
            for size in ("card", "og"):
                if tm["card_research"] not in html.unescape(L.card_inner(c, tm, size)): bad.append(f"{s}: {size}")
            if B.png_text(os.path.join(case_d, "cards", s + ".png"), "dawg-lab-team") != s: bad.append(f"{s}: card image")
        if not re.match(r"^\d+ of these \d+ games are from 2014–2018 and use research grades", tm["research_text"]): bad.append(f"{s}: count")
        if tm["research_games"] != sum(r["n"] for r in tm["season_rows"] if r["research"]): bad.append(f"{s}: research game count")
    chk(f"Team link previews, share cards and preview images for all {len(res_teams)} programs with research seasons: count + label", not bad, "; ".join(bad[:4]))
    no_res = [s for s, tm in teams.items() if not tm["has_research"] and tm["state"] != "none"]
    chk("Programs with no research seasons carry no research label", all(not teams[s]["research_text"] for s in no_res), f"{len(no_res)} programs")
    case_imgs = html.unescape(L.card_inner(c, None, "card") + L.card_inner(c, None, "og"))
    chk("Case share card and preview image: research label", case_imgs.count(rdset["label"]) == 2)

    lines = ["# DAWG Lab publishing safeguards", "",
             "Run on a throwaway copy of the repo with test fixtures (random numbers, never research). Each row puts a case into",
             "`_editorial/lab/` and runs the real `lab.py build` (or `approve`). \"Site writes\" compares every file outside `_editorial/`",
             "before and after.", "",
             "| # | Scenario | Result | Site writes | Reason given | Pass |", "|---|---|---|---|---|---|"]
    for i, (n, res, w, why, ok) in enumerate(rows, 1):
        lines.append(f"| {i} | {n} | {res} | {w} | {why.replace('|', '/')[:150]} | {'✓' if ok else '✗ FAIL'} |")
    lines += ["", "## Research-only values in the valid build", "", "| Where | Labeled | Detail |", "|---|---|---|"]
    for w, ok, det in checks:
        lines.append(f"| {w} | {'✓' if ok else '✗ FAIL'} | {det} |")
    lines += ["", "The team panel, pinned bar and side card are checked in the browser by `test_lab.py` (research note with a",
              "\"How they were made\" link to the receipts in every panel section that charts research games)."]
    passed = sum(1 for *_, ok in rows if ok) + sum(1 for _, ok, _ in checks if ok)
    total = len(rows) + len(checks)
    lines += ["", f"**{passed} of {total} safeguard checks passed.**", ""]
    text = "\n".join(lines)
    print(text)
    if report_path:
        open(report_path, "w").write(text)
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
