# DAWG editorial

Sources for the stories at dawgindex.com/stories/. GitHub Pages doesn't serve this folder (it starts with `_`), but the repo is public, so **only approved stories live here**. Drafts stay in the private drafts folder (`/home/claude/editorial-drafts/<slug>/`) until Matthew approves them.

Separate from the V3 grading pipeline. The build reads `_editorial/` plus `sitemap.xml` (for the team list) and writes only under `stories/`. It never deletes a file.

## Publishing a story

1. **Draft** in `/home/claude/editorial-drafts/<slug>/`:
   - `story.md`
   - a `thumb:` block in story.md, then `python3 _editorial/thumbs.py /home/claude/editorial-drafts/<slug>` to draw `thumb.png` (1200×675), the card picture on the homepage, team pages and /stories/
   - optional `card.png`: the detailed story graphic (16:9, at least 1200 wide), kept for sharing; never used as the card picture
   - optional `og.png`: 1200×630; generated automatically if missing
2. **Preview privately:** `python3 _editorial/build.py preview /home/claude/editorial-drafts/<slug>`. This writes outside the repo, marks the page noindex with a "not published" banner, and makes desktop and phone screenshots for Matthew.
3. **Only after Matthew explicitly approves:** `python3 _editorial/build.py approve /home/claude/editorial-drafts/<slug> --by "Matthew McBrayer"`. This sets the story's date to the day it goes live (Central time) and records `published_at`, which orders stories published the same day (latest first).
4. **Build:** `python3 _editorial/build.py build`. This writes the page, card, social image, `/stories/` index, `stories.json` and `stories/sitemap.xml`.
5. **Test:** `python3 _editorial/test_editorial.py` must end with every check passing.
6. **Commit only `_editorial/` and `stories/`.** Fetch and rebase on `origin/main`, push without force, then verify the live page.

`python3 _editorial/build.py check` validates everything and writes nothing.

## story.md

```
---
slug: my-story                # folder name; lowercase-and-hyphens
status: draft                 # build only publishes 'published' + approved_by + approved_at
title: Full headline for search and sharing
card_title: Short title for homepage, team-page and Stories cards   # optional, 60 characters max; defaults to title
thumb:                        # the card picture; thumbs.py draws thumb.png from this (see the layouts at the top of thumbs.py)
  layout: stat                # stat | score | games
  teams: [oregon, ucla]
  stat: '7'
  label: Turnovers
  alt: Oregon logo next to a big red 7 labeled turnovers, with the UCLA logo after it.
headline: {big: Big line, sub: Second line}   # optional; on-page h1
tab: Red River Rivalry · Week 6
category: Game story
date: '2026-10-11'
teams: [oklahoma, texas]      # team page slugs, checked against the site
dek: One or two sentences under the headline.
card_dek: Optional shorter dek for cards
description: Search description, 200 characters max.
social_description: Optional; defaults to description
stamp: [Oct. 10, 2026, Cotton Bowl, Dallas, Data through Week 6, 2026, DAWG methodology v3.0]
scoreboard: {...}             # optional; see red-river-2026
image: card.png               # optional detailed graphic (kept as card.png; not the card picture)
image_alt: What the card image shows
og_image: og.png              # optional
format: markdown              # or html (body used verbatim)
---
Body in Markdown. `## Heading`, tables, **bold**, links.

::: doesnt
The "What this doesn't tell us" box (required by the editorial playbook).
:::

::: pull
A pull quote.
:::
```

## Rules the build enforces

- No approval on record, no publish. Drafts and unapproved stories in this folder stop the build before anything is written.
- A live story whose source goes missing stays live, untouched, and stays listed in the manifest, on `/stories/` and in the sitemap.
- Validation stops the build on any of these: missing fields, unknown team slugs, a slug that clashes with a site folder, a future date, wrong image sizes, or "2.0" in the copy.
- The same sources always produce byte-identical files.

## House style

**Rivalry names.** Use the full name on first reference, including the word that makes it a name: the Red River Rivalry (never just "Red River"), the Iron Bowl, the Egg Bowl, The Game, the Big Game, the Apple Cup, the Territorial Cup, the Lone Star Showdown, the Sunshine Showdown, the Backyard Brawl, the Holy War, Bedlam. After that, say "the rivalry" or the team names, not a clipped version. For trophy games, name the trophy and the game separately (Paul Bunyan's Axe is the trophy; the game is Minnesota–Wisconsin). Don't use retired or discouraged names ("Civil War" for Oregon–Oregon State, "Red River Shootout", "World's Largest Outdoor Cocktail Party") or sponsor names. When unsure, use the matchup ("Texas–Oklahoma"), and confirm any rivalry name with a quick search before it's published.

**Single-game PLAY variation.** Say: "Single-game PLAY results vary a lot: about 95% of them land within roughly ±21 points, and the standard deviation is about 11 points." Don't call ±21 a margin of error. (6,055 graded games: SD 10.5; 95.5% within ±20.6.)

**Season-average noise.** "Random swings alone put an n-game average anywhere within about ±X points of zero (a 95% range)", with X = 1.96 × 14.1 / √n for DAWG and 1.96 × 10.5 / √n for PLAY.

**Story cards.** Homepage, team pages and /stories/ all use one card: a simple thumbnail, the headline (`card_title`, 60 characters max) printed under it, then a slim row with category, team logos and date. The thumbnail never contains the headline. It shows one thing: team logos plus one number (`stat`), a final score with an optional second row such as yards (`score`), or a team's short run of DAWG results as bars (`games`). No dense charts, tiny labels or source lines; it has to read at 360px wide. `thumbs.py` stamps thumb.png with a hash of the `thumb:` block, and the build refuses a thumb.png that's missing or out of date. `python3 _editorial/build.py preview` also writes `preview-card-desktop.png` and `preview-card-phone.png` so the card can be checked before approval. `card_style` and `card_teaser` are retired.

## The DAWG Lab (`lab.py`)

Lab cases live in `_editorial/lab/NNN-slug/` (case.json, case.md, data.json, plan.md) and build into `lab/`. Same rules as
Stories: approval on record, private previews outside the repo, byte-identical rebuilds, nothing deleted.

- `python3 _editorial/lab.py sample` writes a SAMPLE case to /home/claude/lab-drafts. It can't be approved or built.
- `python3 _editorial/lab.py preview DRAFT_DIR` renders privately to /home/claude/lab-preview (noindex, marked Preview).
- `python3 _editorial/lab.py approve DRAFT_DIR --by "Matthew McBrayer"` only after Matthew's explicit OK.
- `python3 _editorial/lab.py build` writes nothing until a case is approved (no empty Lab). The Stories nav gains its Lab
  link in the same build, and not before.
- Team copy is descriptive by default; habit words are refused unless the case carries a supported team finding.
- Tests: `python3 _editorial/test_lab.py`.
