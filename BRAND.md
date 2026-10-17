# DAWG brand specification

Version 1.0 · written Oct 17, 2026 · documents the identity approved Oct 8–10, 2026

This file is the single source of truth for how DAWG looks and sounds. It applies to every DAWG surface: dawgindex.com, Stories, Lab, Compare, team pages, share images, X graphics, video and anything new.

How to use it:

1. New work starts from this file, not from the nearest existing component. Existing production styling is not automatically approved. Some pre-rebrand styling still ships on the site (see "Known pre-rebrand code still in production").
2. Reuse existing code for function. Take presentation from this file.
3. If this file doesn't define something, flag the gap to Matthew. Don't fill it with an older design. Open gaps are listed at the end.
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
| DAWG / MORE TO THE STORY. | Optional editorial lockup, only when the DAWG letters are at least 72px tall on screen. See open gap G1 |

- The descriptor is a separate text element, so it can become COLLEGE SPORTS when basketball launches. Don't bake it into artwork.
- Descriptor type: Barlow Condensed Bold, uppercase, tracked 0.169em. On the site it's the self-hosted face "Barlow Condensed Logo" (`/brand/BarlowCondensed-Bold.ttf`), 12.5px under a 150px-wide logo, 5px gap, 1px left inset. Scale those numbers together.
- No other text, badge, pill or tag attaches to the mark. A section label such as LAB sits beside the lockup, never inside it. See gap G6.

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
- Surface balance across a page: about 70% warm paper, 20% ivory, 10% dark. One dark feature section per page, plus the footer.
- Paper grain, when used, is extremely fine and quiet. No stains, scratches, torn edges or heavy distress.
- Team colors may identify a team (ticket sides, swatches). They never stand in for grade color.

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

## 5. Language

- Positioning line: **More Than the Score.** (set as "More than the score." in running copy and the footer).
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
| Bowlby One as a headline face; any stroked or offset-shadow headline treatment | Big Shoulders Display 800–900, flat ink |
| Dark page ground as the site default (ink pages with cream cards); the grey light/dark theme tokens (`#15171a`, `#1d2024`, `#f3f2ee`, `#ecebe6`); Saira Condensed and IBM Plex Sans | Paper ground per §2, one dark feature section; the five families in §3 |
| Multi-color striped rules under headers and on share-image bands (red, blue, cream and orange stripes) | A 2px ink rule |
| Orange call-to-action buttons; pill-shaped main navigation; rounded cream "What is this? / Got it" explainer card | Ink buttons; underline-on-current nav; editorial sections |
| Red hard offset shadows on inputs, cards and blocks | Ink offset shadows (§4) |
| "DAWG score," the ±3 thresholds, "who shows up when it counts," "only beats cupcakes," big-game "gets up / shrinks" framing, "trait" language about teams | Section 5 terminology and ±12.3 / ±24 labels |
| V2 features and their names in new work: Matchup Builder, Coaches tab and coach leaderboards, Luck, Finishing, Knife Twist, Cash-In, Answers, green/gold/red thirds | V3 DAWG and PLAY only (V2 stays in the `/v2/` archive) |

Pre-rebrand language that is explicitly retained: "living up to expectations" (a required phrase in §5).

## 8. Known pre-rebrand code still in production

Listed so nobody copies from it. Nothing here has been changed, and fixing any of it needs Matthew's approval.

1. **Team share card** (`STK` style block in `index.html`, the "one-image season profile" share). It uses the retired stroked Bowlby headline with a red shadow, the blue rotated pill, Bowlby h2s, and the striped band with orange. The block is identical in `v2-final`.
2. **Static team stub pages** (`/<team>/index.html`, one per team plus short-name aliases, generated by the pipeline). These have a dark ground, the "DAWG [INDEX]" lockup, an orange "Open the full team file" button and the striped rule.
3. **Old theme tokens in `index.html`.** The page's outer stylesheet still defines Saira Condensed, IBM Plex Sans and the grey light/dark themes (`#15171a`, `#f3f2ee`). The October pages use the tokens in §2–3 instead. Treat these as legacy code paths.
4. **Team page headline wording.** For example, Northwestern: "one of the Power 4's best at beating the line." That phrase is ruled out in §5.

## 9. Open gaps (flag, don't fill)

- **G1.** "MORE TO THE STORY." was approved Oct 8 as the editorial tagline and optional lockup. "More Than the Score." became the positioning line Oct 10. Is MORE TO THE STORY. still in use, or retired?
- **G2.** "Vegas sets the bar. We grade who cleared it." predates the rebrand and still heads the live How It Works section. Retained or retired?
- **G3.** Dark-mode behavior. The brand is paper-first and single-theme. There is no approved dark theme beyond the dark feature section and the reversed logo.
- **G4.** Data-viz palette beyond grade colors: categorical series, neutral fills, and non-grade fills such as a field or turf green. Not defined.
- **G5.** Motion and video: easing, durations, scene transitions, frame size and length for animated explainers. Not defined.
- **G6.** Lab sub-brand. The Lab branch adds a "LAB" boxed tag beside the lockup, double-rule verdict stamps set in Big Shoulders instead of Bowlby, and Lab-only colors (`#FF8A7E`, `#8FB0F0`, `#C2342A`, `#B8AD98`, `#D9CFB6`, `#1E1C19`, `#4A443B`). None of these are in this spec yet. Verdict colors also need a rule so red ("holds") doesn't read as SOFT.
- **G7.** 3D and interactive pieces (for example the DAWG Field): materials, lighting, label sprites. Not defined.
- **G8.** Logo minimum size and clear space. The master sheet gives only the 72px tagline rule.
