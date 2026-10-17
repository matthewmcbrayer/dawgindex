# DAWG brand specification

Version 1.1 · Oct 17, 2026 · documents the identity approved Oct 8–10, 2026 (approved as authoritative by Matthew, Oct 17)

This file is the single source of truth for how DAWG looks and sounds. It applies to every DAWG surface: dawgindex.com, Stories, Lab, Compare, team pages, share images, X graphics, video and anything new.

How to use it:

0. Read this file before any visual or editorial work: pages, features, graphics, share images, video, stories and X copy.
1. New work starts from this file, not from the nearest existing component. Existing production styling is not automatically approved. Some pre-rebrand styling still ships on the site (§8, "Legacy production code: do not copy").
2. Reuse existing code for function. Take presentation from this file.
3. If this file doesn't define something, flag the gap to Matthew. Don't fill it with an older design. Deferred topics are listed in §10.
4. Methodology, research findings and publication safeguards are not set here and are unchanged by this file.

Where values come from: the logo master artifact "DAWG Index Logo v1.0" (claude.ai/artifact/GRSdqypRtn9cjKQJSPexRY, approved Oct 8), and the live October CSS (`_editorial/templates/story.css` and the homepage template inside `index.html`, as of commit 377ffb5). When those sources and this file disagree, ask. Don't pick one.

---

## 1. Logo

The mark is **Option 01**: a black condensed DAWG wordmark followed by three slanted bars, blue on top, yellow in the middle, red at the bottom.

- Master artwork lives in the logo artifact (`svg/dawg-logo.svg`, `svg/dawg-logo-reversed.svg` and the tagline versions, with `SHA256SUMS.txt`). The site header inlines the same paths, `viewBox="0 -0.8 334.3 126.0"`.
- Never redraw, re-space, recolor, stroke, shadow, rotate or stretch the mark. Never set "DAWG" in a font as a stand-in for the mark.
- Bar colors: blue `#2F64C0`, yellow `#F5C030`, red `#E5463A`. Letters: ink `#131210` on light grounds, cream `#F4EAD2` on dark grounds (the reversed master).

### Lockups

| Lockup | Use |
|---|---|
| DAWG (wordmark alone) | Small sizes, favicons, avatars, anywhere the descriptor would be illegible |
| DAWG / COLLEGE FOOTBALL | Primary website and brand lockup (site header, Lab, Stories) |

The DAWG / MORE TO THE STORY. lockup is retired (§7). The tagline versions in the logo artifact (`dawg-logo-tagline.svg`, `dawg-logo-reversed-tagline.svg`) are archive files, not for new work.

- The descriptor is a separate text element, so it can become COLLEGE SPORTS when basketball launches. Don't bake it into artwork.
- Descriptor type: Barlow Condensed Bold, uppercase, tracked 0.169em. On the site it's the self-hosted face "Barlow Condensed Logo" (`/brand/BarlowCondensed-Bold.ttf`), 12.5px under a 150px-wide logo, 5px gap, 1px left inset. Scale those numbers together.
- No other text, badge, pill or tag attaches to the mark. A section label sits beside the lockup, never inside it. The approved example is Lab's boxed LAB tag (§4a).
- Minimum size and clear space are deferred (§10). Until they're defined, use the lockup as the site header already does and don't invent spacing rules.

## 2. Color

| Token | Hex | Role |
|---|---|---|
| `--paper` | `#F4EAD2` | Primary ground: hero and editorial areas |
| `--paper-2` | `#FBF4E2` | Ivory: cards, tickets, data-heavy sections, sticker paper |
| `--paper-3` | `#EADFC4` | Folder or tab tone, quiet panels |
| `--ink` | `#131210` | Type, rules, borders, the one dark feature section, footer |
| `--ink-2` | `#3B362E` | Secondary text |
| `--muted` | `#6E6557` | Captions, meta, labels |
| `--rule` / `--rule-2` | ink at 16% / 34% | Hairlines and dividers |
| `--red` | `#E5463A` | Brand red: kickers, tabs, SOFT fills, one accent per view |
| `--blue` | `#2F64C0` | Info stickers, links of note, the logo bar |
| `--green` | `#23885A` | DAWG and Certified DAWG fills (stickers) |
| `--yellow` | `#F5C030` | Highlight, logo bar, warnings such as SAMPLE |
| `--orange` | `#F08A2C` | Reserved. Present in tokens; use only where an approved component already does |
| `--pos` | `#1E7A50` | Positive numbers and DAWG stamps (text-weight green) |
| `--neg` | `#D13A2F` | Negative numbers and SOFT stamps (text-weight red) |

Rules:

- Grade color is fixed. Better than expected is green (`--pos` text, `--green` fill). Worse than expected is red (`--neg` text, `--red` fill). As expected is ink or `--ink-2`. Blue never means DAWG.
- There is one identity and no separate dark mode. Pages are paper-first. Dark appears only as the dark feature section, the footer, Lab case covers and Lab share cards, and the reversed logo. A page doesn't switch to a dark theme with the viewer's system setting.

### Chart and purpose-specific colors

Charts and graphics may use colors chosen for their purpose (categories, series, a field or turf ground, a highlight), with three conditions:

1. Grade semantics stay intact. Green and red from §2 mean better or worse than expected and nothing else. A chart never uses another color to show a grade, and never uses the grade greens and reds for a non-grade meaning.
2. Purpose-specific colors must be visibly distinct from the grade green and red, and every one of them is named in a legend or label. Color is never the only way to tell series apart.
3. Team colors may identify teams, as in §2.

Record any new purpose-specific color in the graphic's source with a one-line note on what it means.
- Surface balance across a page: about 70% warm paper, 20% ivory, 10% dark. One dark feature section per page, plus the footer.
- Paper grain, when used, is extremely fine and quiet. No stains, scratches, torn edges or heavy distress.
- Team colors may identify a team (ticket sides, swatches, chart marks). They never stand in for grade color.

## 3. Typography

| Token | Family | Use |
|---|---|---|
| `--display` | Big Shoulders Display, 800–900 | Headlines, team names, big numbers, scores. Uppercase. Tight leading (0.82–0.95). The hero may condense with `scaleX(.88–.9)` |
| `--stamp` | Bowlby One | Stamps and small badges only: status stamps, the ticket "AT" disc, scale words, numbered step discs. Never headlines, never body, never stroked, never with a text shadow |
| `--cond` | Barlow Condensed, 600–800 | Kickers, tabs, table heads, buttons, short labels. Uppercase, tracked 0.12–0.16em |
| `--body` | Barlow, 400–700 | Running text, decks, explanations |
| `--mono` | IBM Plex Mono, 400–600 | Data, receipts and ledgers, dates, game IDs, footnotes, small meta |
| — | Barlow Condensed Logo | The logo descriptor only |

- Kicker: Barlow Condensed 800, 13px, tracked 0.16em, uppercase, red.
- Tab label: red fill, white Barlow Condensed 800, tracked 0.14em, rotated about −1.5° to −3°.
- Numbers that line up use `font-variant-numeric: tabular-nums`.
- Load only these families. Fallbacks: "Arial Narrow" for display and condensed, `system-ui` for Barlow, `ui-monospace` for mono.

## 4. Design language

The direction is a modern college-sports data publication with vintage sports ephemera: about 85–90% clean graphic design and 10–15% analog print character.

It should feel like a premium sports publication. It should not feel like a SaaS dashboard, an antique scrapbook, an amusement park, a license plate, a video-game rating card, or EA Sports College Football and Ultimate Team interfaces.

Approved components keep their anatomy. Change them only to fix a specific, named inconsistency.

- **Ticket.** Two team sides in team colors with a logo disc, Big Shoulders names and scores, and a Bowlby "AT" disc. A dashed perforation leads to an ivory stub with the week, date, venue and a real Code 128 barcode. It is slightly rotated in hero use.
- **Status stamp** (`.stampmark`). Bowlby One, uppercase, a 4px border in the current color, 8–10px radius, translucent ivory fill, slight rotation. DAWG and Certified DAWG use `--pos`, SOFT and Certified SOFT use `--neg`, As Expected uses `--ink-2`.
- **Sticker.** A 136px card with a 14px radius and a 2.5px ink border plus an ivory ring and soft drop. It carries a Big Shoulders value and a Barlow Condensed label. Variants: green (good), ivory with red text (bad), blue (info), paper (neutral). Slightly rotated.
- **Ledger / receipt.** IBM Plex Mono on ivory, a 1.5px ink border and a 4px 4px 0 ink offset shadow. Line items run down to a total. Use it for "how we got the grade."
- **Editorial structure.** A 2px ink rule under section heads, thin rules and occasional double rules, small uppercase labels, generous but not empty negative space.
- **Hard offset shadows** are ink. A red offset shadow appears only as a hover state on a mini card.
- **Pill shapes** (999px radius) are for small filter and toggle buttons only, not for navigation or brand marks.
- **Buttons.** Ink fill, paper text, Barlow 700 uppercase, tracked 0.1em.

## 4a. Lab dossier design (approved)

Lab keeps its own approved dossier design, built on the site masthead, footer and §2–3 tokens. Preserve it as is. Source: `_editorial/templates/lab/` on the `lab-v0` branch (commit 123a5a1), where every Lab class is prefixed `lb-`.

- **Case cover.** The one dark component: ink ground, cream Big Shoulders 900 headline, Barlow dek, mono meta and breadcrumb.
- **Evidence exhibits.** Ivory panels on a faint 16px ink grid, 2px ink border, mono exhibit heads.
- **Reading.** Cream article column with a sticky side rail; receipts as a mono definition list; version and correction notes.
- **LAB tag.** A boxed IBM Plex Mono "LAB" label set beside the DAWG / COLLEGE FOOTBALL lockup on Lab pages.
- **Status bands.** Yellow SAMPLE and red PREVIEW bands for pages that aren't public findings.
- **Team panel.** A drawer on desktop, full screen on phones, with a pinned team bar on phones.

Lab tokens (Lab only, in addition to §2):

| Token | Hex | Role |
|---|---|---|
| `--lb-dark` / `--lb-dark-2` | `#131210` / `#1E1C19` | Cover ground and its inset panels |
| `--lb-line-d` | `#4A443B` | Rules on dark |
| `--lb-cream` / `--lb-cream-2` | `#F4EAD2` / `#FBF4E2` | Type on dark / evidence panels |
| `--lb-folder` | `#EADFC4` | Folder tabs and notices |
| `--lb-muted-d` / `--lb-sub-d` | `#B8AD98` / `#D9CFB6` | Meta and dek text on dark |
| `--lb-red-ink` | `#C2342A` | Team names in exhibits, big figures |
| `--lb-soft` | `#D6CAB0` | Soft dividers |

### Research-verdict colors (separate from grade colors)

A research verdict says whether a claim held up in an investigation. It is not a performance grade, so it has its own colors, which appear only on Lab's dark covers and Lab share cards:

| Verdict | Color | Mark |
|---|---|---|
| Holds up | `#FF8A7E` | Check icon, solid double-rule stamp |
| Doesn't hold up | `#F4EAD2` (cream) | X icon, solid double-rule stamp |
| Mixed evidence | `#8FB0F0` | Half-filled circle, solid double-rule stamp |
| Inconclusive | `#B8AD98` | Question mark, dashed double-rule stamp |

Verdict stamps are set in Big Shoulders 900 with a mono subline. They are a different component from the §4 status stamp, which stays Bowlby. Rules:

- Verdict colors never show a DAWG grade. Grade colors never show a verdict.
- A verdict always carries its word and icon, so it never depends on color. This keeps Holds up from reading as SOFT.
- Verdicts appear on dark grounds only. On cream, use the word and icon in ink.

## 5. Language

- Positioning line: **More Than the Score.** It is the single positioning line and the only tagline (set as "More than the score." in running copy and the footer).
- Explanatory copy: "Vegas sets the bar. We grade who cleared it." may be used to explain how grading works, for example as a section heading in How It Works. It is never a tagline: not beside the logo, not as a sign-off, not as a lockup.
- The one DAWG definition, always in the same words: "DAWG = points better or worse than Vegas expected, garbage time removed." It rides with every DAWG post, in the first 280 characters or on the graphic.
- Nouns: "DAWG grade" (a game), "season DAWG grade" (the average). Unit: "pts vs. Vegas." DAWG is the scoreboard against Vegas. PLAY is offense and defense against Vegas.
- Labels: Certified DAWG, DAWG, As Expected, SOFT, Certified SOFT, with cutoffs at ±12.3 and ±24.0. Ticket language: "Certified DAWG performance" / "Certified SOFT performance."
- Use "of 68 Power 4 teams" and "living up to expectations." Claims describe what has happened so far, never what will happen. It's not a power ranking, not a prediction and not betting advice.
- Never use "beat Vegas," "covered," "beat the spread" or "beat the line" as stand-ins for a grade. A bettor's question gets the documented answer: close to covering, with two differences.
- QB lists are "by the numbers." Use "Struggling the most," never "soft," for QBs.
- "2.0" is an internal name and never appears in public copy.
- Rivalries use their full names (the Red River Rivalry, the Iron Bowl).
- First-time reader rule: lead with the football question, explain any house metric in plain English in the same post, and make the takeaway stand on its own.
- Copy is direct and plain. No corporate or AI-sounding phrasing.

## 6. Formats

- X graphics: 1080×1350 (4:5). One finding per image, with a headline and a visual that say the same thing. Show where any non-obvious number comes from. Non-DAWG stats are labeled "A football stat, not a DAWG grade." Show a sample size or minimum when it matters.
- Link previews: 1200×630.
- Check every graphic and page at 360 and 390px wide. No text overflow.

---

## 7. Retired: pre-rebrand elements

These predate the Oct 8–10 rebrand. Don't use, recreate or adapt them. The `v2-final` branch and `/v2/` hold them as archive reference only.

| Retired element | Replaced by |
|---|---|
| The "DAWG [INDEX]" lockup: stroked Bowlby "DAWG" with a red offset shadow and a blue rotated "INDEX" pill | Option 01 logo with the COLLEGE FOOTBALL descriptor |
| The brown retro football badge (old X avatar and favicon) | Wordmark-based avatar and icon set |
| Tagline "Who gets up for big games, and who shrinks." | "More Than the Score." |
| Tagline "MORE TO THE STORY." and the DAWG / MORE TO THE STORY. lockup (approved Oct 8, retired Oct 17) | "More Than the Score." as the single positioning line |
| "Vegas sets the bar. We grade who cleared it." used as a tagline | Kept only as explanatory copy (§5) |
| A dark theme or dark-mode variant of the site | One paper-first identity (§2) |
| Bowlby One as a headline face; any stroked or offset-shadow headline treatment | Big Shoulders Display 800–900, flat ink |
| Dark page ground as the site default (ink pages with cream cards); the grey light/dark theme tokens (`#15171a`, `#1d2024`, `#f3f2ee`, `#ecebe6`); Saira Condensed and IBM Plex Sans | Paper ground per §2, one dark feature section; the five families in §3 |
| Multi-color striped rules under headers and on share-image bands (red, blue, cream and orange stripes) | A 2px ink rule |
| Orange call-to-action buttons; pill-shaped main navigation; rounded cream "What is this? / Got it" explainer card | Ink buttons; underline-on-current nav; editorial sections |
| Red hard offset shadows on inputs, cards and blocks | Ink offset shadows (§4) |
| "DAWG score," the ±3 thresholds, "who shows up when it counts," "only beats cupcakes," big-game "gets up / shrinks" framing, "trait" language about teams | Section 5 terminology and ±12.3 / ±24 labels |
| V2 features and their names in new work: Matchup Builder, Coaches tab and coach leaderboards, Luck, Finishing, Knife Twist, Cash-In, Answers, green/gold/red thirds | V3 DAWG and PLAY only (V2 stays in the `/v2/` archive) |

Pre-rebrand language that is explicitly retained: "living up to expectations" (a required phrase in §5) and "Vegas sets the bar. We grade who cleared it." (explanatory copy only).

## 8. Legacy production code: do not copy

This code is live on dawgindex.com today but predates the rebrand. Never copy, adapt or reference it for new work, even though it ships. Reuse its functionality only by separating it from its presentation. Nothing here has been changed, and changing any of it needs Matthew's approval.

1. **Team share card** (`STK` style block in `index.html`, the "one-image season profile" share). It uses the retired stroked Bowlby headline with a red shadow, the blue rotated pill, Bowlby h2s, and the striped band with orange. The block is identical in `v2-final`.
2. **Static team stub pages** (`/<team>/index.html`, one per team plus short-name aliases, generated by the pipeline). These have a dark ground, the "DAWG [INDEX]" lockup, an orange "Open the full team file" button and the striped rule.
3. **Old theme tokens in `index.html`.** The page's outer stylesheet still defines Saira Condensed, IBM Plex Sans and the grey light/dark themes (`#15171a`, `#f3f2ee`). The October pages use the tokens in §2–3 instead. Treat these as legacy code paths.
4. **Team page headline wording.** For example, Northwestern: "one of the Power 4's best at beating the line." That phrase is ruled out in §5.

When starting from existing code, check it against this list first. The most common leak is the share-card style block (item 1), because it sits in `index.html` next to the October styles and uses the same font names.

## 9. Decisions log

| Date | Decision |
|---|---|
| Oct 8–10, 2026 | Rebrand approved: Option 01 logo, COLLEGE FOOTBALL descriptor, warm paper direction, ticket / stamp / editorial language |
| Oct 10, 2026 | "More Than the Score." adopted as the positioning line |
| Oct 17, 2026 | October identity approved as the authoritative DAWG brand (this file) |
| Oct 17, 2026 | "MORE TO THE STORY." retired as an active tagline |
| Oct 17, 2026 | "Vegas sets the bar. We grade who cleared it." kept as explanatory copy, not a tagline |
| Oct 17, 2026 | No separate dark-mode identity |
| Oct 17, 2026 | Purpose-specific chart colors allowed; grade-color semantics preserved |
| Oct 17, 2026 | Lab's dossier design preserved; research-verdict colors defined separately from grade colors |
| Oct 17, 2026 | Motion, 3D and logo-spacing rules deferred until needed |

## 10. Deferred: define when needed

These are intentionally not specified yet. When a piece of work needs one, propose the rule to Matthew for that piece, then add it here once approved. Don't borrow pre-rebrand styling to fill the gap.

- **Motion and video.** Easing, durations, scene transitions, frame size and length for animated explainers.
- **3D and interactive pieces.** Materials, lighting, label treatment (for example the DAWG Field).
- **Logo spacing.** Minimum size and clear space (interim rule in §1).
