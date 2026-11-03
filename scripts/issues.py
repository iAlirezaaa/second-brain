#!/usr/bin/env python
"""The issue ledger — where an open report stops being invisible.

Usage:
  python scripts/issues.py            # render 00_START_HERE/ISSUES.md from the ledger
  python scripts/issues.py --check    # gate: the ledger is honest and the page is fresh
  python scripts/issues.py --fetch    # compare the ledger to GitHub (needs network)

The owner's brief says an issue that is resolved has to *show* in the repo, and this repo
had the opposite habit: issue #39 was fixed in `f73a378` and the folder said nothing about
it, because the fix lived in a commit message and the GitHub issue stayed open. A status
that lives only upstream is a status a reader of a clone cannot see.

So the ledger is a checked-in file, `15_SYSTEM/config/issues.json`, and this script is the
only writer of the page built from it. The gate refuses four kinds of dishonesty:

  1. a `fixed` row with no commit and no evidence path a clone contains — "we fixed it" is
     not evidence;
  2. a `fixed` row that does not say why the upstream issue may still be open;
  3. an `open` row with no sentence naming what is actually missing;
  4. a page that disagrees with the ledger, i.e. a render somebody forgot.

`--fetch` is the only part that touches the network, and it never writes: it reports the
drift between the ledger and `api.github.com`, so the gate stays offline and green on a
laptop with no connection.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import clone_readable, find_root, load_json, state_fingerprint, is_repo_checkout  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass

LEDGER = "15_SYSTEM/config/issues.json"
PAGE = "00_START_HERE/ISSUES.md"
STATES = ("open", "partial", "fixed", "closed")
UPSTREAM = ("open", "closed")


def ledger_path(root):
    return Path(root) / LEDGER


def page_path(root):
    return Path(root) / PAGE


def read_ledger(root):
    path = ledger_path(root)
    if not path.exists():
        return {"repo": "", "issues": []}, ["%s is missing" % LEDGER]
    try:
        data = load_json(path)
    except ValueError as exc:
        return {"repo": "", "issues": []}, ["%s is not JSON: %s" % (LEDGER, exc)]
    return data, []


def problems_in(data, root):
    """Every reason the ledger cannot be trusted, in the words of the row that failed."""
    problems = []
    if not data.get("repo"):
        problems.append("the ledger does not name the repo it tracks")
    rows = data.get("issues")
    if not isinstance(rows, list) or not rows:
        return problems + ["the ledger holds no issues"]
    seen = set()
    for row in rows:
        number = row.get("number")
        if not isinstance(number, int):
            problems.append("a row has no integer `number`: %r" % (row,))
            continue
        if number in seen:
            problems.append("#%d appears twice" % number)
        seen.add(number)
        if not str(row.get("title") or "").strip():
            problems.append("#%d has no title" % number)
        if row.get("state") not in STATES:
            problems.append("#%d state %r is not one of %s" % (number, row.get("state"), list(STATES)))
        if row.get("upstream") not in UPSTREAM:
            problems.append("#%d upstream %r is not one of %s"
                            % (number, row.get("upstream"), list(UPSTREAM)))
        # a `closed` row is upstream's decision, so it needs no commit of ours; a `fixed`
        # row is this repo's claim, and a claim needs the change and a path a clone carries
        if row.get("state") == "fixed":
            if not row.get("commit"):
                problems.append("#%d is fixed but names no commit" % number)
            evidence = row.get("evidence") or []
            if not evidence:
                problems.append("#%d is fixed but cites no evidence — a claim nobody can open"
                                % number)
            for entry in evidence:
                if not (Path(root) / entry).exists():
                    problems.append("#%d cites %s, which does not exist" % (number, entry))
                elif not clone_readable(entry):
                    problems.append("#%d cites %s, which a clone does not carry"
                                    % (number, entry))
        if row.get("state") == "fixed" and row.get("upstream") == "open" and not row.get("note"):
            problems.append("#%d is fixed here but open upstream, and does not say why"
                            % number)
        if row.get("state") in ("open", "partial") and not str(row.get("gap") or "").strip():
            problems.append("#%d is %s but never says what is still missing"
                            % (number, row["state"]))
        if row.get("state") == "open" and row.get("upstream") == "closed":
            problems.append("#%d is closed upstream but listed as open work" % number)
    return problems


def counts(rows):
    out = {state: 0 for state in STATES}
    for row in rows:
        out[row.get("state")] = out.get(row.get("state"), 0) + 1
    return out


def render(data, root):
    rows = sorted(data["issues"], key=lambda row: row["number"])
    tally = counts(rows)
    lines = [
        "# ایشیوها — دفترِ وضعیت",
        "",
        "این صفحه از `%s` ساخته می‌شود؛ دستی ویرایش نکنید. `python scripts/issues.py`" % LEDGER,
        "می‌نویسد و `python scripts/issues.py --check` (داخل `python scripts/health.py`)",
        "می‌سنجد که هر ردیفِ «اصلاح‌شده» یک کامیت و یک مسیرِ شاهد دارد که در یک کلون هم هست،",
        "و هر ردیفِ «باز» جمله‌ای می‌گوید که چه چیزی هنوز کم است.",
        "",
        "| ایشیو | موضوع | وضعیت در کد | گیت‌هاب | شاهد |",
        "| --- | --- | --- | --- | --- |",
    ]
    label = {"open": "باز", "partial": "نیمه", "fixed": "اصلاح‌شده", "closed": "بسته"}
    for row in rows:
        evidence = row.get("evidence") or []
        cited = "، ".join("`%s`" % entry for entry in evidence[:2]) or "—"
        if row.get("commit"):
            cited = "`%s`، %s" % (row["commit"], cited)
        lines.append("| #%d | %s | %s | %s | %s |" % (
            row["number"], row["title"].replace("|", "/"), label.get(row["state"], row["state"]),
            "باز" if row["upstream"] == "open" else "بسته", cited))
    lines += ["", "## وضعیت‌ها", "",
              "**%d باز · %d نیمه · %d اصلاح‌شده · %d بسته** — جمعاً %d ایشیو."
              % (tally["open"], tally["partial"], tally["fixed"], tally["closed"], len(rows)), ""]
    for row in rows:
        if row.get("state") in ("open", "partial"):
            lines.append("- **#%d** %s" % (row["number"], row.get("gap")))
        if row.get("state") == "fixed" and row.get("upstream") == "open":
            lines.append("- **#%d** (اصلاح‌شده، ایشیو باز) %s" % (row["number"], row.get("note")))
    lines.append("")
    return "\n".join(lines)


def write(root):
    data, bad = read_ledger(root)
    if bad:
        print("REFUSED: " + "; ".join(bad))
        return 1
    text = render(data, root)
    page_path(root).parent.mkdir(parents=True, exist_ok=True)
    page_path(root).write_text(text, encoding="utf-8")
    print("WROTE %s (%d issue(s))" % (PAGE, len(data["issues"])))
    return 0


def check(root):
    # an installed home has no issue ledger and no GitHub repo behind it; like the other
    # machine-plane gates, this one stays quiet while its file is absent rather than
    # inventing a defect for a folder that never claimed to track issues
    if not ledger_path(root).exists():
        if is_repo_checkout(Path(root)):
            print("REFUSED: this repository checkout is missing %s" % LEDGER)
            return 1
        print("OK — installed home has no issue ledger (no repository issue contract)")
        return 0
    data, bad = read_ledger(root)
    problems = bad + problems_in(data, root)
    if problems:
        for problem in problems:
            print("INVALID  %s" % problem)
        print("REFUSED: the issue ledger does not meet its own contract (%s)" % LEDGER)
        return 1
    page = page_path(root)
    if not page.exists():
        print("INVALID  %s is missing — run python scripts/issues.py" % PAGE)
        return 1
    if page.read_text(encoding="utf-8") != render(data, root):
        print("STALE    %s — run python scripts/issues.py" % PAGE)
        return 1
    tally = counts(data["issues"])
    print("OK — %d issue(s) on the ledger: %d open, %d partial, %d fixed, %d closed; "
          "every fixed row cites a commit and a clone-readable path (%s)"
          % (len(data["issues"]), tally["open"], tally["partial"], tally["fixed"],
             tally["closed"], state_fingerprint(root)))
    return 0


def fetch(root):
    import urllib.request
    data, bad = read_ledger(root)
    if bad:
        print("REFUSED: " + "; ".join(bad))
        return 1
    repo = data["repo"]
    url = "https://api.github.com/repos/%s/issues?state=all&per_page=100" % repo
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "second-brain-issues"})
        with urllib.request.urlopen(request, timeout=20) as response:
            live = json.loads(response.read().decode("utf-8"))
    except Exception as exc:  # network, rate limit, 404 -- all mean "cannot compare now"
        print("SKIPPED  cannot read %s right now (%s) — the ledger is unchanged" % (url, exc))
        return 0
    live = {row["number"]: row for row in live if "pull_request" not in row}
    tracked = {row["number"]: row for row in data["issues"]}
    drift = []
    for number, row in sorted(live.items()):
        if number not in tracked:
            drift.append("#%d is on GitHub (%s) and absent from the ledger: %s"
                         % (number, row["state"], row["title"]))
        elif row["state"] != tracked[number]["upstream"]:
            drift.append("#%d is %s upstream and the ledger says %s"
                         % (number, row["state"], tracked[number]["upstream"]))
    for number in sorted(set(tracked) - set(live)):
        drift.append("#%d is on the ledger and absent from GitHub" % number)
    if drift:
        for line in drift:
            print("DRIFT    %s" % line)
        print("the ledger is a snapshot: update %s with --fetch, then re-render" % LEDGER)
        return 1
    print("OK — %d issue(s) on the ledger match %s as of now" % (len(tracked), repo))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--fetch", action="store_true")
    parser.add_argument("--root", default=None)
    args = parser.parse_args(argv)
    root = find_root(Path(args.root)) if args.root else find_root(Path(__file__))
    if args.check:
        return check(root)
    if args.fetch:
        return fetch(root)
    return write(root)


if __name__ == "__main__":
    sys.exit(main())
