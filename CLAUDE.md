# DAWG project instructions

## Brand (required)

Read `BRAND.md` in this repo before any visual or editorial work. That covers new features, pages, page sections, graphics, share images, video, stories, Lab investigations and X copy. Every piece of that work must comply with it.

- Start from `BRAND.md`, not from the nearest existing component. Code on the site can be reused for function, but its styling isn't approved unless `BRAND.md` says so.
- Never copy or adapt the legacy production code in BRAND.md §8, even though it ships. The most common leak is the team share-card style block in `index.html`.
- Never use, recreate or adapt the retired elements in BRAND.md §7. The `v2-final` branch and `/v2/` are archive reference, not a design source.
- Don't redesign an approved component (BRAND.md §4 and Lab's dossier design in §4a) unless you can name the specific inconsistency you're fixing.
- If BRAND.md doesn't cover something, or it's on the deferred list in §10, flag it to Matthew and propose a rule. Don't default to older styling.
- Changes to BRAND.md itself need Matthew's approval and go through a branch, never straight to `main`.

## Unchanged by the brand rules

Methodology (V3 frozen for the season), research findings and checks, publication safeguards, the Sunday pipeline, and the rule that nothing merges or deploys without Matthew's explicit approval.
