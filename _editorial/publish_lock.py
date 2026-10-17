#!/usr/bin/env python3
"""DAWG publish lock: one publisher at a time on the site repo, and a record of the last Sunday run.

Who uses it: sunday.sh (the weekly data run and DAWG_MODE=site code publishes) and _editorial/publish.sh in the site repo
(Lab and Stories). The site repo's copy, _editorial/publish_lock.py, must be byte-identical to this file
(publish/test_publish.py checks it when given a site checkout).

How it works: the lock is a branch, refs/heads/publish-lock, in the site repo. Its one file, LOCK.json, says who holds the lock,
until when, and how the last Sunday run ended. Every change is a new commit on top of the one read, pushed WITHOUT force:
if two publishers race, Git accepts the first push and refuses the second as a non-fast-forward, so exactly one wins.
Nothing is ever deleted (the session proxy refuses ref deletion) and nothing is force-pushed.

  lock.py REPO acquire --holder sunday|site|lab --ttl MIN [--wait MIN] [--require-sunday-ok] [--note TEXT]
        prints the run id on success (exit 0); exit 3 if the lock stays held for --wait minutes; exit 4 if
        --require-sunday-ok and the last Sunday run did not finish successfully.
  lock.py REPO release --run RUN --result ok|no-change|failed [--week LABEL] [--detail TEXT]
        exit 0; exit 2 if RUN no longer holds the lock (it expired and someone else took it; nothing is overwritten).
  lock.py REPO check --run RUN     exit 0 if RUN still holds an unexpired lock (checked right before a push), else 2
  lock.py REPO status [--json]

A held lock whose TTL has passed may be taken over; the takeover is recorded. A Sunday run that dies without releasing
leaves sunday.result = "running", which keeps --require-sunday-ok publishers out until a Sunday run succeeds.
"""
import argparse, datetime as dt, json, os, random, subprocess, sys, tempfile, time

REF = "refs/heads/publish-lock"
SUNDAY_OK = {"ok", "no-change"}
WHO = {"GIT_AUTHOR_NAME": "Matthew McBrayer", "GIT_AUTHOR_EMAIL": "mattwmcbrayer@gmail.com",
       "GIT_COMMITTER_NAME": "Matthew McBrayer", "GIT_COMMITTER_EMAIL": "mattwmcbrayer@gmail.com"}
POLL = float(os.environ.get("DAWG_LOCK_POLL", "30"))   # seconds between tries while waiting (tests use 1)


def now():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


def iso(t):
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse(s):
    return dt.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)


class Repo:
    """A throwaway bare repo used only to read and write the lock branch of REPO."""
    def __init__(self, url):
        self.url, self.dir = url, tempfile.mkdtemp(prefix="dawg-lock-")
        self.git("init", "-q", "--bare")

    def git(self, *a, inp=None, check=True):
        r = subprocess.run(["git", "-C", self.dir, *a], input=inp, capture_output=True, text=True,
                           env={**os.environ, **WHO, "GIT_TERMINAL_PROMPT": "0"})
        if check and r.returncode:
            raise RuntimeError(f"git {' '.join(a[:2])} failed: {r.stderr.strip()[-300:]}")
        return r

    def read(self):
        """(commit sha or None, state dict)."""
        ls = self.git("ls-remote", self.url, REF).stdout.split()
        if not ls:
            return None, {"version": 1, "state": "free"}
        self.git("fetch", "-q", self.url, f"+{REF}:{REF}")
        sha = self.git("rev-parse", REF).stdout.strip()
        return sha, json.loads(self.git("show", f"{sha}:LOCK.json").stdout)

    def write(self, parent, state, msg):
        """Push a new LOCK.json on top of parent. True if accepted; False if someone else moved the ref first."""
        blob = self.git("hash-object", "-w", "--stdin", inp=json.dumps(state, indent=1, sort_keys=True) + "\n").stdout.strip()
        tree = self.git("mktree", inp=f"100644 blob {blob}\tLOCK.json\n").stdout.strip()
        commit = self.git("commit-tree", tree, *(["-p", parent] if parent else []), "-m", msg).stdout.strip()
        r = self.git("push", "-q", self.url, f"{commit}:{REF}", check=False)   # never --force
        if r.returncode == 0:
            return True
        if "non-fast-forward" in r.stderr or "rejected" in r.stderr or "fetch first" in r.stderr:
            return False
        raise RuntimeError(f"lock push failed: {r.stderr.strip()[-300:]}")


def held(state, t):
    return state.get("state") == "held" and parse(state["expires"]) > t


def describe(state, t=None):
    t = t or now()
    if state.get("state") == "held":
        left = int((parse(state["expires"]) - t).total_seconds() // 60)
        s = (f"HELD by {state['holder']} (run {state['run']}) since {state['acquired']}, "
             + (f"expires in {left} min" if left >= 0 else f"EXPIRED {-left} min ago (can be taken over)"))
    else:
        s = "FREE"
    su = state.get("sunday")
    s += "; last Sunday run: " + (f"{su['result']} ({su.get('week') or '?'}, {su.get('finished') or su.get('started')}, run {su['run']})" if su else "none recorded")
    return s


def acquire(a):
    r = Repo(a.repo)
    run = f"{a.holder}-{now().strftime('%Y%m%dT%H%M%SZ')}-{random.randrange(16**4):04x}"
    deadline = time.time() + a.wait * 60
    while True:
        sha, st = r.read()
        t = now()
        if held(st, t):
            if time.time() >= deadline:
                print(f"publish lock is busy: {describe(st, t)}", file=sys.stderr)
                return 3
            time.sleep(POLL)
            continue
        su = st.get("sunday")
        if a.require_sunday_ok and su and su.get("result") not in SUNDAY_OK:
            print(f"refusing to publish: the last Sunday run did not finish successfully ({describe(st, t)}). "
                  "Rerun the Sunday update until it succeeds, then publish.", file=sys.stderr)
            return 4
        new = dict(st, version=1, state="held", holder=a.holder, run=run, acquired=iso(t),
                   expires=iso(t + dt.timedelta(minutes=a.ttl)), note=a.note or "")
        if st.get("state") == "held":   # expired: record the takeover
            new["takeover"] = {"from": st["run"], "expired": st["expires"], "at": iso(t)}
        else:
            new.pop("takeover", None)
        if a.holder == "sunday":
            new["sunday"] = {"result": "running", "run": run, "started": iso(t)}
        if r.write(sha, new, f"lock: {a.holder} acquires ({run})"):
            print(run)
            return 0
        time.sleep(1)   # lost a race; read again


def release(a):
    r = Repo(a.repo)
    for _ in range(10):
        sha, st = r.read()
        if st.get("state") != "held" or st.get("run") != a.run:
            print(f"lock is no longer held by {a.run} ({describe(st)}); not changing it", file=sys.stderr)
            return 2
        t = now()
        new = {k: v for k, v in st.items() if k not in ("holder", "run", "acquired", "expires", "note", "takeover")}
        new.update(state="free", last={"holder": st["holder"], "run": a.run, "result": a.result, "finished": iso(t), "detail": a.detail or ""})
        if st["holder"] == "sunday":
            new["sunday"] = {"result": a.result, "run": a.run, "started": st["acquired"], "finished": iso(t),
                             "week": a.week or "", "detail": a.detail or ""}
        if r.write(sha, new, f"lock: {st['holder']} releases ({a.run}, {a.result})"):
            return 0
        time.sleep(1)
    print("could not release the lock after 10 tries", file=sys.stderr)
    return 1


def check(a):
    _, st = Repo(a.repo).read()
    if held(st, now()) and st.get("run") == a.run:
        return 0
    print(f"run {a.run} does not hold the publish lock any more ({describe(st)})", file=sys.stderr)
    return 2


def status(a):
    _, st = Repo(a.repo).read()
    print(json.dumps(st, indent=1, sort_keys=True) if a.json else describe(st))
    return 0


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("repo")
    sub = p.add_subparsers(dest="cmd", required=True)
    q = sub.add_parser("acquire")
    q.add_argument("--holder", required=True, choices=["sunday", "site", "lab"])
    q.add_argument("--ttl", type=float, required=True)
    q.add_argument("--wait", type=float, default=0)
    q.add_argument("--require-sunday-ok", action="store_true")
    q.add_argument("--note")
    q = sub.add_parser("release")
    q.add_argument("--run", required=True)
    q.add_argument("--result", required=True, choices=["ok", "no-change", "failed"])
    q.add_argument("--week")
    q.add_argument("--detail")
    q = sub.add_parser("check")
    q.add_argument("--run", required=True)
    q = sub.add_parser("status")
    q.add_argument("--json", action="store_true")
    a = p.parse_args()
    try:
        return {"acquire": acquire, "release": release, "check": check, "status": status}[a.cmd](a)
    except RuntimeError as e:
        print(f"publish lock error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
