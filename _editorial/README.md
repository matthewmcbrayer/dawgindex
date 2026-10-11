# DAWG editorial

Sources for the stories at dawgindex.com/stories/. GitHub Pages doesn't serve this folder (it starts with `_`), but the repo is public, so **only approved stories live here**. Drafts stay in the private drafts folder (`/home/claude/editorial-drafts/<slug>/`) until Matthew approves them.

Separate from the V3 grading pipeline. The build reads `_editorial/` plus `sitemap.xml` (for the team list) and writes only under `stories/`. It never deletes a file.

## Publishing a story

1. **Draft** in `/home/claude/editorial-drafts/<slug>/`:
   - `story.md`
   - `card.png`: 16:9, at least 1200 wide, the homepage and index art
   - optional `og.png`: 1200×630; generated automatically if missing
2. **Preview privately:** `python3 _editorial/build.py preview /home/claude/editorial-drafts/<slug>`. This writes outside the repo, marks the page noindex with a "not published" banner, and makes desktop and phone screenshots for Matthew.
3. **Only after Matthew explicitly approves:** `python3 _editorial/build.py approve /home/claude/editorial-drafts/<slug> --by "Matthew McBrayer"`
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
image: card.png
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
