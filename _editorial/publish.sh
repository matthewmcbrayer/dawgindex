#!/bin/bash
# Publish Stories and DAWG Lab changes to the live site: the editorial lane. Independent of the weekly data run and of
# site-code publishes, which never touch lab/, stories/ or _editorial/ (sunday.sh checks that on every run).
#
#   bash _editorial/publish.sh "Publish LAB 001"           after approve + build (README steps 1-4 / the Lab section)
#   DAWG_DRY_RUN=1 bash _editorial/publish.sh "..."         every check, no lock, no commit, no push
#
# Run from a clone of the site repo on main. In order, it:
#   1. refuses changes outside lab/, stories/ and _editorial/ (working tree AND local commits not yet pushed);
#   2. takes the site's publish lock (_editorial/publish_lock.py, a byte-identical copy of dawg-pipeline's publish/lock.py),
#      waiting up to 15 min if the weekly run or a site-code publish holds it, then fast-forwards onto the live site;
#   3. checks the published pages are exactly what the approved sources build (build.py / lab.py build change nothing more),
#      runs build.py check, lab.py check and the editorial tests;
#   4. commits only those folders and pushes without force, then confirms the remote moved to that commit.
# Exit: 0 published (or nothing to publish), 1 refused or failed. Nothing is pushed unless every step passes.
set -Eeuo pipefail
REPO=$(git rev-parse --show-toplevel); cd "$REPO"
MSG=${1:-}; DRY=${DAWG_DRY_RUN:-}
LOCK="python3 _editorial/publish_lock.py"; URL=${DAWG_LOCK_REPO:-$(git remote get-url origin)}
ALLOW='^(lab|stories|_editorial)/'
RUN=""; RESULT=failed
die(){ echo; echo "EDITORIAL PUBLISH FAILED: $1"; echo "Nothing was pushed."; exit 1; }
trap 'die "a command failed (line $LINENO)"' ERR
release(){ [ -n "$RUN" ] || return 0; $LOCK "$URL" release --run "$RUN" --result "$RESULT" --detail "editorial: $MSG" || echo "WARNING: could not release the publish lock ($RUN); it expires on its own."; }
trap release EXIT
[ -n "$MSG" ] || die 'usage: bash _editorial/publish.sh "commit message"'
[ "$(git rev-parse --abbrev-ref HEAD)" = main ] || die "check out main first (this publishes to the live site's main branch)"
changed(){ { git status --porcelain=v1 -uall | cut -c4- | sed 's/.* -> //'; git diff --name-only origin/main...HEAD 2>/dev/null; } | sort -u | sed '/^$/d'; }
outside(){ changed | grep -vE "$ALLOW" || true; }

echo "== changes"
git fetch -q origin
[ -z "$(outside)" ] || die "these changes are outside lab/, stories/ and _editorial/; they belong to the site-code or data lane:
$(outside | head -20 | sed 's/^/  /')"
[ -n "$(changed)" ] || { echo "nothing to publish"; RESULT=no-change; exit 0; }
changed | sed 's/^/  /' | head -30

echo "== publish lock"
if [ -n "$DRY" ]; then echo "DRY RUN: not taking the lock. $($LOCK "$URL" status 2>&1 || true)"
else
  rc=0; RUN=$($LOCK "$URL" acquire --holder lab --ttl 30 --wait "${DAWG_LOCK_WAIT:-15}" --note "$MSG") || rc=$?
  [ $rc -eq 0 ] || { RUN=""; die "could not take the publish lock (exit $rc). $($LOCK "$URL" status 2>&1 || true)"; }
  echo "lock held: $RUN"
fi
git fetch -q origin
AHEAD=$(git rev-list --count origin/main..HEAD); BEHIND=$(git rev-list --count HEAD..origin/main)
if [ "$BEHIND" -gt 0 ]; then
  [ "$AHEAD" -eq 0 ] || die "this clone has $AHEAD local commit(s) and is $BEHIND behind the live site; rebase onto origin/main and rerun"
  git merge -q --ff-only --autostash origin/main || die "could not fast-forward onto the live site"
  echo "fast-forwarded $BEHIND commit(s) from the live site"
  [ -z "$(outside)" ] || die "after updating, changes outside the editorial folders appeared"
fi

echo "== the published pages are what the approved sources build"
state(){ git status --porcelain=v1 -uall | cut -c4- | sed 's/.* -> //' | sort -u | while read -r f; do echo "$f $([ -f "$f" ] && sha256sum < "$f" | cut -c1-16 || echo deleted)"; done; }
BEFORE=$(state)
python3 _editorial/build.py build > /tmp/editorial-build.out 2>&1 || { tail -5 /tmp/editorial-build.out; die "build.py build failed"; }
[ -f _editorial/lab.py ] && { python3 _editorial/lab.py build > /tmp/lab-build.out 2>&1 || { tail -5 /tmp/lab-build.out; die "lab.py build failed"; }; }
AFTER=$(state)
[ "$AFTER" = "$BEFORE" ] || die "the pages on disk were not what the approved sources build; rebuilding rewrote these (review with git diff, then rerun):
$( { echo "$BEFORE"; echo "$AFTER"; } | sort | uniq -u | cut -d' ' -f1 | sort -u | sed 's/^/  /' | head -10)"
[ -z "$(outside)" ] || die "a build wrote outside the editorial folders"

echo "== checks and tests"
python3 _editorial/build.py check > /tmp/editorial-check.out 2>&1 || { tail -5 /tmp/editorial-check.out; die "build.py check failed"; }
[ -f _editorial/lab.py ] && { python3 _editorial/lab.py check > /tmp/lab-check.out 2>&1 || { tail -5 /tmp/lab-check.out; die "lab.py check failed"; }; }
for t in test_editorial.py test_lab.py; do
  [ -f "_editorial/$t" ] || continue
  python3 "_editorial/$t" > "/tmp/$t.out" 2>&1 || { grep -E "^FAIL" "/tmp/$t.out" | head -10; tail -3 "/tmp/$t.out"; die "$t failed"; }
  echo "  $t: $(tail -1 "/tmp/$t.out" | cut -c1-120)"
done

if [ -n "$DRY" ]; then echo; echo "DRY RUN: every check passed; would commit and push:"; changed | sed 's/^/  /' | head -30; RESULT=ok; exit 0; fi

echo "== commit and push"
git add -A   # safe: step 1 (re-checked after the fast-forward) found no change outside the editorial folders; checked again below
git diff --cached --quiet || git -c user.name="Matthew McBrayer" -c user.email="mattwmcbrayer@gmail.com" commit -q -m "$MSG"
BAD=$(git diff --name-only origin/main..HEAD | grep -vE "$ALLOW" || true)
[ -z "$BAD" ] || die "the commits to push touch other paths: $BAD"
$LOCK "$URL" check --run "$RUN" || die "this run no longer holds the publish lock; not pushing"
git push -q origin HEAD:main || { sleep 5; git push -q origin HEAD:main; } || die "git push failed (no force is ever used; a rejection means the live site moved)"
[ "$(git ls-remote origin refs/heads/main | cut -c1-40)" = "$(git rev-parse HEAD)" ] || die "the push did not land"
RESULT=ok
echo; echo "EDITORIAL PUBLISH DONE: $(git rev-parse --short HEAD) is live on main (GitHub Pages serves it within a few minutes)"
